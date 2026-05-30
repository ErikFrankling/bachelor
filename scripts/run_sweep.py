#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from experiment import DEFAULT_TIERS, PENETRATIONS, SCENARIOS, SEEDS, TIERS, allowed_tiers, output_name
from prepare_routes import prepare_routes, scenario_files

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", "--scenario", nargs="+", default=SCENARIOS, choices=SCENARIOS)
    parser.add_argument("--tiers", nargs="+", default=DEFAULT_TIERS, choices=TIERS)
    parser.add_argument("--penetrations", nargs="+", type=float, default=PENETRATIONS)
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--delay", type=int, default=80)
    return parser.parse_args()

def run_case(args):
    case_no, total, widths, scenario, tier, penetration, seed, results_dir, force, gui, delay = args
    raw_dir = results_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tripinfo = raw_dir / output_name(scenario, tier, penetration, seed, "tripinfo")
    summary = raw_dir / output_name(scenario, tier, penetration, seed, "summary")
    edgedata = raw_dir / output_name(scenario, tier, penetration, seed, "edgedata")
    e1detectors = raw_dir / output_name(scenario, tier, penetration, seed, "e1detectors")
    required_outputs = [tripinfo, summary, edgedata]
    if scenario == "ring":
        required_outputs.append(e1detectors)
    if not gui and all(path.exists() for path in required_outputs) and not force:
        return "skipped", scenario, tier, penetration, seed
    print(
        format_progress("start", "case", case_no, total, scenario, tier, penetration, seed, widths),
        flush=True,
    )
    with tempfile.TemporaryDirectory(dir=results_dir) as tmp:
        route_files, additionals = prepare_routes(scenario, tier, penetration, seed, Path(tmp))
        config, _, _, end_time = scenario_files(scenario)
        measurement_additional = Path(tmp) / "measurements.add.xml"
        measurement_additional.write_text(measurements_xml(scenario, edgedata, e1detectors), encoding="utf-8")
        additionals = list(additionals) + [measurement_additional]
        binary = "sumo-gui" if gui else "sumo"
        if scenario == "ring":
            run_ring_traci(config, route_files, additionals, tripinfo, summary, seed, end_time, binary, delay)
        else:
            command = [
                binary,
                "-c", str(config),
                "--route-files", ",".join(str(path) for path in route_files),
                "--additional-files", ",".join(str(path) for path in additionals),
                "--tripinfo-output", str(tripinfo),
                "--summary-output", str(summary),
                "--seed", str(seed),
                "--no-step-log", "true",
                "--no-warnings", "true",
            ]
            if gui:
                command += ["--delay", str(delay), "--start"]
            subprocess.run(command, check=True)
    return "finished", scenario, tier, penetration, seed

def progress_widths(cases):
    return {
        "status": len("finished"),
        "progress": len(f"{len(cases)}/{len(cases)}"),
        "scenario": max(len(case[0]) for case in cases),
        "tier": max(len(case[1]) for case in cases),
        "penetration": max(len(f"{case[2]:g}") for case in cases),
        "seed": max(len(str(case[3])) for case in cases),
    }

def format_progress(status, counter_name, count, total, scenario, tier, penetration, seed, widths):
    counter = f"{count}/{total}"
    return (
        f"{status:<{widths['status']}} "
        f"{counter_name:<4} {counter:<{widths['progress']}} "
        f"scenario {scenario:<{widths['scenario']}} "
        f"tier {tier:<{widths['tier']}} "
        f"p {penetration:<{widths['penetration']}.3g} "
        f"seed {seed:<{widths['seed']}}"
    )

def run_ring_traci(config, route_files, additionals, tripinfo, summary, seed, end_time, binary, delay):
    if os.environ.get("SUMO_HOME"):
        import sys
        sys.path.insert(0, os.path.join(os.environ["SUMO_HOME"], "tools"))
    import contextlib
    import io
    import traci

    command = [
        binary,
        "-c", str(config),
        "--route-files", ",".join(str(path) for path in route_files),
        "--additional-files", ",".join(str(path) for path in additionals),
        "--tripinfo-output", str(tripinfo),
        "--summary-output", str(summary),
        "--seed", str(seed),
        "--no-step-log", "true",
        "--no-warnings", "true",
    ]
    if binary == "sumo-gui":
        command += ["--delay", str(delay), "--start"]

    with contextlib.redirect_stdout(io.StringIO()):
        traci.start(command)
    try:
        capped = False
        restoring = False
        original = None
        cap = None
        while traci.simulation.getTime() < end_time and traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            time = traci.simulation.getTime()
            if "v0" not in traci.vehicle.getIDList():
                continue
            if not capped and time >= 2000:
                original = traci.vehicle.getMaxSpeed("v0")
                cap = min(original, max(5, traci.vehicle.getSpeed("v0") - 5))
                traci.vehicle.setMaxSpeed("v0", cap)
                capped = True
            if capped and not restoring and time >= 2060:
                restoring = True
            if restoring:
                fraction = min(1, (time - 2060) / 300)
                traci.vehicle.setMaxSpeed("v0", cap + (original - cap) * fraction)
    finally:
        traci.close()

def measurements_xml(scenario, edgedata, e1detectors):
    lines = ["<additionals>"]
    lines.append(f'  <edgeData id="edge_flow" file="{edgedata}" freq="60" excludeEmpty="false"/>')
    if scenario == "ring":
        for detector in range(80):
            lines.append(
                f'  <inductionLoop id="ring_det_{detector}" lane="e{detector}_0" '
                f'pos="25" period="50" file="{e1detectors}"/>'
            )
    lines.append("</additionals>")
    return "\n".join(lines)

def selected_cases(args):
    results_dir = Path(args.results_dir).resolve()
    for scenario in args.scenarios:
        for tier in allowed_tiers(scenario, args.tiers):
            for penetration in args.penetrations:
                for seed in args.seeds:
                    yield scenario, tier, penetration, seed, results_dir, args.force, args.gui, args.delay

def main():
    args = parse_args()
    if args.gui and args.jobs != 1:
        raise SystemExit("--gui opens interactive SUMO windows, so use --jobs 1")
    if args.clean:
        shutil.rmtree(args.results_dir, ignore_errors=True)
    selected = list(selected_cases(args))
    total = len(selected)
    widths = progress_widths(selected)
    cases = [(index, total, widths, *case) for index, case in enumerate(selected, start=1)]
    if args.jobs == 1:
        completed = 0
        for case in cases:
            status, scenario, tier, penetration, seed = run_case(case)
            completed += 1
            print(
                format_progress(status, "done", completed, total, scenario, tier, penetration, seed, widths),
                flush=True,
            )
        return
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(run_case, case): case for case in cases}
        completed = 0
        for future in as_completed(futures):
            case = futures[future]
            try:
                status, scenario, tier, penetration, seed = future.result()
            except Exception:
                _, _, _, scenario, tier, penetration, seed, *_ = case
                print(
                    format_progress("failed", "done", completed, total, scenario, tier, penetration, seed, widths),
                    flush=True,
                )
                raise
            completed += 1
            print(
                format_progress(status, "done", completed, total, scenario, tier, penetration, seed, widths),
                flush=True,
            )

if __name__ == "__main__":
    main()
