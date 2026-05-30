#!/usr/bin/env python3

import argparse
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from experiment import scenario_config

def mean(values):
    return sum(values) / len(values) if values else 0

def parse_name(path):
    match = re.match(r"(.+)_(.+)_p([0-9.]+)_s([0-9]+)_tripinfo.xml", path.name)
    if not match:
        return None
    return {
        "scenario": match.group(1),
        "tier": match.group(2),
        "penetration": float(match.group(3)),
        "seed": int(match.group(4)),
    }

def parse_tripinfo(path):
    try:
        trips = ET.parse(path).getroot().findall("tripinfo")
    except ET.ParseError as error:
        raise SystemExit(f"Could not parse {path}: {error}") from error
    return {
        "completed": len(trips),
        "travel_time": mean([float(trip.get("duration", 0)) for trip in trips]),
        "waiting_time": mean([float(trip.get("waitingTime", 0)) for trip in trips]),
        "time_loss": mean([float(trip.get("timeLoss", 0)) for trip in trips]),
    }

def parse_summary(path):
    if not path.exists():
        return {"speed": 0, "running": 0}
    steps = ET.parse(path).getroot().findall("step")
    steps = [step for step in steps if float(step.get("running", 0)) > 0 and float(step.get("meanSpeed", 0)) >= 0]
    return {
        "speed": mean([float(step.get("meanSpeed", 0)) for step in steps]),
        "running": mean([float(step.get("running", 0)) for step in steps]),
    }

def scenario_edge_lengths(scenario):
    config = scenario_config(scenario)
    root = ET.parse(config).getroot()
    net = root.find(".//net-file")
    if net is None:
        return {}
    net_path = (config.parent / net.get("value")).resolve()
    lengths = {}
    for edge in ET.parse(net_path).getroot().findall("edge"):
        if edge.get("function") == "internal":
            continue
        lane_lengths = [
            float(lane.get("length"))
            for lane in edge.findall("lane")
            if lane.get("length") is not None
        ]
        if lane_lengths:
            lengths[edge.get("id")] = mean(lane_lengths) / 1000.0
    return lengths

def parse_edge_measures(path, edge_lengths):
    if not path.exists():
        return {"edge_flow": None, "density": None}
    flows = []
    densities = []
    interval_density = 0.0
    interval_length = 0.0
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "edge":
            flow = float(elem.get("flow", "nan"))
            if math.isfinite(flow):
                flows.append(flow)
            density = float(elem.get("density", 0))
            length = edge_lengths.get(elem.get("id"))
            if length and math.isfinite(density):
                interval_density += density * length
                interval_length += length
        elif elem.tag == "interval":
            if interval_length > 0:
                densities.append(interval_density / interval_length)
            interval_density = 0.0
            interval_length = 0.0
        elem.clear()
    return {
        "edge_flow": mean(flows) if flows else None,
        "density": mean(densities) if densities else None,
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args()
    results = Path(args.results_dir)
    rows = []
    edge_lengths = {}
    for path in sorted((results / "raw").glob("*_tripinfo.xml")):
        row = parse_name(path)
        if row is None:
            continue
        if row["scenario"] not in edge_lengths:
            edge_lengths[row["scenario"]] = scenario_edge_lengths(row["scenario"])
        summary = path.with_name(path.name.replace("_tripinfo.xml", "_summary.xml"))
        edgedata = path.with_name(path.name.replace("_tripinfo.xml", "_edgedata.xml"))
        rows.append(
            row
            | parse_tripinfo(path)
            | parse_summary(summary)
            | parse_edge_measures(edgedata, edge_lengths[row["scenario"]])
        )
    output_dir = results / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).sort_values(["scenario", "tier", "penetration", "seed"]).to_csv(output_dir / "metrics.csv", index=False)
    print(output_dir / "metrics.csv")

if __name__ == "__main__":
    main()
