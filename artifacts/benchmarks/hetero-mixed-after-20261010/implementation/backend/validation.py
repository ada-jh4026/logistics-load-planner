"""B08: 组合独立方案校验器。

遵循 ALGORITHMS.md A1：
- 输入为原始 SolveRequest 和候选 Result，重新计算所有派生量，不调用求解器；
- 顺序：ID/分配完整性 → 路线与车辆唯一性 → 时间/载重 → 布局 → 卸货 → 指标；
- 门店分配原子化；每个箱件恰在一个路线或 unassigned；空路线不出现；
- 路线门店集合与箱件所属门店集合完全一致；
- 独立重算 metrics 并与声称值比较（1e-6 容差），不信任 validation.valid。
"""

from __future__ import annotations

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
        if abs(av - bv) > EPS:
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
    vehicle = _vehicle(request, vehicle_id)
    boxes = {b.id: b for b in request.boxes}
    violations: list[Violation] = []

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
    for r in result.routes:
        vehicle = _vehicle(request, r.vehicle_id)
        cand_violations = validate_vehicle_candidate(
            request, r.vehicle_id, r.store_ids, r.placements, r.unload_steps)
        violations.extend(cand_violations)

    # 6. 指标：独立重算并比较
    recomputed = compute_metrics(request, result.routes, result.unassigned)
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
