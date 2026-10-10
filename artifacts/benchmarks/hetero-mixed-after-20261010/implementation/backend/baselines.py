"""B10: 连通两种完整基线（greedy / sequential）。

把 B05 的路线构造与 B09 的 packer 组合成完整基线：
- greedy 尾插 / sequential 插入 → 路线候选；
- 每条路线用同一 packer 装箱，失败整车退回 unassigned（门店原子，不拆店）；
- 组装 Result 并调用 validate_solution，不通过则不作为有效方案；
- 保存诊断与内部候选（供 B12 coupled 复用）。

失败路线不计入 metrics，但 completion_rate 同步降低，不产生「少送货的虚假降本」。
"""

from __future__ import annotations

from backend.metrics import compute_metrics
from backend.models import (
    Diagnostic,
    Result,
    Route,
    SolveRequest,
    Unassigned,
    Validation,
)
from backend.budget import Budget
from backend.network import schedule_route
from backend.packing import pack_route
from backend.routing import build_greedy_routes, build_insertion_routes
from backend.validation import validate_solution


def _build_route(request: SolveRequest, cand, pack) -> Route:
    vehicle = next(v for v in request.vehicles if v.id == cand.vehicle_id)
    sched = schedule_route(request, cand.vehicle_id, cand.store_ids)
    cost = vehicle.fixed_cost + vehicle.cost_per_km * sched.distance_km
    return Route(
        vehicle_id=cand.vehicle_id,
        store_ids=cand.store_ids,
        stops=sched.stops,
        return_min=sched.return_min,
        distance_km=sched.distance_km,
        cost=cost,
        box_ids=cand.box_ids,
        placements=pack.placements,
        unload_steps=pack.unload_steps,
    )


def _assemble_result(request: SolveRequest, routes: list[Route],
                     unassigned: list[Unassigned],
                     diagnostics: list[Diagnostic]) -> Result:
    metrics = compute_metrics(request, routes, unassigned)
    result = Result(
        routes=routes,
        unassigned=unassigned,
        validation=Validation(valid=True, violations=[]),
        metrics=metrics,
        diagnostics=diagnostics,
    )
    violations = validate_solution(request, result)
    result.validation = Validation(valid=len(violations) == 0,
                                   violations=violations)
    return result


def _solve(request: SolveRequest, build_routes, budget=None) -> Result:
    if budget is None:
        budget = Budget(request.options.time_limit_ms,
                        request.options.max_iterations)
    candidates, unassigned = build_routes(request, budget)
    unassigned = list(unassigned)
    box_store = {b.id: b.store_id for b in request.boxes}

    routes: list[Route] = []
    diagnostics: list[Diagnostic] = []

    for cand in candidates:
        pack = pack_route(request, cand.vehicle_id, cand.store_ids, budget)
        if not pack.success:
            reason = pack.reason_code or "SEARCH_EXHAUSTED"
            for sid in cand.store_ids:
                store_box_ids = [bid for bid in cand.box_ids
                                 if box_store[bid] == sid]
                unassigned.append(Unassigned(
                    store_id=sid, box_ids=store_box_ids,
                    reason_code=reason, message=pack.message or ""))
            diagnostics.append(Diagnostic(
                iteration=0, action="pack_failed", reason_code=reason,
                message=f"车辆 {cand.vehicle_id} 装箱失败：{pack.message}"))
        else:
            routes.append(_build_route(request, cand, pack))

    # 稳定排序保证可复现
    unassigned.sort(key=lambda u: u.store_id)
    diagnostics.sort(key=lambda d: (d.reason_code, d.message))

    return _assemble_result(request, routes, unassigned, diagnostics)


def solve_greedy(request: SolveRequest, budget=None) -> Result:
    """A4 简单贪心基线：greedy 路线 + 统一 packer，无反馈修复。"""
    return _solve(request, build_greedy_routes, budget)


def solve_sequential(request: SolveRequest, budget=None) -> Result:
    """A5 sequential 基线：全位置插入 + 2-opt + 统一 packer，无反馈修复。"""
    return _solve(request, build_insertion_routes, budget)
