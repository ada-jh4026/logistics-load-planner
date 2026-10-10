"""仓库外探针 2：把「增量费用」版本注入完整求解管线（pack + 校验 + coupled 修复），看最终可执行结果。不改 backend/。"""
import json, sys, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from backend.models import SolveRequest
from backend import routing as R
from backend import solver as S
from backend import baselines as B

def _marginal_builder(all_positions: bool):
    def build(request, budget=None):
        agg = R._store_aggregates(request)
        stores = sorted(request.stores, key=lambda s: (s.window_end_min, s.id))
        routes, unassigned = [], []
        for store in stores:
            if budget is not None and budget.expired():
                unassigned.append(R._unassigned(store.id, agg[store.id].box_ids)); continue
            if budget is not None: budget.tick()
            sid = store.id; best, best_cost = None, float("inf")
            for v in sorted(request.vehicles, key=lambda v: v.id):
                existing = next((r for r in routes if r.vehicle_id == v.id), None)
                base = R._candidate_cost(request, existing) if existing else 0.0
                if existing is None: positions = [0]
                elif all_positions: positions = range(len(existing.store_ids) + 1)
                else: positions = [len(existing.store_ids)]
                for pos in positions:
                    if existing is None: new_ids, new_boxes = [sid], list(agg[sid].box_ids)
                    else: new_ids = existing.store_ids[:pos] + [sid] + existing.store_ids[pos:]; new_boxes = existing.box_ids + agg[sid].box_ids
                    cand = R.RouteCandidate(v.id, new_ids, new_boxes)
                    if R._feasible(request, cand, agg):
                        marginal = R._candidate_cost(request, cand) - base
                        if R._better(marginal, cand, best_cost, best): best, best_cost = cand, marginal
            if best is not None: R._insert_candidate(routes, best)
            else: unassigned.append(R._unassigned(sid, agg[sid].box_ids))
        if all_positions:
            for _ in range(2):
                improved = False
                for i, route in enumerate(routes):
                    better = R._two_opt(request, route, agg)
                    if better is not None: routes[i] = better; improved = True
                if not improved: break
        return routes, unassigned
    return build

def run(case, method):
    r = json.load(open(f"data/cases/{case}.json", encoding="utf-8")); r["options"]["method"] = method
    t0 = time.perf_counter(); res = S.solve(SolveRequest(**r)); ms = (time.perf_counter() - t0) * 1000
    m = res.metrics
    return f"{m.served_stores:2d}/{m.total_stores:2d} {m.used_vehicles:2d}车 {m.total_cost:7.1f}元 vol {m.volume_utilization or 0:.2f} valid {res.validation.valid} diag {len(res.diagnostics)} {ms:5.0f}ms"

cases = ("small-11", "small-22", "small-33", "standard-11", "standard-22", "standard-33", "stress-44")
print("== 现状（仓库代码） ==")
for c in cases:
    print(f"{c:12s} greedy {run(c,'greedy')} | sequential {run(c,'sequential')} | coupled {run(c,'coupled')}")

# 注入：所有引用点都替换
orig_g, orig_i = R.build_greedy_routes, R.build_insertion_routes
for mod in (R, B, S):
    if hasattr(mod, "build_greedy_routes"): mod.build_greedy_routes = _marginal_builder(False)
    if hasattr(mod, "build_insertion_routes"): mod.build_insertion_routes = _marginal_builder(True)
print("\n== 注入增量费用比较后（含 pack + 独立校验 + coupled 修复） ==")
for c in cases:
    print(f"{c:12s} greedy {run(c,'greedy')} | sequential {run(c,'sequential')} | coupled {run(c,'coupled')}")
