"""Development search for an independently feasible route missed by current packer.

The found case is explicitly a development regression, not a blind benchmark.
"""

from __future__ import annotations

import json
import random

from backend.budget import Budget
from backend.models import SolveRequest
from backend.models import Placement, UnloadStep
from artifacts.probes.legacy_packing_1c5054e import pack_route
from backend.validation import validate_vehicle_candidate
from scripts.generate_hetero_cases import OUTPUT, build


def main() -> int:
    for seed in range(200):
        rng = random.Random(seed)
        sizes = []
        for _ in range(3):
            widths = [rng.randrange(250, 401, 50) for _ in range(4)]
            if sum(widths) > 1500:
                break
            sizes.append([(rng.randrange(400, 951, 50), width,
                           rng.randrange(250, 751, 50)) for width in widths])
        if len(sizes) != 3:
            continue
        request, witness = build(f"hetero-dev-{seed}", sizes, 1000)
        request["vehicles"] = request["vehicles"][:1]
        for index, store in enumerate(request["stores"]):
            store["window_start_min"] = 480.0 + index * 20.0
            store["window_end_min"] = 490.0 + index * 20.0
        parsed = SolveRequest.model_validate(request)
        assert validate_vehicle_candidate(
            parsed, "V01", witness["store_ids"],
            [Placement.model_validate(p) for p in witness["placements"]],
            [UnloadStep.model_validate(s) for s in witness["unload_steps"]]) == []
        result = pack_route(parsed, "V01", witness["store_ids"], Budget(10000, 2000))
        if result.success:
            continue
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / "hetero-development.json").write_text(
            json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (OUTPUT / "hetero-development.meta.json").write_text(
            json.dumps({"feasible_witness": [witness], "search_seed": seed,
                        "current_packer_reason": result.reason_code,
                        "current_packer_message": result.message},
                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"found_seed={seed} reason={result.reason_code} message={result.message}")
        return 0
    print("no failing case in fixed 0..199 search range")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
