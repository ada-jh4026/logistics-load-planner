"""Create fixed mixed-carton cases with independent unloadable layouts."""

from __future__ import annotations

import json
from pathlib import Path

from backend.models import Placement, SolveRequest
from backend.unloading import generate_unload_steps
from backend.validation import validate_vehicle_candidate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data/hetero_cases"


def build(case_id: str, sizes: list[list[tuple[int, int, int]]],
          segment_mm: int) -> tuple[dict, dict]:
    stores = []
    boxes = []
    placements = []
    for index, stop_sizes in enumerate(sizes):
        sid = f"S{index + 1:02d}"
        stores.append({"id": sid, "x_km": float(index + 1), "y_km": 0.0,
                       "window_start_min": 0.0, "window_end_min": 1440.0,
                       "service_min": 0.0})
        y = 0
        for dimensions in stop_sizes:
            length, width, height = dimensions
            assert length <= segment_mm and y + width <= 1500
            bid = f"B{len(boxes) + 1:03d}"
            boxes.append({"id": bid, "store_id": sid,
                          "length_mm": length, "width_mm": width,
                          "height_mm": height, "weight_kg": 10.0,
                          "fragile": False, "allow_rotate_xy": False})
            placements.append({"box_id": bid, "x_mm": index * segment_mm,
                               "y_mm": y, "z_mm": 0, "rotation_xy": 0})
            y += width
    request = {
        "schema_version": "0.1", "case_id": case_id, "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0.0, "y_km": 0.0,
                  "departure_min": 480.0},
        "stores": stores,
        "vehicles": [
            {"id": "V01", "length_mm": 3000, "width_mm": 1500,
             "height_mm": 1500, "max_weight_kg": 1000.0,
             "fixed_cost": 100.0, "cost_per_km": 1.0},
            {"id": "V02", "length_mm": 3000, "width_mm": 1500,
             "height_mm": 1500, "max_weight_kg": 1000.0,
             "fixed_cost": 150.0, "cost_per_km": 1.0},
        ],
        "boxes": boxes,
        "options": {"method": "coupled", "seed": 0,
                    "time_limit_ms": 10000, "max_iterations": 2000,
                    "speed_kmph": 30.0},
    }
    parsed = SolveRequest.model_validate(request)
    box_map = {b.id: b for b in parsed.boxes}
    placed = [Placement.model_validate(p) for p in placements]
    route = [s.id for s in parsed.stores]
    steps, error = generate_unload_steps(box_map, placed, route)
    assert error is None
    violations = validate_vehicle_candidate(parsed, "V01", route, placed, steps)
    assert not violations, violations
    witness = {"vehicle_id": "V01", "store_ids": route,
               "placements": placements,
               "unload_steps": [step.model_dump() for step in steps]}
    return request, witness


def main() -> None:
    specifications = [
        ("hetero-floor-2", [[(1200, 400, 300), (900, 500, 400), (600, 400, 500)],
                            [(1100, 450, 350), (700, 500, 600), (500, 400, 300)]], 1500),
        ("hetero-floor-3", [[(900, 400, 300), (600, 400, 500), (450, 350, 250)],
                            [(800, 400, 350), (700, 400, 300), (500, 400, 450)],
                            [(850, 450, 400), (600, 350, 500), (400, 400, 300)]], 1000),
        ("hetero-long-2", [[(1200, 600, 300), (1100, 500, 400)],
                           [(1200, 550, 500), (800, 500, 300), (500, 350, 400)]], 1500),
    ]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {"kind": "synthetic_known_feasible_heterogeneous_floor_layouts",
                "cases": []}
    for case_id, sizes, segment in specifications:
        request, witness = build(case_id, sizes, segment)
        path = OUTPUT / f"{case_id}.json"
        path.write_text(json.dumps(request, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
        (OUTPUT / f"{case_id}.meta.json").write_text(
            json.dumps({"feasible_witness": [witness]}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        manifest["cases"].append({"case_id": case_id,
                                  "path": f"data/hetero_cases/{case_id}.json"})
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print(f"generated={len(specifications)} independently_validated={len(specifications)}")


if __name__ == "__main__":
    main()
