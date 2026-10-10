"""B05 路线构造测试。

验证：每个门店恰被分配或未分配、不拆店、载重/总体积/时间窗必要条件通过、
确定性可复现。不依赖被测函数内部逻辑，用独立检查验证必要条件。
"""

import json
from pathlib import Path

import pytest

from backend.models import SolveRequest
from backend.network import schedule_route
from backend.routing import build_greedy_routes, build_insertion_routes


def _load_case(name: str) -> SolveRequest:
    data = json.loads(Path(f"data/cases/{name}.json").read_text(encoding="utf-8"))
    return SolveRequest.model_validate(data)


def _all_store_ids(req):
    return {s.id for s in req.stores}


def _all_box_ids(req):
    return {b.id for b in req.boxes}


def _assigned_store_ids(routes):
    return {sid for r in routes for sid in r.store_ids}


def _unassigned_store_ids(unassigned):
    return {u.store_id for u in unassigned}


def _check_partition(req, routes, unassigned):
    """独立验证：门店/箱件完整分区、无重复、无遗漏。"""
    # 门店分区
    assigned = _assigned_store_ids(routes)
    unassigned_ids = _unassigned_store_ids(unassigned)
    assert assigned.isdisjoint(unassigned_ids), "门店同时出现在已分配和未分配"
    assert assigned | unassigned_ids == _all_store_ids(req), "门店有遗漏或多余"

    # 箱件分区
    assigned_boxes = {bid for r in routes for bid in r.box_ids}
    unassigned_boxes = {bid for u in unassigned for bid in u.box_ids}
    assert assigned_boxes.isdisjoint(unassigned_boxes), "箱件重复出现"
    assert assigned_boxes | unassigned_boxes == _all_box_ids(req), "箱件有遗漏"

    # 不拆店：每条路线内箱件所属门店集合 == 该路线门店集合
    box_store = {b.id: b.store_id for b in req.boxes}
    for r in routes:
        route_box_stores = {box_store[bid] for bid in r.box_ids}
        assert route_box_stores == set(r.store_ids), "门店箱件被拆分"


def _check_necessary_conditions(req, routes):
    """独立验证：载重、总体积、时间窗必要条件。"""
    vehicles = {v.id: v for v in req.vehicles}
    boxes = {b.id: b for b in req.boxes}
    for r in routes:
        v = vehicles[r.vehicle_id]
        weight = sum(boxes[bid].weight_kg for bid in r.box_ids)
        assert weight <= v.max_weight_kg + 1e-6, f"{r.vehicle_id} 超载"
        volume = sum(boxes[bid].length_mm * boxes[bid].width_mm * boxes[bid].height_mm
                     for bid in r.box_ids)
        assert volume <= v.length_mm * v.width_mm * v.height_mm + 1e-6, \
            f"{r.vehicle_id} 总体积超限"
        sched = schedule_route(req, r.vehicle_id, r.store_ids)
        assert sched.violations == [], f"{r.vehicle_id} 时间窗违规"


@pytest.mark.parametrize("builder", [build_greedy_routes, build_insertion_routes])
def test_c01_all_assigned(builder):
    req = _load_case("c01")
    routes, unassigned = builder(req)
    assert len(routes) == 1
    assert unassigned == []
    _check_partition(req, routes, unassigned)
    _check_necessary_conditions(req, routes)


@pytest.mark.parametrize("builder", [build_greedy_routes, build_insertion_routes])
def test_c07_capacity_limit_one_store(builder):
    req = _load_case("c07")
    routes, unassigned = builder(req)
    # 一车 100kg，S1 60kg、S2 60kg，最多服务一店，另一店整体未分配
    assert len(routes) == 1
    assert len(unassigned) == 1
    _check_partition(req, routes, unassigned)
    _check_necessary_conditions(req, routes)


@pytest.mark.parametrize("builder", [build_greedy_routes, build_insertion_routes])
def test_c03_time_window_unassignable(builder):
    req = _load_case("c03")
    routes, unassigned = builder(req)
    # 时间窗无法到达 → 门店未分配
    assert len(routes) == 0
    assert len(unassigned) == 1
    _check_partition(req, routes, unassigned)


@pytest.mark.parametrize("builder", [build_greedy_routes, build_insertion_routes])
def test_suite_partition_and_conditions(builder):
    req = _load_case("small-11")
    routes, unassigned = builder(req)
    _check_partition(req, routes, unassigned)
    _check_necessary_conditions(req, routes)


def test_deterministic_greedy():
    req = _load_case("small-11")
    r1, u1 = build_greedy_routes(req)
    r2, u2 = build_greedy_routes(req)
    assert [(r.vehicle_id, r.store_ids) for r in r1] == \
           [(r.vehicle_id, r.store_ids) for r in r2]
    assert [u.store_id for u in u1] == [u.store_id for u in u2]


def test_deterministic_insertion():
    req = _load_case("small-11")
    r1, u1 = build_insertion_routes(req)
    r2, u2 = build_insertion_routes(req)
    assert [(r.vehicle_id, r.store_ids) for r in r1] == \
           [(r.vehicle_id, r.store_ids) for r in r2]
    assert [u.store_id for u in u1] == [u.store_id for u in u2]


def test_budget_none_accepted():
    req = _load_case("small-11")
    routes, unassigned = build_greedy_routes(req, budget=None)
    routes2, unassigned2 = build_insertion_routes(req, budget=None)
    _check_partition(req, routes, unassigned)
    _check_partition(req, routes2, unassigned2)
