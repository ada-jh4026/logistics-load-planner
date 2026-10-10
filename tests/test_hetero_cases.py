"""Verify the fixed mixed-carton witnesses independently of the packer."""

import json
from pathlib import Path
import pytest

from backend.models import Placement, SolveRequest, UnloadStep
from backend.validation import validate_vehicle_candidate
from backend.validation import validate_solution
from backend.solver import solve
from backend.packing import pack_route
from backend.unloading import validate_loading_steps, generate_loading_steps


def test_all_heterogeneous_witnesses_are_independently_feasible():
    root = Path(__file__).resolve().parents[1]
    directory = root / "data/hetero_cases"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    paths = [root / entry["path"] for entry in manifest["cases"]]
    paths.append(directory / "hetero-development.json")
    for path in paths:
        request = SolveRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))
        metadata = json.loads(path.with_suffix(".meta.json").read_text(encoding="utf-8"))
        assert len({(b.length_mm, b.width_mm, b.height_mm) for b in request.boxes}) > 1
        for witness in metadata["feasible_witness"]:
            violations = validate_vehicle_candidate(
                request, witness["vehicle_id"], witness["store_ids"],
                [Placement.model_validate(p) for p in witness["placements"]],
                [UnloadStep.model_validate(s) for s in witness["unload_steps"]],
            )
            assert violations == [], (request.case_id, violations)


@pytest.mark.parametrize("method", ["greedy", "sequential", "coupled"])
def test_known_feasible_multistop_regression_is_fully_served(method):
    request = SolveRequest.model_validate(json.loads(
        Path("data/hetero_cases/hetero-development.json").read_text(encoding="utf-8")))
    request.options.method = method
    result = solve(request)
    assert result.metrics.served_stores == 3
    assert result.metrics.served_boxes == 12
    assert validate_solution(request, result) == []
    boxes = {b.id: b for b in request.boxes}
    for route in result.routes:
        vehicle = next(v for v in request.vehicles if v.id == route.vehicle_id)
        assert validate_loading_steps(generate_loading_steps(route.unload_steps),
                                      boxes, route.placements, vehicle) == []


def test_mixed_failed_routes_are_recovered_without_losing_valid_stores():
    request = SolveRequest.model_validate(json.loads(
        Path("data/hetero_cases/small-11-mixed-1.json").read_text(encoding="utf-8")))
    result = solve(request)
    assert result.metrics.served_stores == 10
    assert validate_solution(request, result) == []
    trace = result.repair_trace
    assert trace.accepted_count > 0
    state = [r.model_dump() for r in trace.initial_routes]
    for event in trace.events:
        if event.outcome == "accepted":
            assert [r.model_dump() for r in event.routes_before] == state
            state = [r.model_dump() for r in event.routes_after]
            assert event.metrics_after.served_stores > event.metrics_before.served_stores
    assert state == [r.model_dump() for r in result.routes]


def test_route_pack_is_deterministic_for_mixed_cartons():
    request = SolveRequest.model_validate(json.loads(
        Path("data/hetero_cases/hetero-development.json").read_text(encoding="utf-8")))
    ids = [s.id for s in request.stores]
    first = pack_route(request, "V01", ids)
    second = pack_route(request, "V01", ids)
    assert first.success and second.success
    assert first.placements == second.placements
    assert first.unload_steps == second.unload_steps
