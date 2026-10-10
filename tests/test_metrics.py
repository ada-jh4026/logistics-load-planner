"""B04 指标测试（EVALUATION.md 固定公式 + C01 手算值）。"""

import json
from pathlib import Path

import pytest

from backend.metrics import compute_metrics
from backend.models import Route, SolveRequest, Stop


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _route(vehicle_id, store_ids, box_ids, distance_km, stops=None):
    stops = stops or [
        Stop(store_id=sid, arrival_min=490, service_start_min=500,
             departure_min=505)
        for sid in store_ids
    ]
    return Route(
        vehicle_id=vehicle_id,
        store_ids=store_ids,
        stops=stops,
        return_min=515,
        distance_km=distance_km,
        cost=0,
        box_ids=box_ids,
        placements=[],
        unload_steps=[],
    )


def test_metrics_c01_hand_calc():
    req = _load_case("c01")
    route = _route("V01", ["S01"], ["B01", "B02"], 10.0)
    m = compute_metrics(req, [route], [])

    assert m.total_stores == 1
    assert m.served_stores == 1
    assert m.total_boxes == 2
    assert m.served_boxes == 2
    assert m.completion_rate == pytest.approx(1.0)
    assert m.total_distance_km == pytest.approx(10.0)
    assert m.total_cost == pytest.approx(120.0)  # 100 + 2*10
    # 2 箱各 1000^3=1e9，总 2e9；车 2000*1000*2000=4e9 → 0.5
    assert m.volume_utilization == pytest.approx(0.5)
    # 100+50=150kg / 500kg = 0.3
    assert m.weight_utilization == pytest.approx(0.3)
    assert m.on_time_rate == pytest.approx(1.0)


def test_metrics_empty_plan():
    req = _load_case("c01")
    m = compute_metrics(req, [], [])
    assert m.served_stores == 0
    assert m.served_boxes == 0
    assert m.completion_rate == pytest.approx(0.0)
    assert m.used_vehicles == 0
    assert m.total_distance_km == pytest.approx(0.0)
    assert m.total_cost == pytest.approx(0.0)
    assert m.on_time_rate is None
    assert m.volume_utilization is None
    assert m.weight_utilization is None


def test_metrics_unused_vehicle_excluded_from_denominator():
    # 两辆车，仅用 V01；V02 不得计入利用率分母
    data = json.loads(Path("data/cases/c01.json").read_text(encoding="utf-8"))
    data["vehicles"].append({
        "id": "V02", "length_mm": 3000, "width_mm": 1500, "height_mm": 1500,
        "max_weight_kg": 1000, "fixed_cost": 150, "cost_per_km": 2,
    })
    req = SolveRequest.model_validate(data)
    route = _route("V01", ["S01"], ["B01", "B02"], 10.0)
    m = compute_metrics(req, [route], [])

    # 分母只用 V01（4e9 mm^3, 500kg），不含 V02
    assert m.volume_utilization == pytest.approx(2e9 / 4e9)
    assert m.weight_utilization == pytest.approx(150.0 / 500.0)
    assert m.used_vehicles == 1


def test_metrics_on_time_rate_partial():
    req = _load_case("c01")
    # service_start 600 超过 window_end 600（c01 S01 窗口 500..600）
    # 构造一个迟到 stop：service_start 601
    late_stop = Stop(store_id="S01", arrival_min=601, service_start_min=601,
                     departure_min=606)
    route = Route(
        vehicle_id="V01", store_ids=["S01"], stops=[late_stop],
        return_min=611, distance_km=10, cost=0,
        box_ids=["B01", "B02"], placements=[], unload_steps=[],
    )
    m = compute_metrics(req, [route], [])
    assert m.on_time_rate == pytest.approx(0.0)
