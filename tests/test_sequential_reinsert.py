"""The experiment baseline must be a real, independently valid solver."""

import json
from pathlib import Path

from backend.baselines import solve_sequential
from backend.models import SolveRequest
from backend.validation import validate_solution
from scripts.sequential_reinsert import solve_sequential_reinsert


def test_reinsert_recovers_simple_size_failure():
    data = json.loads(Path("data/conflict_cases/trace-c10.json")
                      .read_text(encoding="utf-8"))
    request = SolveRequest.model_validate(data)
    baseline = solve_sequential(request)
    result = solve_sequential_reinsert(request)
    assert baseline.metrics.served_stores == 0
    assert result.metrics.served_stores == 1
    assert result.routes[0].vehicle_id == "V02"
    assert validate_solution(request, result) == []


def test_reinsert_does_not_modify_already_served_case():
    data = json.loads(Path("data/cases/small-11.json")
                      .read_text(encoding="utf-8"))
    request = SolveRequest.model_validate(data)
    baseline = solve_sequential(request)
    result = solve_sequential_reinsert(request)
    assert result.metrics.served_stores == baseline.metrics.served_stores
    assert [(r.vehicle_id, r.store_ids) for r in result.routes] == [
        (r.vehicle_id, r.store_ids) for r in baseline.routes]
    assert validate_solution(request, result) == []
