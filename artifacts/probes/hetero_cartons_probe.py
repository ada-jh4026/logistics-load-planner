"""探针：把基准案例的箱件从「全部 500mm 立方体」换成异构纸箱（药店真实形态），看三种方法是否拉开差距、协同修复是否触发。不改 backend/。"""
import json, sys, random, copy, time
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from backend.models import SolveRequest
from backend.solver import solve

# 连锁药店常见外箱规格（mm）与重量（kg），含少量「别扭件」（长条/大件）
CARTONS = [
    ((400, 300, 300), 6.0), ((500, 400, 300), 9.0), ((600, 400, 400), 12.0), ((450, 350, 250), 5.0),
    ((800, 400, 300), 10.0), ((1200, 400, 300), 14.0),   # 长条（输液架、货架件）
    ((900, 600, 500), 25.0), ((1100, 600, 1000), 40.0),   # 大件（冷柜、设备）
]
WEIGHTS = [22, 22, 18, 14, 10, 6, 5, 3]  # 抽样权重：小箱多、大件少

def heterogenize(req: dict, seed: int, fragile_rate=0.15, boxes_scale=1.0) -> dict:
    rng = random.Random(seed)
    r = copy.deepcopy(req)
    new_boxes = []
    k = 0
    for sid in [s["id"] for s in r["stores"]]:
        n = max(1, round(sum(1 for b in r["boxes"] if b["store_id"] == sid) * boxes_scale))
        for _ in range(n):
            (L, W, H), w = rng.choices(CARTONS, weights=WEIGHTS)[0]
            k += 1
            new_boxes.append({"id": f"B{k:03d}", "store_id": sid, "length_mm": L, "width_mm": W, "height_mm": H,
                              "weight_kg": w, "fragile": rng.random() < fragile_rate, "allow_rotate_xy": True})
    r["boxes"] = new_boxes
    r["case_id"] = r["case_id"] + "-hetero"
    return r

def run(r: dict, method: str):
    r = copy.deepcopy(r); r["options"]["method"] = method
    t0 = time.perf_counter(); res = solve(SolveRequest(**r)); ms = (time.perf_counter() - t0) * 1000
    m = res.metrics
    repairs = [d for d in res.diagnostics if d.action != "pack_failed"]
    fails = [d for d in res.diagnostics if d.action == "pack_failed"]
    return f"{m.served_stores:2d}/{m.total_stores:2d}店 {m.used_vehicles:2d}车 {m.total_cost:7.1f}元 vol {m.volume_utilization or 0:.2f} valid {res.validation.valid} pack失败 {len(fails)} 修复动作 {len(repairs)} {ms:5.0f}ms"

for case in ("small-11", "small-22", "standard-11", "standard-22", "stress-44"):
    base = json.load(open(f"data/cases/{case}.json", encoding="utf-8"))
    for seed in (1, 2):
        h = heterogenize(base, seed)
        print(f"--- {case} hetero seed {seed}: {len(h['boxes'])} 箱 ---")
        for m in ("greedy", "sequential", "coupled"):
            print(f"   {m:10s} {run(h, m)}")
