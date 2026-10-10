"""O02 predeclared scenarios have independent, meaningful certificates."""

import json
from collections import Counter
from pathlib import Path

from backend.models import Placement, SolveRequest, UnloadStep
from backend.network import schedule_route
from backend.unloading import generate_unload_steps
from backend.validation import validate_vehicle_candidate


ROOT = Path("data/conflict_cases")


def _case(name):
    data = json.loads((ROOT / f"{name}.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / f"{name}.meta.json")
                      .read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data), meta


def test_manifest_predeclares_every_category():
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["cases"]) == 19
    assert Counter(e["category"] for e in manifest["cases"]) == {
        "combination_geometry": 5, "time_geometry": 5,
        "unload_mechanism_control": 5, "no_repair_control": 2,
        "known_infeasible_control": 2,
    }
    assert manifest["seeds"] == [22, 33, 44, 55, 66]


def test_combination_geometry_has_valid_alternative_not_single_box_failure():
    request, meta = _case("geometry-22")
    vehicle = request.vehicles[0]
    boxes = request.boxes
    assert all(box.length_mm < vehicle.length_mm and
               box.width_mm < vehicle.width_mm and
               box.height_mm < vehicle.height_mm for box in boxes)
    assert sum(b.length_mm * b.width_mm * b.height_mm for b in boxes) < (
        vehicle.length_mm * vehicle.width_mm * vehicle.height_mm)
    assert sum(b.length_mm for b in boxes) > vehicle.length_mm
    assert sum(b.width_mm for b in boxes) > vehicle.width_mm
    assert sum(b.height_mm for b in boxes) > vehicle.height_mm
    for route in meta["feasible_witness"]:
        placements = [Placement.model_validate(p) for p in route["placements"]]
        steps = [UnloadStep.model_validate(s) for s in route["unload_steps"]]
        assert validate_vehicle_candidate(request, route["vehicle_id"],
                                          route["store_ids"], placements,
                                          steps) == []


def test_time_geometry_has_real_window_rejections_and_valid_split():
    request, meta = _case("time-geometry-22")
    for order in (["S01", "S03"], ["S03", "S01"]):
        assert any(v.code == "TIME_WINDOW" for v in
                   schedule_route(request, "V02", order).violations)
    for route in meta["feasible_witness"]:
        placements = [Placement.model_validate(p) for p in route["placements"]]
        steps = [UnloadStep.model_validate(s) for s in route["unload_steps"]]
        assert validate_vehicle_candidate(request, route["vehicle_id"],
                                          route["store_ids"], placements,
                                          steps) == []


def test_unload_control_has_blocked_and_valid_layouts():
    request, meta = _case("unload-mechanism-22")
    boxes = {b.id: b for b in request.boxes}
    blocked = [Placement.model_validate(p)
               for p in meta["blocked_candidate"]["placements"]]
    _, error = generate_unload_steps(boxes, blocked, ["S01", "S02"])
    assert error is not None and error.code == "UNLOAD_BLOCKED"
    witness = meta["feasible_witness"][0]
    valid = [Placement.model_validate(p) for p in witness["placements"]]
    steps = [UnloadStep.model_validate(s) for s in witness["unload_steps"]]
    assert validate_vehicle_candidate(request, "V01", ["S01", "S02"],
                                      valid, steps) == []
