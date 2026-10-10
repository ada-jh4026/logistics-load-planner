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
    RepairEvent,
    RepairTrace,
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

MAX_REJECT_EVENTS = 64
MAX_RELOCATION_CANDIDATES = 8


class _TraceRecorder:
    """Bound rejected-event storage without losing counts or accepted steps."""

    def __init__(self):
        self.events: list[RepairEvent] = []
        self.attempted_count = 0
        self.accepted_count = 0
        self.omitted_count = 0
        self._next_id = 1
        self._stored_rejections = 0

    def add(self, *, iteration: int, action: str, outcome: str,
            store_ids: list[str], box_ids: list[str],
            source_vehicle_id: str | None, target_vehicle_id: str | None,
            reason_code: str | None, message: str,
            before: Result | None = None, after: Result | None = None) -> None:
        event_id = self._next_id
        self._next_id += 1
        if outcome == "accepted":
            self.accepted_count += 1
        if outcome == "rejected":
            if self._stored_rejections >= MAX_REJECT_EVENTS:
                self.omitted_count += 1
                return
            self._stored_rejections += 1
        self.events.append(RepairEvent(
            event_id=event_id, iteration=iteration, action=action,
            outcome=outcome, store_ids=list(store_ids), box_ids=list(box_ids),
            source_vehicle_id=source_vehicle_id,
            target_vehicle_id=target_vehicle_id, reason_code=reason_code,
            message=message,
            metrics_before=before.metrics.model_copy(deep=True) if before else None,
            metrics_after=after.metrics.model_copy(deep=True) if after else None,
            routes_before=[r.model_copy(deep=True) for r in before.routes] if before else None,
            routes_after=[r.model_copy(deep=True) for r in after.routes] if after else None,
        ))


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
                  trace: _TraceRecorder,
                  ) -> tuple[dict, set, str | None, str] | None:
    """尝试把 sid 移到其他车，返回首个可行 (new_routes, new_unassigned)。

    仅重新 pack 受影响的车（源车 + 目标车），避免全量 pack 耗尽预算。
    """
    current = [(vid, list(sids)) for vid, sids in routes_by_vehicle.items()
               if sids]
    cands = relocation_candidates(request, sid, current)

    source_vid = next((vid for vid, sids in routes_by_vehicle.items()
                       if sid in sids), None)

    for target_vid, new_target_ids in cands:
        if target_vid == source_vid:
            continue
        if budget.expired():
            break
        trace.attempted_count += 1
        new_routes = {vid: list(sids) for vid, sids in routes_by_vehicle.items()}
        if source_vid is not None:
            new_routes[source_vid] = [s for s in new_routes[source_vid] if s != sid]
        new_routes[target_vid] = new_target_ids
        new_routes = {vid: sids for vid, sids in new_routes.items() if sids}

        # 仅重新 pack 受影响的车（源车移除后、目标车加入后）
        ok = True
        failed_reason = None
        failed_message = None
        for vid in sorted(v for v in {source_vid, target_vid} if v is not None):
            if vid is not None and vid in new_routes:
                pack = pack_route(request, vid, new_routes[vid], budget)
                if not pack.success:
                    ok = False
                    failed_reason = pack.reason_code or "SEARCH_EXHAUSTED"
                    failed_message = f"车辆 {vid} 装箱失败：{pack.message}"
                    break
        if ok:
            return new_routes, set(unassigned_stores) - {sid}, source_vid, target_vid
        trace.add(
            iteration=budget.iterations, action="relocate", outcome="rejected",
            store_ids=[sid],
            box_ids=[b.id for b in request.boxes if b.store_id == sid],
            source_vehicle_id=source_vid, target_vehicle_id=target_vid,
            reason_code=failed_reason, message=failed_message or "装载检查未通过",
        )

    return None


def _ranked_relocations(request: SolveRequest, sid: str,
                        routes_by_vehicle: dict[str, list[str]]):
    """Rank structural moves by estimated route-cost delta, then stable IDs."""
    current = [(vid, list(sids)) for vid, sids in routes_by_vehicle.items() if sids]
    source_vid = next((vid for vid, sids in current if sid in sids), None)
    vehicles = {v.id: v for v in request.vehicles}

    def route_cost(vid: str, ids: list[str]) -> float:
        if not ids:
            return 0.0
        v = vehicles[vid]
        return v.fixed_cost + v.cost_per_km * schedule_route(request, vid, ids).distance_km

    old_source = routes_by_vehicle.get(source_vid, []) if source_vid else []
    source_after = [s for s in old_source if s != sid]
    source_delta = (route_cost(source_vid, source_after) - route_cost(source_vid, old_source)
                    if source_vid else 0.0)
    ranked = []
    for target_vid, new_ids in relocation_candidates(request, sid, current):
        if target_vid == source_vid:
            continue
        old_target = routes_by_vehicle.get(target_vid, [])
        delta = source_delta + route_cost(target_vid, new_ids) - route_cost(target_vid, old_target)
        ranked.append((delta, target_vid, tuple(new_ids), source_vid))
    return sorted(ranked)


def _best_relocate(request: SolveRequest, sid: str,
                   routes_by_vehicle: dict[str, list[str]],
                   unassigned_stores: set[str], budget: Budget,
                   trace: _TraceRecorder, best_score: tuple):
    """Compare at most eight independently validated moves; preserve best snapshot."""
    winner = None
    for _, target_vid, target_ids, source_vid in _ranked_relocations(
            request, sid, routes_by_vehicle)[:MAX_RELOCATION_CANDIDATES]:
        if budget.expired():
            break
        budget.tick()
        trace.attempted_count += 1
        routes = {vid: list(ids) for vid, ids in routes_by_vehicle.items()}
        if source_vid:
            routes[source_vid] = [s for s in routes[source_vid] if s != sid]
        routes[target_vid] = list(target_ids)
        routes = {vid: ids for vid, ids in routes.items() if ids}
        # _evaluate packs every route and runs the independent solution validator.
        result, score = _evaluate(request, routes, unassigned_stores - {sid}, budget)
        if result.validation.valid and score < best_score:
            tie_key = (score, target_vid, target_ids)
            if winner is None or tie_key < winner[0]:
                winner = (tie_key, routes, unassigned_stores - {sid},
                          source_vid, target_vid, result, score)
            continue
        reason = (result.validation.violations[0].code
                  if not result.validation.valid else "NO_IMPROVEMENT")
        trace.add(
            iteration=budget.iterations, action="relocate", outcome="rejected",
            store_ids=[sid], box_ids=[b.id for b in request.boxes if b.store_id == sid],
            source_vehicle_id=source_vid, target_vehicle_id=target_vid,
            reason_code=reason,
            message=(f"独立校验未通过：{reason}" if not result.validation.valid
                     else "已验证方案的目标分数未改善"),
        )
    return winner


def solve_coupled(request: SolveRequest, budget: Budget | None = None,
                  *, selection: str = "best") -> Result:
    if selection not in {"best", "first"}:
        raise ValueError(f"unknown relocation selection: {selection}")
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
    trace = _TraceRecorder()
    initial_result = best_result.model_copy(deep=True)
    served_vehicles = {r.vehicle_id for r in best_result.routes}
    failed_vehicles = [vid for vid, sids in sorted(routes_by_vehicle.items())
                       if sids and vid not in served_vehicles]
    for vid, diagnostic in zip(failed_vehicles, best_result.diagnostics):
        store_ids = routes_by_vehicle[vid]
        trace.add(
            iteration=budget.iterations, action="pack_failed", outcome="detected",
            store_ids=store_ids,
            box_ids=[b.id for b in request.boxes if b.store_id in store_ids],
            source_vehicle_id=vid, target_vehicle_id=None,
            reason_code=diagnostic.reason_code, message=diagnostic.message,
        )

    # 修复循环
    while not budget.expired():
        budget.tick()
        current_unassigned = {u.store_id for u in best_result.unassigned}
        if not current_unassigned:
            break

        improved = False
        for sid in sorted(current_unassigned):
            if selection == "best":
                chosen = _best_relocate(request, sid, routes_by_vehicle,
                                        unassigned_stores, budget, trace, best_score)
                if chosen is None:
                    continue
                _, new_routes, new_unassigned, source_vid, target_vid, new_result, new_score = chosen
            else:
                moved = _try_relocate(request, sid, routes_by_vehicle,
                                      unassigned_stores, budget, trace)
                if moved is None:
                    continue
                new_routes, new_unassigned, source_vid, target_vid = moved
                new_result, new_score = _evaluate(request, new_routes,
                                                  new_unassigned, budget)
            if new_result.validation.valid and new_score < best_score:
                trace.add(
                    iteration=budget.iterations, action="relocate", outcome="accepted",
                    store_ids=[sid],
                    box_ids=[b.id for b in request.boxes if b.store_id == sid],
                    source_vehicle_id=source_vid, target_vehicle_id=target_vid,
                    reason_code=None, message=f"门店 {sid} 调整至车辆 {target_vid} 并通过独立校验",
                    before=best_result, after=new_result,
                )
                best_result, best_score = new_result, new_score
                routes_by_vehicle = new_routes
                unassigned_stores = new_unassigned
                improved = True
                break
            reason = (new_result.validation.violations[0].code
                      if not new_result.validation.valid else "NO_IMPROVEMENT")
            trace.add(
                iteration=budget.iterations, action="relocate", outcome="rejected",
                store_ids=[sid],
                box_ids=[b.id for b in request.boxes if b.store_id == sid],
                source_vehicle_id=source_vid, target_vehicle_id=target_vid,
                reason_code=reason,
                message=(f"独立校验未通过：{reason}" if not new_result.validation.valid
                         else "已验证方案的目标分数未改善"),
            )

        if not improved:
            break

    if best_result.metrics.served_stores == best_result.metrics.total_stores:
        status = "repaired" if trace.accepted_count else "not_needed"
    elif budget.expired():
        status = "budget_exhausted"
    elif trace.accepted_count:
        status = "partially_repaired"
    else:
        status = "unresolved"
    best_result.repair_trace = RepairTrace(
        status=status,
        initial_metrics=initial_result.metrics.model_copy(deep=True),
        final_metrics=best_result.metrics.model_copy(deep=True),
        initial_routes=[r.model_copy(deep=True) for r in initial_result.routes],
        attempted_count=trace.attempted_count,
        accepted_count=trace.accepted_count,
        events=trace.events,
        truncated=trace.omitted_count > 0,
        omitted_count=trace.omitted_count,
    )
    return best_result
