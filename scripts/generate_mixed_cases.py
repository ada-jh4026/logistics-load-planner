"""Freeze Claude's synthetic mixed-carton probe distribution before benchmarking."""
import copy
import json
import random
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARTONS = [((400, 300, 300), 6), ((500, 400, 300), 9),
           ((600, 400, 400), 12), ((450, 350, 250), 5),
           ((800, 400, 300), 10), ((1200, 400, 300), 14),
           ((900, 600, 500), 25), ((1100, 600, 1000), 40)]
WEIGHTS = [22, 22, 18, 14, 10, 6, 5, 3]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--holdout", action="store_true")
    args = parser.parse_args()
    out = ROOT / "data/hetero_cases"
    out.mkdir(exist_ok=True)
    entries = []
    names = ("small-22", "standard-22", "stress-44") if args.holdout else ("small-11", "standard-11", "stress-44")
    seeds = (11, 22) if args.holdout else (1, 2)
    for name in names:
        for seed in seeds:
            data = json.loads((ROOT / "data/cases" / f"{name}.json").read_text(encoding="utf-8"))
            original = copy.deepcopy(data["boxes"])
            rng = random.Random(seed)
            data["boxes"] = []
            for store in data["stores"]:
                sid = store["id"]
                for _ in range(sum(b["store_id"] == sid for b in original)):
                    (length, width, height), weight = rng.choices(CARTONS, weights=WEIGHTS)[0]
                    data["boxes"].append({
                        "id": f"B{len(data['boxes']) + 1:03d}", "store_id": sid,
                        "length_mm": length, "width_mm": width, "height_mm": height,
                        "weight_kg": weight, "fragile": rng.random() < .15,
                        "allow_rotate_xy": True})
            cid = f"{name}-mixed-{seed}"
            data["case_id"] = cid
            (out / f"{cid}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            entries.append({"case_id": cid, "path": f"data/hetero_cases/{cid}.json",
                            "base_case": name, "carton_seed": seed,
                            "feasibility": "not_certified_before_run"})
    manifest = {"kind": "synthetic_mixed_cartons_claude_distribution",
                "cases": entries, "cartons": CARTONS, "weights": WEIGHTS,
                "fragile_rate": .15,
                "holdout": args.holdout,
                "selection": f"all {names} crossed with seeds {seeds}; no filtering"}
    filename = "mixed-holdout-manifest.json" if args.holdout else "mixed-manifest.json"
    (out / filename).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated={len(entries)}")


if __name__ == "__main__":
    main()
