"""B08: 组合独立方案校验器。

遵循 ALGORITHMS.md A1：
- 输入为原始 SolveRequest 和候选 Result，重新计算所有派生量，不调用求解器；
- 顺序：ID/分配完整性 → 路线与车辆唯一性 → 时间/载重 → 布局 → 卸货 → 指标；
- 门店分配原子化；每个箱件恰在一个路线或 unassigned；空路线不出现；
- 路线门店集合与箱件所属门店集合完全一致；
- 独立重算 metrics 并与声称值比较（1e-6 容差），不信任 validation.valid。
"""

from __future__ import annotations

from collections import Counter
from math import isclose

from backend.geometry import validate_layout
from backend.metrics import compute_metrics
from backend.models import Metrics, Placement, Result, SolveRequest, UnloadStep, Violation
from backend.network import EPS, schedule_route
from backend.unloading import validate_unload_steps

_FLOAT_METRIC_FIELDS = (
    "completion_rate", "total_distance_km", "total_cost",
    "on_time_rate", "volume_utilization", "weight_utilization",
)
_INT_METRIC_FIELDS = (
    "total_stores", "served_stores", "total_boxes", "served_boxes",
    "used_vehicles", "unload_block_count",
)


def _vehicle(request: SolveRequest, vehicle_id: str):
    return next(v for v in request.vehicles if v.id == vehicle_id)


def _metrics_match(a: Metrics, b: Metrics) -> bool:
    for f in _INT_METRIC_FIELDS:
        if getattr(a, f) != getattr(b, f):
            return False
    for f in _FLOAT_METRIC_FIELDS:
        av, bv = getattr(a, f), getattr(b, f)
        if av is None and bv is None:
            continue
        if av is None or bv is None:
            return False
        if not isclose(av, bv, rel_tol=0, abs_tol=EPS):
            return False
    return True


def validate_vehicle_candidate(request: SolveRequest, vehicle_id: str,
                               store_ids: list[str],
                               placements: list[Placement],
                               unload_steps: list[UnloadStep] | None = None
                               ) -> list[Violation]:
    """单辆车候选校验：几何 + 载重 + 时间窗 +（可选）卸货。

    供 packer（B09）与 repair（B12）复用，不依赖求解器。
    """
    boxes = {b.id: b for b in request.boxes}
    violations: list[Violation] = []
    if vehicle_id not in {v.id for v in request.vehicles}:
        return [Violation(code="VEHICLE_REUSED", vehicle_id=vehicle_id,
                          message="候选引用不存在的车辆")]
    vehicle = _vehicle(request, vehicle_id)
    expected = Counter(b.id for b in request.boxes if b.store_id in store_ids)
    actual = Counter(p.box_id for p in placements)
    if actual != expected:
        violations.append(Violation(code="STEP_MISMATCH", vehicle_id=vehicle_id,
                                    message="布局箱件与路线门店的完整箱件清单不一致"))
    if any(bid not in boxes for bid in actual):
        return violations

    # 几何：边界、碰撞、承托、易碎、旋转
    violations.extend(validate_layout(boxes, placements, vehicle))

    # 载重
    total_weight = sum(boxes[p.box_id].weight_kg for p in placements)
    if total_weight - vehicle.max_weight_kg > EPS:
        violations.append(Violation(
            code="OVERWEIGHT", vehicle_id=vehicle_id,
            message=f"车辆 {vehicle_id} 超载：{total_weight} > {vehicle.max_weight_kg}",
        ))

    # 时间窗（无效门店引用先报违规，避免 schedule_route 抛 KeyError）
    store_id_set = {s.id for s in request.stores}
    invalid_stores = [sid for sid in store_ids if sid not in store_id_set]
    if invalid_stores:
        violations.append(Violation(
            code="STORE_SPLIT", vehicle_id=vehicle_id,
            message=f"路线引用了不存在的门店 {invalid_stores}"))
    else:
        violations.extend(schedule_route(request, vehicle_id, store_ids).violations)

    # 卸货
    if unload_steps is not None:
        violations.extend(
            validate_unload_steps(unload_steps, boxes, placements, store_ids))

    return violations


def validate_solution(request: SolveRequest, result: Result) -> list[Violation]:
    """完整方案校验，返回全部违规（valid=true 也不跳过任何检查）。"""
    violations: list[Violation] = []
    box_store = {b.id: b.store_id for b in request.boxes}
    all_box_ids = set(box_store.keys())
    vehicle_ids = {v.id for v in request.vehicles}
    boxes = {b.id: b for b in request.boxes}

    # Reject unknown references before calling geometry/scheduling/metrics.
    store_ids = {s.id for s in request.stores}
    for route in result.routes:
        if (route.vehicle_id not in vehicle_ids
                or any(s not in store_ids for s in route.store_ids)
                or any(s.store_id not in store_ids for s in route.stops)
                or any(b not in boxes for b in route.box_ids)
                or any(p.box_id not in boxes for p in route.placements)
                or any(s.box_id not in boxes or s.store_id not in store_ids
                       for s in route.unload_steps)):
            violations.append(Violation(code="STORE_SPLIT", vehicle_id=route.vehicle_id,
                                        message="路线含未知车辆、门店或箱件引用"))
    for un in result.unassigned:
        if un.store_id not in store_ids or any(b not in boxes for b in un.box_ids):
            violations.append(Violation(code="STORE_SPLIT", message="未分配清单含未知引用"))
    if violations:
        return violations

    represented_stores = [s for r in result.routes for s in r.store_ids] + [u.store_id for u in result.unassigned]
    if Counter(represented_stores) != Counter(store_ids):
        violations.append(Violation(code="STORE_SPLIT", message="每个门店必须恰好出现于一条路线或未分配清单"))
    for un in result.unassigned:
        if Counter(un.box_ids) != Counter(b.id for b in request.boxes if b.store_id == un.store_id):
            violations.append(Violation(code="STORE_SPLIT", store_id=un.store_id,
                                        message="未分配门店与完整箱件清单不一致"))

    # 1. 分配完整性：每个箱恰在一个路线或 unassigned
    seen: dict[str, str] = {}  # box_id -> 归属
    store_assignment: dict[str, object] = {}

    for ri, route in enumerate(result.routes):
        if route.vehicle_id not in vehicle_ids:
            violations.append(Violation(
                code="VEHICLE_REUSED", vehicle_id=route.vehicle_id,
                message=f"路线引用了不存在的车辆 {route.vehicle_id}"))
        for bid in route.box_ids:
            if bid in seen:
                violations.append(Violation(
                    code="BOX_DUPLICATE", box_ids=[bid],
                    message=f"箱 {bid} 重复出现"))
            seen[bid] = f"route:{ri}"
            sid = box_store.get(bid)
            if sid is not None:
                if sid in store_assignment and store_assignment[sid] != ri:
                    violations.append(Violation(
                        code="STORE_SPLIT", store_id=sid,
                        box_ids=[bid], message=f"门店 {sid} 被拆分"))
                store_assignment[sid] = ri

    for ui, un in enumerate(result.unassigned):
        for bid in un.box_ids:
            if bid in seen:
                violations.append(Violation(
                    code="BOX_DUPLICATE", box_ids=[bid],
                    message=f"箱 {bid} 重复出现"))
            seen[bid] = f"unassigned:{ui}"
            sid = box_store.get(bid)
            if sid is not None:
                key = ("unassigned", un.store_id)
                if sid in store_assignment and store_assignment[sid] != key:
                    violations.append(Violation(
                        code="STORE_SPLIT", store_id=sid,
                        box_ids=[bid], message=f"门店 {sid} 被拆分"))
                store_assignment[sid] = key

    missing = all_box_ids - set(seen.keys())
    if missing:
        violations.append(Violation(
            code="BOX_MISSING", box_ids=sorted(missing),
            message=f"箱件遗漏：{sorted(missing)}"))

    # 2. 车辆唯一性 + 空路线
    used = [r.vehicle_id for r in result.routes]
    if len(used) != len(set(used)):
        violations.append(Violation(
            code="VEHICLE_REUSED",
            message=f"车辆重复使用：{sorted(used)}"))
    for r in result.routes:
        expected = Counter(b.id for b in request.boxes if b.store_id in r.store_ids)
        if (Counter(r.box_ids) != expected
                or Counter(p.box_id for p in r.placements) != expected
                or Counter(s.box_id for s in r.unload_steps) != expected):
            violations.append(Violation(code="STEP_MISMATCH", vehicle_id=r.vehicle_id,
                                        message="路线、布局、卸货箱件必须与门店完整清单逐件一致且无重复"))
        if not r.store_ids or not r.box_ids:
            violations.append(Violation(
                code="STEP_MISMATCH", vehicle_id=r.vehicle_id,
                message=f"车辆 {r.vehicle_id} 出现空路线"))
        route_box_stores = {box_store[bid] for bid in r.box_ids}
        if route_box_stores != set(r.store_ids):
            violations.append(Violation(
                code="STORE_SPLIT", vehicle_id=r.vehicle_id,
                message=f"车辆 {r.vehicle_id} 路线门店与箱件门店不一致"))

    # 3-5. 每条路线：时间/载重/布局/卸货
    canonical_routes = []
    for r in result.routes:
        vehicle = _vehicle(request, r.vehicle_id)
        cand_violations = validate_vehicle_candidate(
            request, r.vehicle_id, r.store_ids, r.placements, r.unload_steps)
        violations.extend(cand_violations)

        schedule = schedule_route(request, r.vehicle_id, r.store_ids)
        cost = vehicle.fixed_cost + vehicle.cost_per_km * schedule.distance_km
        pairs = [(r.distance_km, schedule.distance_km), (r.cost, cost),
                 (r.return_min, schedule.return_min)]
        stops_match = len(r.stops) == len(schedule.stops)
        for actual, expected in zip(r.stops, schedule.stops):
            stops_match = stops_match and actual.store_id == expected.store_id
            pairs.extend((getattr(actual, field), getattr(expected, field)) for field in
                         ("arrival_min", "service_start_min", "departure_min"))
        if not stops_match or any(not isclose(a, b, rel_tol=0, abs_tol=EPS) for a, b in pairs):
            violations.append(Violation(code="METRIC_MISMATCH", vehicle_id=r.vehicle_id,
                                        message="路线里程、费用、到站顺序或时刻表与原始输入重算不符"))
        canonical_routes.append(r.model_copy(update={
            "distance_km": schedule.distance_km, "cost": cost,
            "return_min": schedule.return_min, "stops": schedule.stops}))

    # 6. 指标：独立重算并比较
    # Structural errors can make derived Metrics invalid (e.g. duplicate stores).
    if violations:
        return violations
    recomputed = compute_metrics(request, canonical_routes, result.unassigned)
    if not _metrics_match(recomputed, result.metrics):
        violations.append(Violation(
            code="METRIC_MISMATCH",
            message=(
                f"指标不符：重算 total_cost={recomputed.total_cost}、"
                f"volume_utilization={recomputed.volume_utilization}，"
                f"声称 total_cost={result.metrics.total_cost}、"
                f"volume_utilization={result.metrics.volume_utilization}"
            ),
        ))

    return violations
