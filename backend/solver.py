"""B12: 求解入口与 coupled 协同修复。

- solve(request) 按 options.method 路由到 greedy / sequential / coupled；
- coupled 从 sequential 的原始路线候选开始，pack 失败的车进入修复；
- 修复按 A7：把冲突门店移到其他已有车的最佳插入位或未使用车辆，
  重新 pack 受影响车，用目标元组 (未服务门店数, 未服务箱数, 费用, 里程) 字典序
  比较并保留最佳已验证结果；max_iterations/time_limit 终止，超时不丢最佳结果。
"""

from __future__ import annotations

from backend.baselines import solve_greedy, solve_sequential
from backend.budget import Budget
from backend.metrics import compute_metrics
from backend.models import (
    Diagnostic,
    Result,
    Route,
    SolveRequest,
    Unassigned,
    Validation,
)
from backend.network import schedule_route
from backend.packing import pack_route
from backend.repair import relocation_candidates
from backend.routing import build_insertion_routes
from backend.validation import validate_solution


def solve(request: SolveRequest, budget: Budget | None = None) -> Result:
    """求解入口：按 method 路由。"""
    method = request.options.method
    if method == "greedy":
        return solve_greedy(request, budget)
    if method == "sequential":
        return solve_sequential(request, budget)
    if method == "coupled":
        return solve_coupled(request, budget)
    raise ValueError(f"未知 method: {method}")


def _score(result: Result) -> tuple:
    m = result.metrics
    return (m.total_stores - m.served_stores,
            m.total_boxes - m.served_boxes,
            m.total_cost,
            m.total_distance_km)


def _build_route(request: SolveRequest, vehicle_id: str,
                 store_ids: list[str], pack) -> Route:
    vehicle = next(v for v in request.vehicles if v.id == vehicle_id)
    sched = schedule_route(request, vehicle_id, store_ids)
    cost = vehicle.fixed_cost + vehicle.cost_per_km * sched.distance_km
    box_store = {b.id: b.store_id for b in request.boxes}
    box_ids = [b.id for b in request.boxes if b.store_id in set(store_ids)]
    # 按 store_ids 顺序排 box_ids
    order = {sid: i for i, sid in enumerate(store_ids)}
    box_ids.sort(key=lambda bid: order[box_store[bid]])
    return Route(
        vehicle_id=vehicle_id,
        store_ids=store_ids,
        stops=sched.stops,
        return_min=sched.return_min,
        distance_km=sched.distance_km,
        cost=cost,
        box_ids=box_ids,
        placements=pack.placements,
        unload_steps=pack.unload_steps,
    )


def _assemble(request: SolveRequest, routes: list[Route],
              unassigned: list[Unassigned],
              diagnostics: list[Diagnostic]) -> Result:
    metrics = compute_metrics(request, routes, unassigned)
    result = Result(routes=routes, unassigned=unassigned,
                    validation=Validation(valid=True, violations=[]),
                    metrics=metrics, diagnostics=diagnostics)
    violations = validate_solution(request, result)
    result.validation = Validation(valid=len(violations) == 0,
                                   violations=violations)
    return result


def _evaluate(request: SolveRequest, routes_by_vehicle: dict[str, list[str]],
              unassigned_stores: set[str], budget: Budget,
              ) -> tuple[Result, tuple]:
    """从分配组装并评估 Result，返回 (result, score)。pack 失败的车退回。"""
    box_store = {b.id: b.store_id for b in request.boxes}
    routes: list[Route] = []
    remaining = set(unassigned_stores)
    reasons: dict[str, str] = {}
    diagnostics: list[Diagnostic] = []

    for vid in sorted(routes_by_vehicle.keys()):
        store_ids = routes_by_vehicle[vid]
        if not store_ids:
            continue
        pack = pack_route(request, vid, store_ids, budget)
        if pack.success:
            routes.append(_build_route(request, vid, store_ids, pack))
        else:
            reason = pack.reason_code or "SEARCH_EXHAUSTED"
            for sid in store_ids:
                remaining.add(sid)
                reasons[sid] = reason
            diagnostics.append(Diagnostic(
                iteration=0, action="pack_failed",
                reason_code=reason,
                message=f"车辆 {vid} 装箱失败：{pack.message}"))

    unassigned = []
    for sid in sorted(remaining):
        box_ids = [bid for bid, s in box_store.items() if s == sid]
        unassigned.append(Unassigned(store_id=sid, box_ids=box_ids,
                                     reason_code=reasons.get(sid, "SEARCH_EXHAUSTED"),
                                     message="协同修复后仍未找到可行分配"))

    result = _assemble(request, routes, unassigned, diagnostics)
    return result, _score(result)


def _try_relocate(request: SolveRequest, sid: str,
                  routes_by_vehicle: dict[str, list[str]],
                  unassigned_stores: set[str], budget: Budget,
                  ) -> tuple[dict, set] | None:
    """尝试把 sid 移到其他车，返回首个可行 (new_routes, new_unassigned)。"""
    current = [(vid, list(sids)) for vid, sids in routes_by_vehicle.items()
               if sids]
    cands = relocation_candidates(request, sid, current)

    source_vid = next((vid for vid, sids in routes_by_vehicle.items()
                       if sid in sids), None)

    for target_vid, new_target_ids in cands:
        if target_vid == source_vid:
            continue
        new_routes = {vid: list(sids) for vid, sids in routes_by_vehicle.items()}
        if source_vid is not None:
            new_routes[source_vid] = [s for s in new_routes[source_vid] if s != sid]
        new_routes[target_vid] = new_target_ids
        new_routes = {vid: sids for vid, sids in new_routes.items() if sids}

        # 重新评估整个分配（pack 所有车），全部可行则接受
        new_unassigned = set(unassigned_stores) - {sid}
        result, _ = _evaluate(request, new_routes, new_unassigned, budget)
        # 若该店被成功服务（不在 unassigned 中）则接受
        served = {s for r in result.routes for s in r.store_ids}
        if sid in served:
            return new_routes, new_unassigned

    return None


def solve_coupled(request: SolveRequest, budget: Budget | None = None) -> Result:
    if budget is None:
        budget = Budget(request.options.time_limit_ms,
                        request.options.max_iterations)

    # 初始：sequential 原始路线候选
    candidates, unassigned = build_insertion_routes(request, budget)
    routes_by_vehicle: dict[str, list[str]] = {}
    for cand in candidates:
        routes_by_vehicle[cand.vehicle_id] = list(cand.store_ids)
    unassigned_stores = {u.store_id for u in unassigned}

    best_result, best_score = _evaluate(request, routes_by_vehicle,
                                        unassigned_stores, budget)

    # 修复循环
    while not budget.expired():
        budget.tick()
        current_unassigned = {u.store_id for u in best_result.unassigned}
        if not current_unassigned:
            break

        improved = False
        for sid in sorted(current_unassigned):
            moved = _try_relocate(request, sid, routes_by_vehicle,
                                  unassigned_stores, budget)
            if moved is None:
                continue
            new_routes, new_unassigned = moved
            new_result, new_score = _evaluate(request, new_routes,
                                              new_unassigned, budget)
            if new_score < best_score:
                best_result, best_score = new_result, new_score
                routes_by_vehicle = new_routes
                unassigned_stores = new_unassigned
                improved = True
                break

        if not improved:
            break

    return best_result
