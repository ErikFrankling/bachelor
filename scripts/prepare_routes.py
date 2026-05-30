import math
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from experiment import ROOT, TIER_TYPES, scenario_config

def config_value(config, tag):
    root = ET.parse(config).getroot()
    elem = root.find(f".//{tag}")
    if elem is None:
        return ""
    return elem.get("value", "")

def split_files(value):
    return [part.strip() for part in value.split(",") if part.strip()]

def resolve_files(config, value):
    return [(config.parent / path).resolve() for path in split_files(value)]

def scenario_files(scenario):
    config = scenario_config(scenario)
    routes = resolve_files(config, config_value(config, "route-files"))
    additionals = resolve_files(config, config_value(config, "additional-files"))
    end_time = float(config_value(config, "end") or 0)
    return config, routes, additionals, end_time

def route_edges(root, route_id):
    route = root.find(f".//route[@id='{route_id}']")
    if route is None:
        return None
    return route.get("edges")

def flow_count(flow):
    if flow.get("number"):
        return int(float(flow.get("number")))
    begin = float(flow.get("begin", 0))
    end = float(flow.get("end", begin))
    if flow.get("vehsPerHour"):
        return int(math.floor((end - begin) * float(flow.get("vehsPerHour")) / 3600))
    if flow.get("period"):
        return int(math.floor((end - begin) / float(flow.get("period"))))
    return 0

def expand_flows(root):
    for flow in list(root.findall("flow")):
        count = flow_count(flow)
        if count <= 0:
            root.remove(flow)
            continue
        begin = float(flow.get("begin", 0))
        end = float(flow.get("end", begin))
        step = (end - begin) / count if count else 0
        edges = route_edges(root, flow.get("route", "")) if flow.get("route") else None
        for index in range(count):
            vehicle = ET.Element("vehicle")
            vehicle.set("id", f"{flow.get('id', 'flow')}.{index}")
            vehicle.set("depart", f"{begin + index * step:.2f}")
            for key in ["type", "route", "from", "to", "departLane", "departSpeed"]:
                if flow.get(key):
                    vehicle.set(key, flow.get(key))
            if edges is not None and not vehicle.get("route"):
                ET.SubElement(vehicle, "route", {"edges": edges})
            root.append(vehicle)
        root.remove(flow)

def mix_file(path, tier, penetration, seed):
    tree = ET.parse(path)
    root = tree.getroot()
    expand_flows(root)
    vehicles = [
        vehicle for vehicle in root.findall("vehicle")
        if vehicle.get("type", "human") in {"", "human"}
    ]
    count = round(len(vehicles) * penetration)
    rng = random.Random(f"{seed}:{path.name}:{penetration}")
    selected = set(rng.sample([vehicle.get("id") for vehicle in vehicles], count))
    av_type = TIER_TYPES[tier]
    for vehicle in vehicles:
        vehicle.set("type", av_type if vehicle.get("id") in selected else "human")
    ordered = sorted(root.findall("vehicle"), key=lambda vehicle: float(vehicle.get("depart", 0)))
    for vehicle in root.findall("vehicle"):
        root.remove(vehicle)
    for vehicle in ordered:
        root.append(vehicle)
    return tree

def prepare_routes(scenario, tier, penetration, seed, work_dir):
    _, routes, additionals, _ = scenario_files(scenario)
    work_dir.mkdir(parents=True, exist_ok=True)
    mixed = []
    for index, route in enumerate(routes):
        output = work_dir / f"{scenario}_{tier}_{penetration}_{seed}_{index}.rou.xml"
        mix_file(route, tier, penetration, seed).write(output, encoding="utf-8", xml_declaration=True)
        mixed.append(output)
    return mixed, additionals
