"""B05: 两种路线构造策略（greedy 尾插 + sequential 插入）。

遵循 ALGORITHMS.md A4/A5：
- 门店先按最早 window_end、再 ID 排序；车辆按 ID 排序保证可复现；
- 门店作为整体（不拆店），仅做载重/总箱体积/时间窗「必要条件」检查；
- greedy 只做尾部追加，sequential 做全位置插入并加最多 2 轮 2-opt；
- 返回内部 RouteCandidate 与 unassigned 原因，不声称几何可行（packer 在
  B09、独立校验器在 B08），不直接生成 validation.valid。

budget 参数当前仅保留接入点（A8），正式预算由 B11 统一接入。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.models import SolveRequest, Unassigned
from backend.network import EPS, RouteSchedule, schedule_route


@dataclass
class StoreAggregate:
    weight_kg: float
    volume_mm3: float
    box_ids: list[str]


@dataclass
class RouteCandidate:
    vehicle_id: str
    store_ids: list[str]
    box_ids: list[str] = field(default_factory=list)


def _store_aggregates(request: SolveRequest) -> dict[str, StoreAggregate]:
    agg: dict[str, StoreAggregate] = {
        s.id: StoreAggregate(weight_kg=0.0, volume_mm3=0.0, box_ids=[])
        for s in request.stores
    }
    for box in request.boxes:
        a = agg[box.store_id]
        a.weight_kg += box.weight_kg
        a.volume_mm3 += box.length_mm * box.width_mm * box.height_mm
        a.box_ids.append(box.id)
    return agg


def _vehicle(request: SolveRequest, vehicle_id: str):
    return next(v for v in request.vehicles if v.id == vehicle_id)


def _schedule(request: SolveRequest, cand: RouteCandidate) -> RouteSchedule:
    return schedule_route(request, cand.vehicle_id, cand.store_ids)


def _feasible(request: SolveRequest, cand: RouteCandidate,
              agg: dict[str, StoreAggregate]) -> bool:
    """载重、总箱体积、时间窗的必要条件检查（非几何可行）。"""
    vehicle = _vehicle(request, cand.vehicle_id)

    total_weight = sum(agg[sid].weight_kg for sid in cand.store_ids)
    if total_weight - vehicle.max_weight_kg > EPS:
        return False

    total_volume = sum(agg[sid].volume_mm3 for sid in cand.store_ids)
    vehicle_volume = vehicle.length_mm * vehicle.width_mm * vehicle.height_mm
    if total_volume - vehicle_volume > EPS:
        return False

    if _schedule(request, cand).violations:
        return False

    return True


def _candidate_cost(request: SolveRequest, cand: RouteCandidate) -> float:
    vehicle = _vehicle(request, cand.vehicle_id)
    dist = _schedule(request, cand).distance_km
    return vehicle.fixed_cost + vehicle.cost_per_km * dist


def _better(cost: float, cand: RouteCandidate,
            best_cost: float, best: RouteCandidate | None) -> bool:
    if best is None:
        return True
    if cost < best_cost - EPS:
        return True
    if abs(cost - best_cost) <= EPS:
        return cand.vehicle_id < best.vehicle_id
    return False


def _insert_candidate(routes: list[RouteCandidate], cand: RouteCandidate) -> None:
    for i, r in enumerate(routes):
        if r.vehicle_id == cand.vehicle_id:
            routes[i] = cand
            return
    routes.append(cand)


def _unassigned(store_id: str, box_ids: list[str]) -> Unassigned:
    return Unassigned(
        store_id=store_id,
        box_ids=box_ids,
        reason_code="SEARCH_EXHAUSTED",
        message="无可行车辆（载重/总箱体积/时间窗必要条件不满足）",
    )


def build_greedy_routes(request: SolveRequest, budget=None):
    """A4 基线 greedy：门店排序后逐个尾部追加，选增量成本最低。"""
    agg = _store_aggregates(request)
    stores = sorted(request.stores, key=lambda s: (s.window_end_min, s.id))

    routes: list[RouteCandidate] = []
    unassigned: list[Unassigned] = []

    for store in stores:
        if budget is not None and budget.expired():
            unassigned.append(_unassigned(store.id, agg[store.id].box_ids))
            continue

        best: RouteCandidate | None = None
        best_cost = float("inf")
        sid = store.id

        # 已有车尾部追加
        for route in routes:
            cand = RouteCandidate(route.vehicle_id,
                                  route.store_ids + [sid],
                                  route.box_ids + agg[sid].box_ids)
            if _feasible(request, cand, agg):
                cost = _candidate_cost(request, cand)
                if _better(cost, cand, best_cost, best):
                    best, best_cost = cand, cost

        # 未使用车辆作为新车
        used = {r.vehicle_id for r in routes}
        for v in sorted(request.vehicles, key=lambda v: v.id):
            if v.id in used:
                continue
            cand = RouteCandidate(v.id, [sid], list(agg[sid].box_ids))
            if _feasible(request, cand, agg):
                cost = _candidate_cost(request, cand)
                if _better(cost, cand, best_cost, best):
                    best, best_cost = cand, cost

        if best is not None:
            _insert_candidate(routes, best)
        else:
            unassigned.append(_unassigned(sid, agg[sid].box_ids))

    return routes, unassigned


def build_insertion_routes(request: SolveRequest, budget=None):
    """A5 路线 sequential：全位置插入 + 最多 2 轮 2-opt。"""
    agg = _store_aggregates(request)
    stores = sorted(request.stores, key=lambda s: (s.window_end_min, s.id))

    routes: list[RouteCandidate] = []
    unassigned: list[Unassigned] = []

    for store in stores:
        if budget is not None and budget.expired():
            unassigned.append(_unassigned(store.id, agg[store.id].box_ids))
            continue

        best: RouteCandidate | None = None
        best_cost = float("inf")
        sid = store.id

        for v in sorted(request.vehicles, key=lambda v: v.id):
            existing = next((r for r in routes if r.vehicle_id == v.id), None)
            if existing is None:
                positions = [0]
            else:
                positions = range(len(existing.store_ids) + 1)

            for pos in positions:
                if existing is None:
                    new_ids = [sid]
                    new_boxes = list(agg[sid].box_ids)
                else:
                    new_ids = (existing.store_ids[:pos] + [sid]
                               + existing.store_ids[pos:])
                    new_boxes = existing.box_ids + agg[sid].box_ids
                cand = RouteCandidate(v.id, new_ids, new_boxes)
                if _feasible(request, cand, agg):
                    cost = _candidate_cost(request, cand)
                    if _better(cost, cand, best_cost, best):
                        best, best_cost = cand, cost

        if best is not None:
            _insert_candidate(routes, best)
        else:
            unassigned.append(_unassigned(sid, agg[sid].box_ids))

    # 2-opt：最多 2 轮，不接受费用变差
    for _ in range(2):
        improved = False
        for i, route in enumerate(routes):
            better = _two_opt(request, route, agg)
            if better is not None:
                routes[i] = better
                improved = True
        if not improved:
            break

    return routes, unassigned


def _two_opt(request: SolveRequest, route: RouteCandidate,
             agg: dict[str, StoreAggregate]) -> RouteCandidate | None:
    """对单条路线尝试一次 2-opt 反转，返回首个严格降本且可行的路线。"""
    best: RouteCandidate | None = None
    best_dist = _schedule(request, route).distance_km
    n = len(route.store_ids)
    for i in range(n):
        for j in range(i + 1, n):
            new_ids = (route.store_ids[:i]
                       + list(reversed(route.store_ids[i:j + 1]))
                       + route.store_ids[j + 1:])
            cand = RouteCandidate(route.vehicle_id, new_ids, route.box_ids)
            if _feasible(request, cand, agg):
                dist = _schedule(request, cand).distance_km
                if dist < best_dist - EPS:
                    best = cand
                    best_dist = dist
    return best
