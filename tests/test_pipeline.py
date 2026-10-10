"""B12 端到端 pipeline 测试（solve 路由 + 完整流程）。"""

import json
from pathlib import Path

import pytest

from backend.models import SolveRequest
from backend.solver import solve
from backend.validation import validate_solution


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _set_method(req: SolveRequest, method: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{req.case_id}.json").read_text(encoding="utf-8"))
    data["options"]["method"] = method
    return SolveRequest.model_validate(data)


@pytest.mark.parametrize("method", ["greedy", "sequential", "coupled"])
def test_solve_routes_methods(method):
    req = _load_case("c01")
    req = _set_method(req, method)
    result = solve(req)
    # 结果必须通过独立校验（无违规）
    assert validate_solution(req, result) == []


@pytest.mark.parametrize("method", ["greedy", "sequential", "coupled"])
def test_solve_small11_valid(method):
    req = _load_case("small-11")
    req = _set_method(req, method)
    result = solve(req)
    assert validate_solution(req, result) == []


def test_solve_c07_partial():
    req = _load_case("c07")
    result = solve(req)
    assert result.metrics.served_stores == 1
    assert len(result.unassigned) == 1
    assert validate_solution(req, result) == []


def test_unknown_method_raises():
    req = _load_case("c01")
    data = json.loads(Path("data/cases/c01.json").read_text(encoding="utf-8"))
    data["options"]["method"] = "magic"
    with pytest.raises(ValueError):
        solve(SolveRequest.model_validate(data))
