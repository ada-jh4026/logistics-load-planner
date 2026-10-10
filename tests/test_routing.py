"""B04 路由与时效测试（ACCEPTANCE C01/C03 手算断言）。"""

import json
from pathlib import Path

import pytest

from backend.models import SolveRequest
from backend.network import EPS, distance_km, schedule_route, travel_min


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _make_request(window_end: float) -> SolveRequest:
    return SolveRequest.model_validate({
        "schema_version": "0.1",
        "case_id": "test-boundary",
        "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0, "y_km": 0, "departure_min": 480},
        "stores": [{"id": "S01", "x_km": 30, "y_km": 0,
                    "window_start_min": 490, "window_end_min": window_end,
                    "service_min": 5}],
        "vehicles": [{"id": "V01", "length_mm": 2000, "width_mm": 1000,
                      "height_mm": 2000, "max_weight_kg": 500,
                      "fixed_cost": 100, "cost_per_km": 2}],
        "boxes": [{"id": "B01", "store_id": "S01", "length_mm": 500,
                   "width_mm": 500, "height_mm": 500, "weight_kg": 50,
                   "fragile": False, "allow_rotate_xy": True}],
        "options": {"method": "coupled", "seed": 42, "time_limit_ms": 10000,
                    "max_iterations": 200, "speed_kmph": 30},
    })


def test_distance_km():
    assert distance_km(0, 0, 3, 4) == pytest.approx(5.0)
    assert distance_km(0, 0, 0, 0) == pytest.approx(0.0)


def test_travel_min():
    assert travel_min(5.0, 30.0) == pytest.approx(10.0)


def test_schedule_c01_hand_calc():
    req = _load_case("c01")
    sched = schedule_route(req, "V01", ["S01"])

    # 距离 (0,0)->(3,4)=5km，往返 10km
    assert sched.distance_km == pytest.approx(10.0)

    stop = sched.stops[0]
    assert stop.arrival_min == pytest.approx(490.0)      # 480 + 10min
    assert stop.service_start_min == pytest.approx(500.0)  # 等待到窗口 500
    assert stop.departure_min == pytest.approx(505.0)    # 500 + 5min 服务
    assert sched.return_min == pytest.approx(515.0)      # 505 + 10min 回仓
    assert sched.violations == []


def test_schedule_c03_time_window_violation():
    req = _load_case("c03")
    sched = schedule_route(req, "V01", ["S01"])

    # 30km/30kmph*60 = 60min，480 + 60 = 540，窗口 490..500
    assert sched.stops[0].arrival_min == pytest.approx(540.0)
    assert len(sched.violations) == 1
    assert sched.violations[0].code == "TIME_WINDOW"
    assert sched.violations[0].store_id == "S01"


def test_time_window_boundary_exact_ok():
    # 窗口结束 540 时准时
    req = _make_request(540.0)
    sched = schedule_route(req, "V01", ["S01"])
    assert sched.stops[0].service_start_min == pytest.approx(540.0)
    assert sched.violations == []


def test_time_window_boundary_just_before_rejected():
    # 窗口结束 539.999 时不合格（容差 1e-6 内仍判定晚到）
    req = _make_request(539.999)
    sched = schedule_route(req, "V01", ["S01"])
    assert sched.stops[0].service_start_min == pytest.approx(540.0)
    assert len(sched.violations) == 1


def test_waiting_is_accounted():
    # 门店离仓库近、窗口靠后：arrival 早于 window_start 时应等待
    req = _make_request(1000.0)
    sched = schedule_route(req, "V01", ["S01"])
    stop = sched.stops[0]
    # arrival=540，窗口起点 490 已过，但终点 1000 很晚，service_start=540
    assert stop.service_start_min == pytest.approx(540.0)
