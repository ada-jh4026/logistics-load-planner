"""Experiment-only sequential + simple failed-store reinsertion baseline.

Public SolveRequest.options.method remains the existing three-value enum.
Already served stores retain their relative order and vehicle assignment.
"""

from __future__ import annotations

from backend.baselines import solve_sequential
from backend.budget import Budget
from backend.models import Result, SolveRequest
from backend.packing import pack_route
from backend.routing import RouteCandidate, _feasible, _store_aggregates
from backend.solver import _assemble, _build_route
from backend.network import schedule_route


def solve_sequential_reinsert(request: SolveRequest,
                              budget: Budget | None = None) -> Result:
    if budget is None:
        budget = Budget(request.options.time_limit_ms,
                        request.options.max_iterations)
    current = solve_sequential(request, budget)
    if not current.validation.valid:
        return current

    aggregates = _store_aggregates(request)
    stores = {store.id: store for store in request.stores}
    vehicles = {vehicle.id: vehicle for vehicle in request.vehicles}
    pending = sorted((entry.store_id for entry in current.unassigned),
                     key=lambda sid: (stores[sid].window_end_min, sid))

    for sid in pending:
        if budget.expired():
            break
        options = []
        active = {route.vehicle_id: route for route in current.routes}
        for vid in sorted(vehicles):
            old = active.get(vid)
            old_ids = old.store_ids if old else []
            for pos in range(len(old_ids) + 1):
                new_ids = old_ids[:pos] + [sid] + old_ids[pos:]
                candidate = RouteCandidate(vid, new_ids)
                if not _feasible(request, candidate, aggregates):
                    continue
                vehicle = vehicles[vid]
                sched = schedule_route(request, vid, new_ids)
                cost = vehicle.fixed_cost + vehicle.cost_per_km * sched.distance_km
                delta = cost - (old.cost if old else 0)
                options.append((delta, vid, pos, new_ids))

        for _, vid, _, new_ids in sorted(options):
            if budget.expired():
                break
            budget.tick()
            packed = pack_route(request, vid, new_ids, budget)
            if not packed.success:
                continue
            route = _build_route(request, vid, new_ids, packed)
            routes = [r for r in current.routes if r.vehicle_id != vid] + [route]
            routes.sort(key=lambda r: r.vehicle_id)
            unassigned = [entry for entry in current.unassigned
                          if entry.store_id != sid]
            trial = _assemble(request, routes, unassigned,
                              list(current.diagnostics))
            if trial.validation.valid and (
                    trial.metrics.served_stores == current.metrics.served_stores + 1):
                current = trial
                break

    return current
