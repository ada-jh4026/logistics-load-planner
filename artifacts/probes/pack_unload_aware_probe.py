"""探针：构造式「卸货感知」配载。不改 backend/，运行时替换 packing 的候选排序与可放检查：
1) 放置时就拒绝会被「更晚到站」箱件挡住抽出路径的位置（把事后卸货模拟变成事前约束）；
2) 非末站箱件优先靠后门（x 小），末站箱件优先靠车头；
3) 承托允许由若干顶面同高的非易碎箱共同完整承托（矩形并集覆盖）。
在异构纸箱案例上对比修复前后，并跑原测试套件确认不破坏。"""
import json, sys, random, copy, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from backend.models import SolveRequest, Placement
from backend import packing as P
from backend import geometry as G
from backend.unloading import _blocks_movement
from backend.geometry import oriented_size, inside_vehicle, intersects

# ---------- 多箱共同承托（矩形并集完整覆盖） ----------
def _covered_by_union(x0, y0, x1, y1, rects) -> bool:
    """rects 是否完整覆盖 [x0,x1)×[y0,y1)。按 x/y 切分网格逐格检查。"""
    xs = sorted({x0, x1} | {r[0] for r in rects} | {r[2] for r in rects})
    ys = sorted({y0, y1} | {r[1] for r in rects} | {r[3] for r in rects})
    xs = [v for v in xs if x0 <= v <= x1]; ys = [v for v in ys if y0 <= v <= y1]
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i+1]) / 2, (ys[j] + ys[j+1]) / 2
            if not any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects):
                return False
    return True

def find_support_multi(box, x, y, z, rot, boxes, placements):
    """返回承托箱列表（顶面恰为 z、非易碎、并集完整覆盖底面）；否则 None。单箱完整覆盖是其特例。"""
    bl, bw, _ = oriented_size(box, rot)
    tops = []
    for other in placements:
        if other.box_id == box.id: continue
        ob = boxes[other.box_id]; ol, ow, oh = oriented_size(ob, other.rotation_xy)
        if other.z_mm + oh == z and not ob.fragile:
            ix0, iy0 = max(x, other.x_mm), max(y, other.y_mm)
            ix1, iy1 = min(x + bl, other.x_mm + ol), min(y + bw, other.y_mm + ow)
            if ix1 > ix0 and iy1 > iy0:
                tops.append((ix0, iy0, ix1, iy1, other))
    if not tops: return None
    return [t[4] for t in tops] if _covered_by_union(x, y, x + bl, y + bw, [t[:4] for t in tops]) else None

# ---------- 卸货感知的可放检查 ----------
def make_can_place(store_order: dict[str, int], boxes: dict, multi_support: bool):
    def can_place(box, rot, x, y, z, placements, boxes_, vehicle):
        if not inside_vehicle(box, x, y, z, rot, vehicle): return False
        for p in placements:
            if intersects(box, x, y, z, rot, boxes_[p.box_id], p.x_mm, p.y_mm, p.z_mm, p.rotation_xy): return False
        if z != 0:
            if multi_support:
                sup = find_support_multi(box, x, y, z, rot, boxes_, placements)
                if sup is None: return False
                # 不得压在更早到站（会先卸）的箱上
                if any(store_order[boxes_[s.box_id].store_id] < store_order[box.store_id] for s in sup): return False
            else:
                sup = G.find_support(box, x, y, z, rot, boxes_, placements)
                if sup is None or boxes_[sup.box_id].fragile: return False
                if store_order[boxes_[sup.box_id].store_id] < store_order[box.store_id]: return False
        # 抽出路径（x 向后门）不得被「更晚到站」的箱挡住
        for p in placements:
            ob = boxes_[p.box_id]
            if store_order[ob.store_id] > store_order[box.store_id] and _blocks_movement(box, x, y, z, rot, ob, p.x_mm, p.y_mm, p.z_mm, p.rotation_xy):
                return False
        return True
    return can_place

def make_candidates(store_order: dict[str, int], last_stop: int):
    orig = P._candidate_positions
    def cands(box, rot, placements, boxes, vehicle):
        c = orig(box, rot, placements, boxes, vehicle)
        if store_order[box.store_id] == last_stop:
            c.sort(key=lambda t: (t[2], -t[0], t[1]))   # 末站：低、靠车头
        else:
            c.sort(key=lambda t: (t[2], t[0], t[1]))    # 其它站：低、靠后门
        return c
    return cands

orig_pack = P.pack_route
def pack_route_aware(request, vehicle_id, store_ids, budget=None, multi_support=True):
    store_order = {sid: i for i, sid in enumerate(store_ids)}
    boxes = {b.id: b for b in request.boxes}
    saved = (P._can_place, P._candidate_positions)
    P._can_place = make_can_place(store_order, boxes, multi_support)
    P._candidate_positions = make_candidates(store_order, len(store_ids) - 1)
    try:
        return orig_pack(request, vehicle_id, store_ids, budget)
    finally:
        P._can_place, P._candidate_positions = saved

# ---------- 用 pack_route_aware 跑完整求解 ----------
from backend import baselines as B, solver as S
CARTONS = [((400,300,300),6.0),((500,400,300),9.0),((600,400,400),12.0),((450,350,250),5.0),((800,400,300),10.0),((1200,400,300),14.0),((900,600,500),25.0),((1100,600,1000),40.0)]
W = [22,22,18,14,10,6,5,3]
def heterogenize(req, seed, fragile_rate=0.15):
    rng = random.Random(seed); r = copy.deepcopy(req); nb = []; k = 0
    for sid in [s["id"] for s in r["stores"]]:
        n = sum(1 for b in r["boxes"] if b["store_id"] == sid)
        for _ in range(n):
            (L,Wd,H), w = rng.choices(CARTONS, weights=W)[0]; k += 1
            nb.append({"id": f"B{k:03d}", "store_id": sid, "length_mm": L, "width_mm": Wd, "height_mm": H, "weight_kg": w, "fragile": rng.random() < fragile_rate, "allow_rotate_xy": True})
    r["boxes"] = nb; return r

def run(r, method):
    r = copy.deepcopy(r); r["options"]["method"] = method
    t0 = time.perf_counter(); res = S.solve(SolveRequest(**r)); ms = (time.perf_counter() - t0) * 1000
    m = res.metrics; fails = sum(1 for d in res.diagnostics if d.action == "pack_failed")
    # 独立校验（原校验器单箱承托规则）
    from backend.validation import validate_solution
    v = validate_solution(SolveRequest(**r), res)
    return f"{m.served_stores:2d}/{m.total_stores:2d}店 {m.used_vehicles:2d}车 {m.total_cost:7.1f}元 vol {m.volume_utilization or 0:.2f} 原校验违规 {len(v):2d} pack失败 {fails} {ms:5.0f}ms"

cases = ("small-11", "small-22", "standard-11", "stress-44")
for label, aware, multi in (("现状", False, False), ("卸货感知", True, False), ("卸货感知+多箱承托", True, True)):
    if aware:
        f = (lambda req, vid, sids, budget=None, _m=multi: pack_route_aware(req, vid, sids, budget, _m))
        B.pack_route = f; S.pack_route = f
    else:
        B.pack_route = orig_pack; S.pack_route = orig_pack
    print(f"\n===== {label} =====")
    for case in cases:
        base = json.load(open(f"data/cases/{case}.json", encoding="utf-8"))
        for seed in (1, 2):
            h = heterogenize(base, seed)
            print(f"{case}-h{seed}: " + " | ".join(f"{m[:4]} {run(h, m)}" for m in ("greedy", "sequential", "coupled")))
    # 原同构案例不退化
    for case in ("small-11", "standard-11"):
        base = json.load(open(f"data/cases/{case}.json", encoding="utf-8"))
        print(f"{case} (原): " + " | ".join(f"{m[:4]} {run(base, m)}" for m in ("sequential", "coupled")))
