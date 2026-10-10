"""B10 基线连通测试（A4/A5 + EVALUATION）。"""

import json
from pathlib import Path

import pytest

from backend.baselines import solve_greedy, solve_sequential
from backend.models import SolveRequest
from backend.validation import validate_solution


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _codes(violations):
    return {v.code for v in violations}


@pytest.mark.parametrize("solver", [solve_greedy, solve_sequential])
def test_c01_all_assigned_valid(solver):
    req = _load_case("c01")
    result = solver(req)
    assert result.validation.valid is True
    assert result.metrics.served_stores == 1
    assert result.metrics.completion_rate == pytest.approx(1.0)
    # 独立复验无违规
    assert validate_solution(req, result) == []


@pytest.mark.parametrize("solver", [solve_greedy, solve_sequential])
def test_c07_partial_valid(solver):
    req = _load_case("c07")
    result = solver(req)
    # 一车 100kg，最多服务一店
    assert result.metrics.served_stores == 1
    assert result.metrics.completion_rate == pytest.approx(0.5)
    assert len(result.unassigned) == 1
    # 部分计划仍应合法（无违规）
    assert validate_solution(req, result) == []


@pytest.mark.parametrize("solver", [solve_greedy, solve_sequential])
def test_c02_box_too_large_unassigned(solver):
    req = _load_case("c02")
    result = solver(req)
    assert result.metrics.served_stores == 0
    assert len(result.unassigned) == 1
    assert result.unassigned[0].reason_code == "BOX_TOO_LARGE"
    assert validate_solution(req, result) == []


@pytest.mark.parametrize("solver", [solve_greedy, solve_sequential])
def test_c03_time_window_unassigned(solver):
    req = _load_case("c03")
    result = solver(req)
    assert result.metrics.served_stores == 0
    assert len(result.unassigned) == 1


@pytest.mark.parametrize("solver", [solve_greedy, solve_sequential])
def test_small_11_valid(solver):
    req = _load_case("small-11")
    result = solver(req)
    # 无论服务多少门店，方案必须无违规（不拆店、不漏箱、指标一致）
    assert validate_solution(req, result) == []


def test_both_baselines_same_cost_basis():
    # 两种基线用相同成本口径：cost = fixed + per_km * distance
    req = _load_case("c01")
    g = solve_greedy(req)
    s = solve_sequential(req)
    assert g.metrics.total_cost == pytest.approx(120.0)
    assert s.metrics.total_cost == pytest.approx(120.0)


def test_deterministic():
    req = _load_case("small-11")
    g1 = solve_greedy(req)
    g2 = solve_greedy(req)
    assert g1.metrics.total_cost == g2.metrics.total_cost
    assert g1.metrics.served_stores == g2.metrics.served_stores
