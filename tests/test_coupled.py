"""B12 协同修复测试（ACCEPTANCE C10/C11）。"""

import json
from pathlib import Path

from backend.budget import Budget
from backend.models import SolveRequest
from backend.solver import solve, solve_coupled


def _make_c10_request() -> SolveRequest:
    return SolveRequest.model_validate({
        "schema_version": "0.1",
        "case_id": "c10",
        "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0, "y_km": 0, "departure_min": 480},
        "stores": [{"id": "S01", "x_km": 3, "y_km": 4,
                    "window_start_min": 0, "window_end_min": 1440,
                    "service_min": 5}],
        "vehicles": [
            # 小车 2000x1000x1000，放不下 2500 长
            {"id": "V01", "length_mm": 2000, "width_mm": 1000,
             "height_mm": 1000, "max_weight_kg": 500,
             "fixed_cost": 10, "cost_per_km": 2},
            # 大车 3000x1500x1500，放得下
            {"id": "V02", "length_mm": 3000, "width_mm": 1500,
             "height_mm": 1500, "max_weight_kg": 1000,
             "fixed_cost": 100, "cost_per_km": 2},
        ],
        "boxes": [{"id": "B01", "store_id": "S01", "length_mm": 2500,
                   "width_mm": 500, "height_mm": 500, "weight_kg": 50,
                   "fragile": False, "allow_rotate_xy": True}],
        "options": {"method": "coupled", "seed": 42, "time_limit_ms": 10000,
                    "max_iterations": 200, "speed_kmph": 30},
    })


def test_c10_coupled_relocates_to_large_vehicle():
    req = _make_c10_request()
    result = solve_coupled(req)
    # 该店应被服务（从小车移到大车）
    assert result.metrics.served_stores == 1
    assert result.metrics.served_boxes == 1
    assert result.unassigned == []
    # 用的是大车 V02
    assert result.routes[0].vehicle_id == "V02"


def test_c10_greedy_fails_on_small_vehicle():
    # greedy 优先小车（便宜），pack 失败退回 unassigned，无协同修复
    req = _make_c10_request()
    req.options.method = "greedy"
    result = solve(req)
    assert result.metrics.served_stores == 0
    assert len(result.unassigned) == 1


def test_c10_coupled_via_solve_routing():
    req = _make_c10_request()
    result = solve(req)  # method=coupled
    assert result.metrics.served_stores == 1


def test_coupled_all_boxes_have_destination():
    req = _make_c10_request()
    result = solve_coupled(req)
    # 全部箱有去向（routes 或 unassigned），无遗漏
    from backend.validation import validate_solution
    assert validate_solution(req, result) == []


def test_coupled_small11_valid():
    data = json.loads(Path("data/cases/small-11.json").read_text(encoding="utf-8"))
    req = SolveRequest.model_validate(data)
    result = solve_coupled(req)
    from backend.validation import validate_solution
    assert validate_solution(req, result) == []


def test_coupled_respects_budget():
    req = _make_c10_request()
    state = [0.0]
    b = Budget(time_limit_ms=1000, max_iterations=100000,
               clock=lambda: state[0])
    state[0] = 10.0
    result = solve_coupled(req, budget=b)
    assert result is not None
