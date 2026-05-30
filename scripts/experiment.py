from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = ["ring", "bologna", "i80_vsl", "glosa_two_signal"]

TIERS = ["krauss", "idm", "acc", "cacc", "glosa"]
DEFAULT_TIERS = ["krauss", "idm", "acc", "cacc", "glosa"]

SIGNALIZED = {
    "bologna",
    "glosa_two_signal",
}

PENETRATIONS = [round(i * 0.05, 2) for i in range(21)]
SEEDS = [0, 1, 2]

TIER_TYPES = {
    "krauss": "av_krauss",
    "idm": "av_basic",
    "acc": "av_acc",
    "cacc": "av_cacc",
    "glosa": "av_glosa",
}

TIER_LABELS = {
    "krauss": "Krauss",
    "idm": "IDM",
    "acc": "ACC",
    "cacc": "CACC",
    "glosa": "GLOSA",
}

TIER_COLORS = {
    "krauss": "#111111",
    "idm": "#0072B2",
    "acc": "#E69F00",
    "cacc": "#009E73",
    "glosa": "#CC79A7",
}

def scenario_config(scenario):
    if scenario == "bologna":
        return ROOT / "config/scenarios/bologna/bologna.sumocfg"
    return ROOT / "config/scenarios" / f"{scenario}.sumocfg"

def allowed_tiers(scenario, tiers):
    if scenario in SIGNALIZED:
        return list(tiers)
    return [tier for tier in tiers if tier != "glosa"]

def output_name(scenario, tier, penetration, seed, kind):
    return f"{scenario}_{tier}_p{penetration}_s{seed}_{kind}.xml"
