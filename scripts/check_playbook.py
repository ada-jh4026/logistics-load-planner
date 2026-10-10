"""Validate the handoff package, not the future application."""
from pathlib import Path
import json
import math

ROOT = Path(__file__).resolve().parents[1]
PB = ROOT / "docs" / "playbook"

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def check_board():
    board = read_json(PB / "board.json")
    tasks = board["tasks"]
    by_id = {t["id"]: t for t in tasks}
    require(len(by_id) == len(tasks), "Duplicate task ID")
    legal = set(board["task_status_values"])
    for task in tasks:
        tid = task["id"]
        require(task["status"] in legal, f"{tid}: invalid status")
        require((ROOT / task["card"]).is_file(), f"{tid}: missing task card")
        require(task["estimate_minutes"] > 0, f"{tid}: invalid estimate")
        for dep in task["depends_on"]:
            require(dep in by_id and dep != tid, f"{tid}: invalid dependency {dep}")
        if task["status"] == "done":
            require(task["evidence"], f"{tid}: done without evidence")
            for evidence in task["evidence"]:
                require((ROOT / evidence).is_file(), f"{tid}: missing evidence {evidence}")
            require(all(by_id[d]["status"] == "done" for d in task["depends_on"]),
                    f"{tid}: done before dependencies")
        if task["status"] == "blocked":
            require(bool(task["blocked_reason"]), f"{tid}: missing blocked reason")
    visiting, visited = set(), set()
    def visit(tid):
        require(tid not in visiting, f"Dependency cycle at {tid}")
        if tid in visited:
            return
        visiting.add(tid)
        for dep in by_id[tid]["depends_on"]:
            visit(dep)
        visiting.remove(tid)
        visited.add(tid)
    for tid in by_id:
        visit(tid)
    cards = {p.stem for p in (PB / "tasks").glob("*.md")}
    require(cards == set(by_id), "Task cards and board differ")
    ready = [t["id"] for t in tasks if t["status"] == "pending"
             and all(by_id[d]["status"] == "done" for d in t["depends_on"])]
    return len(tasks), ready

def close(actual, expected, label):
    require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9),
            f"{label}: {actual} != {expected}")

def check_pair(request_name, response_name):
    req = read_json(PB / "examples" / request_name)
    resp = read_json(PB / "examples" / response_name)
    require(req["schema_version"] == resp["schema_version"] == "0.1", "Version mismatch")
    require(req["case_id"] == resp["case_id"], "Case ID mismatch")
    require(resp["is_mock"] is True, "Documentation response must be marked mock")
    require(resp["elapsed_ms"] == 0, "No invented measured runtime in UI fixture")
    require(req["options"]["method"] == resp["method"], "Method mismatch")
    if resp["status"] == "failed":
        require(resp["result"] is None and resp["error"] is not None, "Bad error fixture")
        return
    result = resp["result"]
    stores = {s["id"]: s for s in req["stores"]}
    boxes = {b["id"]: b for b in req["boxes"]}
    vehicles = {v["id"]: v for v in req["vehicles"]}
    used, served_stores, served_boxes, represented = [], [], [], []
    total_distance = total_cost = 0
    for route in result["routes"]:
        vehicle = vehicles[route["vehicle_id"]]
        used.append(vehicle)
        represented.extend(route["box_ids"])
        served_boxes.extend(route["box_ids"])
        served_stores.extend(route["store_ids"])
        require(set(p["box_id"] for p in route["placements"]) == set(route["box_ids"]),
                "Placement IDs do not match route")
        require(set(s["box_id"] for s in route["unload_steps"]) == set(route["box_ids"]),
                "Unload IDs do not match route")
        require([s["step"] for s in route["unload_steps"]]
                == list(range(1, len(route["box_ids"]) + 1)), "Nonconsecutive unload steps")
        previous, clock, distance = req["depot"], req["depot"]["departure_min"], 0
        require(len(route["stops"]) == len(route["store_ids"]), "Stop count mismatch")
        for store_id, stop in zip(route["store_ids"], route["stops"]):
            store = stores[store_id]
            leg = math.hypot(store["x_km"]-previous["x_km"], store["y_km"]-previous["y_km"])
            distance += leg
            arrival = clock + leg / req["options"]["speed_kmph"] * 60
            start = max(arrival, store["window_start_min"])
            clock = start + store["service_min"]
            require(stop["store_id"] == store_id, "Stop order mismatch")
            close(stop["arrival_min"], arrival, "arrival")
            close(stop["service_start_min"], start, "service start")
            close(stop["departure_min"], clock, "departure")
            require(start <= store["window_end_min"], "Fixture misses time window")
            previous = store
        back = math.hypot(previous["x_km"]-req["depot"]["x_km"],
                          previous["y_km"]-req["depot"]["y_km"])
        distance += back
        close(route["return_min"], clock + back / req["options"]["speed_kmph"]*60, "return")
        close(route["distance_km"], distance, "distance")
        cost = vehicle["fixed_cost"] + vehicle["cost_per_km"] * distance
        close(route["cost"], cost, "cost")
        total_distance += distance
        total_cost += cost
    for entry in result["unassigned"]:
        require(set(entry["box_ids"]) == {b["id"] for b in boxes.values()
                                          if b["store_id"] == entry["store_id"]},
                "Unassigned store must include all its boxes")
        represented.extend(entry["box_ids"])
    require(len(represented) == len(set(represented)), "Duplicate box assignment")
    require(set(represented) == set(boxes), "Incomplete assignment")
    require(len(served_stores) == len(set(served_stores)), "Store served twice")
    require(len(used) == len({v["id"] for v in used}), "Vehicle reused")
    metric = result["metrics"]
    expected = {
        "total_stores": len(stores), "served_stores": len(served_stores),
        "total_boxes": len(boxes), "served_boxes": len(served_boxes),
        "completion_rate": len(served_stores)/len(stores), "used_vehicles": len(used),
        "total_distance_km": total_distance, "total_cost": total_cost,
        "on_time_rate": 1, "unload_block_count": 0,
        "volume_utilization": sum(boxes[b]["length_mm"]*boxes[b]["width_mm"]*boxes[b]["height_mm"]
                                  for b in served_boxes) /
                              sum(v["length_mm"]*v["width_mm"]*v["height_mm"] for v in used),
        "weight_utilization": sum(boxes[b]["weight_kg"] for b in served_boxes) /
                              sum(v["max_weight_kg"] for v in used)
    }
    for name, value in expected.items():
        close(metric[name], value, name)
    require(result["validation"] == {"valid": True, "violations": []},
            "Fixture validation declaration mismatch")
    require((resp["status"] == "succeeded") == (len(result["unassigned"]) == 0),
            "Fixture status mismatch")

def main():
    for filename in ["STATE.md", "DECISIONS.md", "CONTRACT.md", "ALGORITHMS.md",
                     "ACCEPTANCE.md", "EVALUATION.md", "SCHEDULE.md", "HANDOFF.md"]:
        require((PB / filename).is_file(), f"Missing document {filename}")
    count, ready = check_board()
    check_pair("request-success.json", "response-success.json")
    check_pair("request-partial.json", "response-partial.json")
    check_pair("request-success.json", "response-failed.json")
    print(f"PASS: {count} task cards; acyclic dependencies; 3 UI example pairs consistent.")
    print("Ready tasks:", ", ".join(ready) or "(none)")
    print("This verifies planning artifacts only; no application or solver tests were run.")

if __name__ == "__main__":
    main()

