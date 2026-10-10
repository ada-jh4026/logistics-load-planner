"""诊断 3：混合箱件 + 多门店路线时 pack_route 的失败原因；对照「同一批箱全归一店」。"""
import json, sys, random, copy
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from backend.models import SolveRequest
from backend.packing import pack_route
from backend.budget import Budget

base = json.load(open("data/cases/small-11.json", encoding="utf-8"))
CARTONS = [((400,300,300),6.0),((500,400,300),9.0),((600,400,400),12.0),((450,350,250),5.0),((800,400,300),10.0),((1200,400,300),14.0),((900,600,500),25.0),((1100,600,1000),40.0)]
W = [22,22,18,14,10,6,5,3]

def make(n_stores, boxes_per_store, seed, vehicle="small", flatten=False):
    rng = random.Random(seed); r = copy.deepcopy(base)
    r["stores"] = r["stores"][:n_stores]; sids = [s["id"] for s in r["stores"]]
    r["vehicles"] = [v for v in r["vehicles"] if (v["length_mm"] == 2000) == (vehicle == "small")][:1]
    r["boxes"] = []; k = 0
    for sid in sids:
        for _ in range(boxes_per_store):
            (L,Wd,H), w = rng.choices(CARTONS, weights=W)[0]; k += 1
            r["boxes"].append({"id": f"B{k:03d}", "store_id": sids[0] if flatten else sid, "length_mm": L, "width_mm": Wd, "height_mm": H, "weight_kg": w, "fragile": False, "allow_rotate_xy": True})
    if flatten: r["stores"] = r["stores"][:1]
    return SolveRequest(**r)

for n_stores, bps in ((2, 4), (3, 4), (4, 4), (2, 8), (3, 6)):
    print(f"== {n_stores} 店 × {bps} 箱 ==")
    for seed in range(4):
        req = make(n_stores, bps, seed)
        p = pack_route(req, req.vehicles[0].id, [s.id for s in req.stores], Budget(10000, 10000))
        reqf = make(n_stores, bps, seed, flatten=True)
        pf = pack_route(reqf, reqf.vehicles[0].id, [reqf.stores[0].id], Budget(10000, 10000))
        print(f"  seed {seed}: 多店 {'OK ' if p.success else 'FAIL'} [{p.reason_code}] {str(p.message)[:70]:70s} | 同箱单店 {'OK' if pf.success else 'FAIL'}")
