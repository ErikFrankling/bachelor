# Thesis SUMO Experiments

This is the accompanying SUMO simulation harness for the bachelor thesis "A Microscopic Traffic Simulation Study of Autonomous Vehicle Penetration Rate Effects on Traffic Flow Across Different Control Models and Scenarios", written by Erik Frankling (@ErikFrankling) and Adam Wallén (@AdamWalln).

This repository contains SUMO scenarios and Python scripts for running the thesis experiments, parsing raw XML outputs, and plotting results.

## Dependencies

Required tools: Python 3, SUMO, TraCI, pandas, matplotlib, and numpy.

## Examples

Run the full experiment suite with four parallel SUMO workers, then parse the raw XML and generate all plots in the default `results` directory:

```sh
nix develop
python scripts/run_sweep.py --jobs 4 && python scripts/parse_results.py && python scripts/plot_results.py
```

Run a short test in `results/test`, overwrite that test directory, then parse and plot only that test output. To make it quick, this only runs the `glosa_two_signal` scenario with `0`, `0.5`, and `1` penetration values, and only one seed:

```sh
python scripts/run_sweep.py --scenario glosa_two_signal --penetrations 0 0.5 1 --seeds 0 --results-dir results/test --clean --jobs 4 && python scripts/parse_results.py --results-dir results/test && python scripts/plot_results.py --results-dir results/test
```

Inspect one simulation case in the SUMO GUI. This is for visual debugging, so it only runs the selected case and does not need parsing or plotting:

```sh
python scripts/run_sweep.py  --seeds 0 --gui --delay 80 --results-dir results/test --force --scenario ring --tiers idm --penetrations 0.5
```

## Scripts

### `scripts/run_sweep.py`

Runs SUMO experiments and writes raw XML output to `results/raw/`.

Options:

- `--scenarios`: one or more of `ring`, `bologna`, `i80_vsl`, `glosa_two_signal` (default: all)
- `--tiers`: one or more of `krauss`, `idm`, `acc`, `cacc`, `glosa` (default: all)
- `--penetrations`: AV penetration values (default: `0.0` to `1.0` in `0.05` steps)
- `--seeds`: random seeds (default: `0 1 2`)
- `--results-dir`: output directory (default: `results`)
- `--jobs`: parallel workers (default: `1`)
- `--force`: rerun cases even if outputs already exist
- `--clean`: remove the results directory before running
- `--gui`: run with `sumo-gui` for visual inspection
- `--delay`: GUI delay in milliseconds (default: `80`)

### `scripts/parse_results.py`

Parses raw XML files from `results/raw/` and writes `results/processed/metrics.csv`.

Options:

- `--results-dir`: results directory (default: `results`)

### `scripts/plot_results.py`

Reads `results/processed/metrics.csv` and writes plots to `results/plots/`.

Options:

- `--results-dir`: results directory (default: `results`)
- `--exclude-tiers`: tiers to leave out of plots

## Nix

A Nix flake is included for users of the Nix package manager. Run `nix develop` to enter a development shell with all necessary dependencies.
