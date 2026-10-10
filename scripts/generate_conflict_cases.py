"""O02 fixed synthetic conflict inputs, certificates, and predeclared cases.

No solver outcome is used to select or alter a case. Seed variations are
deterministic formula variants, not independent empirical orders.
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.models import Placement, SolveRequest, UnloadStep
from backend.unloading import generate_unload_steps
from backend.validation import validate_vehicle_candidate

OUT = Path("data/conflict_cases")
# Seed 11 was used only while shaping the scenario families. These five
# variants are predeclared for the untouched comparison run.
SEEDS = (22, 33, 44, 55, 66)


def _base(case_id, stores, vehicles, boxes):
    return {
        "schema_version": "0.1", "case_id": case_id,
        "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0, "y_km": 0,
                  "departure_min": 480},
        "stores": stores, "vehicles": vehicles, "boxes": boxes,
        "options": {"method": "coupled", "seed": int(case_id.split("-")[-1]),
                    "time_limit_ms": 10000, "max_iterations": 200,
                    "speed_kmph": 30},
    }


def _store(sid, x, end=1440):
    return {"id": sid, "x_km": x, "y_km": 0,
            "window_start_min": 0, "window_end_min": end,
            "service_min": 0}


def _vehicle(vid, length, width=1000, height=1000, fixed=10):
    return {"id": vid, "length_mm": length, "width_mm": width,
            "height_mm": height, "max_weight_kg": 500,
            "fixed_cost": fixed, "cost_per_km": 2}


def _box(bid, sid, length, width=600, height=600):
    return {"id": bid, "store_id": sid, "length_mm": length,
            "width_mm": width, "height_mm": height,
            "weight_kg": 50, "fragile": False,
            "allow_rotate_xy": False}


def _route_witness(req: SolveRequest, vehicle_id: str, sid: str):
    bid = next(box.id for box in req.boxes if box.store_id == sid)
    placement = Placement(box_id=bid, x_mm=0, y_mm=0, z_mm=0,
                          rotation_xy=0)
    unload = UnloadStep(step=1, store_id=sid, box_id=bid)
    violations = validate_vehicle_candidate(req, vehicle_id, [sid],
                                            [placement], [unload])
    if violations:
        raise AssertionError((req.case_id, vehicle_id,
                              [v.code for v in violations]))
    return {"vehicle_id": vehicle_id, "store_ids": [sid],
            "placements": [placement.model_dump()],
            "unload_steps": [unload.model_dump()]}


def _save(case, metadata):
    req = SolveRequest.model_validate(case)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{req.case_id}.json").write_text(
        json.dumps(req.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8")
    (OUT / f"{req.case_id}.meta.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8")


def generate():
    entries = []
    for seed in SEEDS:
        # Every box fits each vehicle and aggregate volume is below capacity,
        # but two floor boxes cannot coexist: 2L>car L, 2W>car W, 2H>car H.
        length = 1800 + seed % 5 * 10
        cid = f"geometry-{seed}"
        case = _base(cid,
                     [_store("S01", 3 + seed % 3), _store("S02", 4 + seed % 3)],
                     [_vehicle("V01", 3000, fixed=10),
                      _vehicle("V02", 3000, fixed=100)],
                     [_box("B01", "S01", length),
                      _box("B02", "S02", length)])
        req = SolveRequest.model_validate(case)
        witness = [_route_witness(req, "V01", "S01"),
                   _route_witness(req, "V02", "S02")]
        _save(case, {"category": "combination_geometry",
                     "seed": seed, "expected_trigger": "packer_failure",
                     "feasible_witness": witness,
                     "construction": "single boxes fit; combined floor layout exceeds all three axes"})
        entries.append({"case_id": cid, "path": f"data/conflict_cases/{cid}.json",
                        "category": "combination_geometry", "seed": seed})

    for seed in SEEDS:
        # Failed V01 group; V02 has S03 and cannot take S01/S02 within
        # their windows; unused V03 can. This probes candidate traversal.
        distance = 10 + seed % 3
        length = 1800 + seed % 5 * 10
        cid = f"time-geometry-{seed}"
        case = _base(cid,
                     [_store("S01", -distance, 510),
                      _store("S02", -distance, 511),
                      _store("S03", distance, 520)],
                     [_vehicle("V01", 3000, fixed=10),
                      _vehicle("V02", 5100, fixed=100),
                      _vehicle("V03", 5100, fixed=150)],
                     [_box("B01", "S01", length),
                      _box("B02", "S02", length),
                      _box("B03", "S03", 3200, width=1000, height=1000)])
        req = SolveRequest.model_validate(case)
        witness = [_route_witness(req, "V01", "S01"),
                   _route_witness(req, "V03", "S02"),
                   _route_witness(req, "V02", "S03")]
        _save(case, {"category": "time_geometry",
                     "seed": seed, "expected_trigger": "packer_failure",
                     "feasible_witness": witness,
                     "construction": "moving a failed store onto occupied V02 violates tight windows; unused V03 is feasible"})
        entries.append({"case_id": cid, "path": f"data/conflict_cases/{cid}.json",
                        "category": "time_geometry", "seed": seed})

    for seed in SEEDS:
        # A counterexample layout blocks S01, but the same request also has
        # a valid reversed floor placement. The solver may find it directly.
        length = 900 + seed % 3 * 20
        cid = f"unload-mechanism-{seed}"
        case = _base(cid,
                     [_store("S01", 3), _store("S02", 4)],
                     [_vehicle("V01", 2 * length, width=length,
                               height=length)],
                     [_box("B01", "S01", length, width=length,
                           height=length),
                      _box("B02", "S02", length, width=length,
                           height=length)])
        req = SolveRequest.model_validate(case)
        boxes = {box.id: box for box in req.boxes}
        blocked = [Placement(box_id="B01", x_mm=length, y_mm=0,
                             z_mm=0, rotation_xy=0),
                   Placement(box_id="B02", x_mm=0, y_mm=0,
                             z_mm=0, rotation_xy=0)]
        _, error = generate_unload_steps(boxes, blocked, ["S01", "S02"])
        if error is None or error.code != "UNLOAD_BLOCKED":
            raise AssertionError((cid, error))
        valid = [Placement(box_id="B01", x_mm=0, y_mm=0,
                           z_mm=0, rotation_xy=0),
                 Placement(box_id="B02", x_mm=length, y_mm=0,
                           z_mm=0, rotation_xy=0)]
        steps, error = generate_unload_steps(boxes, valid, ["S01", "S02"])
        if error or validate_vehicle_candidate(req, "V01", ["S01", "S02"],
                                               valid, steps):
            raise AssertionError(f"{cid}: valid layout rejected")
        _save(case, {"category": "unload_mechanism_control",
                     "seed": seed, "expected_trigger": "not_assumed",
                     "blocked_candidate": {"placements": [p.model_dump() for p in blocked],
                                           "violation": "UNLOAD_BLOCKED"},
                     "feasible_witness": [{"vehicle_id": "V01",
                                           "store_ids": ["S01", "S02"],
                                           "placements": [p.model_dump() for p in valid],
                                           "unload_steps": [s.model_dump() for s in steps]}],
                     "construction": "checker rejects a blocking layout; end-to-end packer may avoid it"})
        entries.append({"case_id": cid, "path": f"data/conflict_cases/{cid}.json",
                        "category": "unload_mechanism_control", "seed": seed})

    for case_id in ("small-11", "standard-11"):
        entries.append({"case_id": case_id,
                        "path": f"data/cases/{case_id}.json",
                        "category": "no_repair_control", "seed": 11})

    for seed in (77, 88):
        cid = f"impossible-size-{seed}"
        length = 5100 + seed
        case = _base(cid, [_store("S01", 3)],
                     [_vehicle("V01", 3000),
                      _vehicle("V02", 5000, fixed=100)],
                     [_box("B01", "S01", length)])
        _save(case, {"category": "known_infeasible_control",
                     "seed": seed, "expected_trigger": "oversize",
                     "certificate": {"box_id": "B01", "length_mm": length,
                                     "max_vehicle_length_mm": 5000,
                                     "rotation_allowed": False}})
        entries.append({"case_id": cid, "path": f"data/conflict_cases/{cid}.json",
                        "category": "known_infeasible_control", "seed": seed})

    manifest = {"version": 1, "selection_rule": "all entries generated before comparing methods",
                "seeds": list(SEEDS), "methods": ["greedy", "sequential",
                                                 "sequential_reinsert", "coupled"],
                "cases": entries}
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # Expose only two representative, real inputs through the existing
    # /api/examples discovery path for the frontend demonstration.
    demo_dir = Path("data/cases")
    for case_id in ("geometry-22", "time-geometry-22"):
        (demo_dir / f"{case_id}.json").write_bytes(
            (OUT / f"{case_id}.json").read_bytes())
    print(f"cases={len(entries)} generated={len(entries) - 2} "
          "control_references=2 demo_examples=2")


if __name__ == "__main__":
    generate()
