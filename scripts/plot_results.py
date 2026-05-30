#!/usr/bin/env python3

import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from experiment import TIER_COLORS, TIER_LABELS, TIERS, scenario_config

BASELINE_COLOR = "#6B6B6B"

MARKERS = {
    "krauss": "x",
    "idm": "o",
    "acc": "^",
    "cacc": "s",
    "glosa": "D",
}

PLOTS = [
    ("speed", "Mean speed [m/s]", "speed"),
    ("throughput", "Throughput [veh/h]", "throughput"),
    ("travel_time", "Travel time [s]", "travel_time"),
    ("waiting_time", "Waiting time [s]", "waiting_time"),
    ("time_loss", "Time loss [s]", "time_loss"),
    ("completed", "Completed trips", "completed"),
    ("running", "Mean vehicles in network", "running"),
    ("density", "Traffic density [veh/km]", "density"),
]

RING_PLOTS = [
    ("speed", "Mean speed [m/s]", "speed"),
    ("lap_time", "Estimated lap time [s]", "lap_time"),
    ("density", "Traffic density [veh/km]", "density"),
]

RING_DETECTOR_RE = re.compile(
    r"^ring_(?P<tier>[^_]+)_p(?P<penetration>[0-9.]+)_s(?P<seed>[0-9]+)_e1detectors\.xml$"
)

def apply_style():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Times New Roman", "Times"],
        "mathtext.fontset": "dejavuserif",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.linewidth": 0.75,
        "axes.grid": True,
        "grid.color": "#B0B0B0",
        "grid.linestyle": "--",
        "grid.linewidth": 0.45,
        "grid.alpha": 0.45,
        "legend.fontsize": 6.5,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "xtick.direction": "in",
        "ytick.direction": "in",
        "xtick.top": True,
        "ytick.right": True,
        "figure.dpi": 140,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
    })

def plot_metric(df, metric, ylabel, output):
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    baseline_rows = df[df["penetration"] == 0]
    if not baseline_rows.empty:
        baseline = baseline_rows.groupby("seed")[metric].mean().mean()
        ax.axhline(
            baseline,
            color=BASELINE_COLOR,
            linestyle=":",
            linewidth=1.0,
            label="Human baseline",
            zorder=0,
        )
    for tier in TIERS:
        tier_df = df[df["tier"] == tier]
        if tier_df.empty:
            continue
        grouped = tier_df.groupby("penetration")[metric]
        avg = grouped.mean()
        std = grouped.std().fillna(0)
        ax.plot(
            avg.index,
            avg.values,
            marker=MARKERS[tier],
            linewidth=1.15,
            markersize=3.2,
            markeredgewidth=0.8,
            label=TIER_LABELS[tier],
            color=TIER_COLORS[tier],
        )
        ax.fill_between(avg.index, avg - std, avg + std, alpha=0.12, color=TIER_COLORS[tier], linewidth=0)
    ax.set_xlabel("AV penetration")
    ax.set_ylabel(ylabel)
    ax.set_xlim(-0.02, 1.02)
    ax.legend(frameon=False, ncol=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output)
    plt.close(fig)

def scenario_duration(scenario):
    root = ET.parse(scenario_config(scenario)).getroot()
    begin = root.find(".//begin")
    end = root.find(".//end")
    begin_time = float(begin.get("value")) if begin is not None else 0.0
    end_time = float(end.get("value")) if end is not None else begin_time
    return max(1.0, end_time - begin_time)

def add_throughput(df):
    df = df.copy()
    for scenario in df["scenario"].unique():
        duration = scenario_duration(scenario)
        mask = df["scenario"] == scenario
        df.loc[mask, "throughput"] = df.loc[mask, "completed"] * 3600.0 / duration
    if "edge_flow" in df.columns:
        has_edge_flow = df["edge_flow"].notna()
        df.loc[has_edge_flow, "throughput"] = df.loc[has_edge_flow, "edge_flow"]
    return df

def ring_data(df):
    df = df.copy()
    df["lap_time"] = 4000 / df["speed"]
    return df

def read_ring_detectors(path):
    rows = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "interval":
            continue
        det_id = elem.attrib.get("id", "")
        if not det_id.startswith("ring_det_"):
            elem.clear()
            continue
        speed = float(elem.attrib.get("speed", "-1"))
        if speed >= 0:
            detector = int(det_id.rsplit("_", 1)[1])
            rows.append({
                "time": float(elem.attrib["begin"]),
                "position": detector * 50.0,
                "speed": speed,
            })
        elem.clear()
    return pd.DataFrame(rows)

def parse_edge_flow(path):
    flows = []
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "edge":
            flow = float(elem.attrib.get("flow", "nan"))
            if np.isfinite(flow):
                flows.append(flow)
        elem.clear()
    return float(np.mean(flows)) if flows else np.nan

def parse_edgedata_name(path):
    match = re.match(r"(.+)_(.+)_p([0-9.]+)_s([0-9]+)_edgedata.xml", path.name)
    if not match:
        return None
    return {
        "tier": match.group(2),
        "penetration": float(match.group(3)),
        "seed": int(match.group(4)),
    }

def load_edge_flow(results, scenario, tiers):
    rows = []
    raw = results / "raw"
    for path in raw.glob(f"{scenario}_*_edgedata.xml"):
        row = parse_edgedata_name(path)
        if row is None or row["tier"] not in tiers:
            continue
        rows.append(row | {"edge_flow": parse_edge_flow(path)})
    return pd.DataFrame(rows)

def load_ring_time_space_panels(results, panels):
    raw = results / "raw"
    data = []
    for tier, penetration in panels:
        path = raw / f"ring_{tier}_p{penetration}_s0_e1detectors.xml"
        if not path.exists():
            continue
        df = read_ring_detectors(path)
        if not df.empty:
            data.append((tier, penetration, df))
    return data

def draw_ring_time_space(data, output, nrows, ncols, figsize, title):
    if not data:
        return

    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharex=True, sharey=True)
    axes = np.atleast_1d(axes).ravel()
    fig.subplots_adjust(left=0.075, right=0.985, top=0.89, bottom=0.14, wspace=0.22, hspace=0.42)
    last_image = None
    for ax, (tier, penetration, df) in zip(axes, data):
        grid = (
            df.pivot_table(index="position", columns="time", values="speed", aggfunc="mean")
            .sort_index()
            .sort_index(axis=1)
        )
        values = grid.to_numpy()
        last_image = ax.imshow(
            values,
            origin="lower",
            aspect="auto",
            cmap="RdYlGn",
            vmin=0,
            vmax=15.0,
            extent=[
                float(grid.columns.min()),
                float(grid.columns.max()),
                float(grid.index.min()),
                float(grid.index.max()),
            ],
        )
        ax.set_title(f"{TIER_LABELS[tier]}, p={penetration:g}", fontsize=8)
        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Position along ring [m]")
    for ax in axes[len(data):]:
        ax.axis("off")
    if last_image is not None:
        colorbar_axis = fig.add_axes([0.28, 0.06, 0.44, 0.028])
        colorbar = fig.colorbar(last_image, cax=colorbar_axis, orientation="horizontal")
        colorbar.set_label("Speed [m/s]")
    fig.suptitle(title, fontsize=10)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output)
    plt.close(fig)

def plot_ring_time_space(results, baseline_output, av_output):
    preferred_tiers = ["krauss", "acc", "cacc"]
    baseline_data = load_ring_time_space_panels(
        results,
        [(tier, 0.0) for tier in preferred_tiers],
    )
    if baseline_data:
        draw_ring_time_space(
            [baseline_data[0]],
            baseline_output,
            nrows=1,
            ncols=1,
            figsize=(5.2, 3.6),
            title="Ring: Time-space speed heatmap, p=0",
        )

    av_panels = [(tier, penetration) for tier in preferred_tiers for penetration in (0.5, 1.0)]
    av_data = load_ring_time_space_panels(results, av_panels)
    draw_ring_time_space(
        av_data,
        av_output,
        nrows=3,
        ncols=2,
        figsize=(8.0, 7.6),
        title="Ring: Time-space speed heatmap, p=0.5 and p=1",
    )

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--exclude-tiers", nargs="*", default=[])
    args = parser.parse_args()
    apply_style()
    results = Path(args.results_dir)
    df = pd.read_csv(results / "processed/metrics.csv")
    if args.exclude_tiers:
        df = df[~df["tier"].isin(args.exclude_tiers)]
    df = add_throughput(df)
    for scenario in sorted(df["scenario"].unique()):
        scenario_df = df[df["scenario"] == scenario]
        edge_flow = load_edge_flow(results, scenario, list(scenario_df["tier"].unique()))
        if not edge_flow.empty:
            scenario_df = scenario_df.drop(columns=["edge_flow"], errors="ignore").merge(
                edge_flow,
                on=["tier", "penetration", "seed"],
                how="left",
            )
            scenario_df = add_throughput(scenario_df)
        plot_dir = results / "plots" / scenario
        plot_dir.mkdir(parents=True, exist_ok=True)
        for old_plot in plot_dir.glob("*.png"):
            old_plot.unlink()
        plots = PLOTS
        if scenario == "ring":
            scenario_df = ring_data(scenario_df)
            plots = RING_PLOTS
        for metric, ylabel, name in plots:
            plot_metric(scenario_df, metric, ylabel, results / "plots" / scenario / f"{name}.png")
        if scenario == "ring":
            plot_ring_time_space(
                results,
                results / "plots" / scenario / "time_space_speed_p0.png",
                results / "plots" / scenario / "time_space_speed_av.png",
            )
    print(results / "plots")

if __name__ == "__main__":
    main()
