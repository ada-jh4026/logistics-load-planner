"""O01: repair history must describe real, independently valid state changes."""

import json
from pathlib import Path

from backend.budget import Budget
from backend.models import JobResponse, SolveRequest
from backend.solver import solve_coupled
from backend.validation import validate_solution
from tests.test_coupled import _make_c10_request


def _routes(routes):
    return [route.model_dump() for route in routes]


def test_successful_repair_replays_to_final_valid_routes():
    request = _make_c10_request()
    result = solve_coupled(request)
    trace = result.repair_trace
    assert trace.status == "repaired"
    assert trace.initial_metrics.served_stores == 0
    assert trace.final_metrics.served_stores == 1
    assert trace.attempted_count >= trace.accepted_count == 1
    assert any(e.action == "pack_failed" and e.outcome == "detected"
               for e in trace.events)

    current = _routes(trace.initial_routes)
    for event in trace.events:
        assert set(event.store_ids) <= {s.id for s in request.stores}
        assert set(event.box_ids) <= {b.id for b in request.boxes}
        if event.outcome == "accepted":
            assert _routes(event.routes_before) == current
            assert event.metrics_before.served_stores == 0
            assert event.metrics_after.served_stores == 1
            current = _routes(event.routes_after)
        else:
            assert event.routes_before is None
            assert event.routes_after is None
    assert current == _routes(result.routes)
    assert validate_solution(request, result) == []


def test_no_repair_is_distinct_from_missing_trace():
    request = SolveRequest.model_validate(json.loads(
        Path("data/cases/small-11.json").read_text(encoding="utf-8")))
    result = solve_coupled(request)
    assert result.repair_trace.status == "not_needed"
    assert result.repair_trace.attempted_count == 0
    assert result.repair_trace.accepted_count == 0

    old_response = json.loads(Path(
        "docs/playbook/examples/response-success.json").read_text(encoding="utf-8"))
    parsed = JobResponse.model_validate(old_response)
    assert parsed.result.repair_trace is None


def test_unresolved_case_does_not_claim_impossible_geometry():
    request = _make_c10_request()
    request.vehicles = [request.vehicles[0]]
    result = solve_coupled(request)
    trace = result.repair_trace
    assert trace.status == "unresolved"
    assert trace.accepted_count == 0
    assert result.metrics.served_stores == 0
    assert validate_solution(request, result) == []


def test_expired_budget_keeps_valid_snapshot():
    request = _make_c10_request()
    state = [0.0]
    budget = Budget(1000, 100000, clock=lambda: state[0])
    state[0] = 10.0
    result = solve_coupled(request, budget=budget)
    assert result.repair_trace.status == "budget_exhausted"
    assert result.repair_trace.accepted_count == 0
    assert validate_solution(request, result) == []


def test_truncated_rejections_keep_counts_and_accepted_steps(monkeypatch):
    from backend import solver

    request = _make_c10_request()
    large = request.vehicles[1]
    large.id = "V03"
    rejected_vehicle = request.vehicles[0].model_copy(deep=True)
    rejected_vehicle.id = "V02"
    rejected_vehicle.fixed_cost = 20
    request.vehicles.insert(1, rejected_vehicle)
    monkeypatch.setattr(solver, "MAX_REJECT_EVENTS", 0)

    result = solve_coupled(request)
    trace = result.repair_trace
    assert trace.status == "repaired"
    assert trace.attempted_count >= 2
    assert trace.accepted_count == 1
    assert trace.truncated is True
    assert trace.omitted_count >= 1
    assert any(e.outcome == "accepted" for e in trace.events)
    assert not any(e.outcome == "rejected" for e in trace.events)
    assert validate_solution(request, result) == []
