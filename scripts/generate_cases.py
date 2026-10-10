"""B03: 生成固定案例及可行构造数据。

产出两类数据：

1. 固定验收案例 C01/C02/C03/C07（对应 ACCEPTANCE.md），case_id 稳定，不依赖 seed。
2. 随机实验案例 small/standard/stress（对应 EVALUATION.md 规模），用 seed 控制门店位置
   与箱数，同 seed 结果确定。

每个随机案例配套一份「已知可行见证」（witness），记录完整的车辆-门店分配、逐箱
地板布局与卸货步骤。见证仅用于数据正确性复核（B16 会用独立校验器复查），
绝不允许传入正式求解器充当答案。

用法：
    python scripts/generate_cases.py --suite small --seeds 11 22 33 --output data/cases
"""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

SCHEMA_VERSION = "0.1"

# 两种车型：长宽高(mm)、载重(kg)、固定费(元)、每公里(元)
VEHICLE_TYPES = {
    "small": {"length_mm": 2000, "width_mm": 1000, "height_mm": 2000,
              "max_weight_kg": 500.0, "fixed_cost": 100.0, "cost_per_km": 2.0},
    "large": {"length_mm": 3000, "width_mm": 1500, "height_mm": 1500,
              "max_weight_kg": 1000.0, "fixed_cost": 150.0, "cost_per_km": 2.0},
}

# 等规格箱：500mm 立方，10kg。保守地板布局依赖等规格箱。
BOX_SIZE_MM = 500
BOX_WEIGHT_KG = 10.0

SPEED_KMPH = 30.0
DEPARTURE_MIN = 480.0
SERVICE_MIN = 5.0

# 每辆大车服务 3 店、小车服务 2 店；车型交替分配保证两种车型都出现。
LARGE_STORES = 3
SMALL_STORES = 2

SUITE_STORES = {"small": 10, "standard": 30, "stress": 60}
BOXES_PER_STORE_RANGE = (3, 5)


def _options(seed: int = 42) -> dict:
    return {
        "method": "coupled",
        "seed": seed,
        "time_limit_ms": 10000,
        "max_iterations": 200,
        "speed_kmph": SPEED_KMPH,
    }


def _vehicle(kind: str, index: int) -> dict:
    return {"id": f"V{index:02d}", **VEHICLE_TYPES[kind]}


def _box(index: int, store_id: str) -> dict:
    return {
        "id": f"B{index:03d}",
        "store_id": store_id,
        "length_mm": BOX_SIZE_MM,
        "width_mm": BOX_SIZE_MM,
        "height_mm": BOX_SIZE_MM,
        "weight_kg": BOX_WEIGHT_KG,
        "fragile": False,
        "allow_rotate_xy": True,
    }


def _store(index: int, x_km: float, y_km: float,
           window_start: float, window_end: float) -> dict:
    return {
        "id": f"S{index:02d}",
        "x_km": round(x_km, 3),
        "y_km": round(y_km, 3),
        "window_start_min": round(window_start, 3),
        "window_end_min": round(window_end, 3),
        "service_min": SERVICE_MIN,
    }


def _distance_km(ax: float, ay: float, bx: float, by: float) -> float:
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def _travel_min(km: float) -> float:
    return km / SPEED_KMPH * 60.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _make_groups(positions: list[tuple[str, float, float]]) -> list[tuple[str, list[tuple[str, float, float]]]]:
    """车型交替分组；组内按离仓库距离排序（近的先送）作为配送顺序。"""
    groups = []
    idx = 0
    toggle = 0
    while idx < len(positions):
        kind = "large" if toggle % 2 == 0 else "small"
        size = LARGE_STORES if kind == "large" else SMALL_STORES
        group = sorted(positions[idx:idx + size],
                       key=lambda p: _distance_km(0.0, 0.0, p[1], p[2]))
        groups.append((kind, group))
        idx += size
        toggle += 1
    return groups


def _floor_layout(n_boxes: int, length_mm: int, width_mm: int,
                  height_mm: int) -> list[tuple[int, int, int]]:
    """等规格箱的保守地板布局：x 优先、y 其次、z 最后，逐格放置。"""
    cols_x = length_mm // BOX_SIZE_MM
    cols_y = width_mm // BOX_SIZE_MM
    per_layer = cols_x * cols_y
    placements = []
    for i in range(n_boxes):
        layer = i // per_layer
        rem = i % per_layer
        placements.append(((rem % cols_x) * BOX_SIZE_MM,
                           (rem // cols_x) * BOX_SIZE_MM,
                           layer * BOX_SIZE_MM))
    return placements


def generate_suite(suite: str, seed: int) -> tuple[dict, dict]:
    """生成一个 suite 案例，返回 (request, witness)。"""
    rng = random.Random(seed)
    n_stores = SUITE_STORES[suite]

    # 1. 门店位置（seed 控制）
    positions = [(f"S{i + 1:02d}", rng.uniform(2.0, 60.0), rng.uniform(2.0, 60.0))
                 for i in range(n_stores)]

    # 2. 车型交替分组，组内按距离排序（配送顺序）
    groups = _make_groups(positions)

    # 3. 每店箱数（seed 控制，约 4）
    boxes_per_store = {sid: rng.randint(*BOXES_PER_STORE_RANGE) for sid, _, _ in positions}

    # 4. 车辆
    vehicles = [_vehicle(kind, gi + 1) for gi, (kind, _) in enumerate(groups)]

    # 5. 箱件（按组、组内配送顺序、店内顺序编号）
    boxes = []
    route_box_ids: list[list[str]] = []
    box_index = 0
    for kind, group in groups:
        ids = []
        for sid, _, _ in group:
            for _ in range(boxes_per_store[sid]):
                box_index += 1
                boxes.append(_box(box_index, sid))
                ids.append(f"B{box_index:03d}")
        route_box_ids.append(ids)

    # 6. 门店时间窗：按配送顺序派生宽裕窗口（保证见证路线可行）
    stores = []
    for kind, group in groups:
        prev_x = prev_y = 0.0
        clock = DEPARTURE_MIN
        for sid, x, y in group:
            clock += _travel_min(_distance_km(prev_x, prev_y, x, y))
            arrival = clock
            stores.append(_store(int(sid[1:]), x, y,
                                 _clamp(arrival - 60.0, 0.0, 1440.0),
                                 _clamp(arrival + 120.0, 0.0, 1440.0)))
            clock = arrival + SERVICE_MIN
            prev_x, prev_y = x, y

    request = {
        "schema_version": SCHEMA_VERSION,
        "case_id": f"{suite}-{seed}",
        "data_source": "synthetic",
        "depot": {"id": "DEPOT", "x_km": 0, "y_km": 0, "departure_min": DEPARTURE_MIN},
        "stores": stores,
        "vehicles": vehicles,
        "boxes": boxes,
        # 实验套件用足够大的迭代上限与压力案例 30s 预算（EVALUATION 口径）
        "options": {
            **_options(42),
            "max_iterations": 10000,
            "time_limit_ms": 30000 if suite == "stress" else 10000,
        },
    }

    witness = _build_witness(request, groups, seed)
    return request, witness


def _build_witness(request: dict, groups, seed: int) -> dict:
    """用确定性 packer 构造已知可行见证（路线 + 逐箱布局 + 卸货步骤）。

    见证由 pack_route 生成（逆配送序装箱 + 正确卸货序列），保证布局与卸货
    均可行；仅用于数据正确性复核，不作为求解器答案（B16 用独立校验器复查）。
    """
    from backend.models import SolveRequest
    from backend.packing import pack_route

    req = SolveRequest.model_validate(request)
    routes = []
    for (kind, group), vehicle in zip(groups, request["vehicles"]):
        store_ids = [sid for sid, _, _ in group]
        pack = pack_route(req, vehicle["id"], store_ids)
        if not pack.success:
            raise ValueError(
                f"见证构造失败：车辆 {vehicle['id']} 门店 {store_ids} "
                f"reason={pack.reason_code}: {pack.message}")
        routes.append({
            "vehicle_id": vehicle["id"],
            "store_ids": store_ids,
            "box_ids": [p.box_id for p in pack.placements],
            "placements": [p.model_dump() for p in pack.placements],
            "unload_steps": [s.model_dump() for s in pack.unload_steps],
        })

    return {
        "case_id": request["case_id"],
        "seed": seed,
        "kind": "witness",
        "note": "已知可行见证，仅用于数据正确性复核，不作为求解器答案。",
        "routes": routes,
    }


# --------------------------------------------------------------------------
# 固定验收案例 C01/C02/C03/C07
# --------------------------------------------------------------------------

def _base_request(case_id: str, depot, stores, vehicles, boxes) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "data_source": "synthetic",
        "depot": depot,
        "stores": stores,
        "vehicles": vehicles,
        "boxes": boxes,
        "options": _options(42),
    }


def _fixed_cases() -> list[dict]:
    depot = {"id": "DEPOT", "x_km": 0, "y_km": 0, "departure_min": 480.0}
    small_vehicle = {
        "id": "V01", "length_mm": 2000, "width_mm": 1000, "height_mm": 2000,
        "max_weight_kg": 500.0, "fixed_cost": 100.0, "cost_per_km": 2.0,
    }

    # C01 正常配送与等待（与 examples/request-success 同场景）
    c01 = _base_request(
        "c01", depot,
        [{"id": "S01", "x_km": 3, "y_km": 4, "window_start_min": 500,
          "window_end_min": 600, "service_min": 5}],
        [small_vehicle],
        [
            {"id": "B01", "store_id": "S01", "length_mm": 1000, "width_mm": 1000,
             "height_mm": 1000, "weight_kg": 100, "fragile": False, "allow_rotate_xy": True},
            {"id": "B02", "store_id": "S01", "length_mm": 1000, "width_mm": 1000,
             "height_mm": 1000, "weight_kg": 50, "fragile": True, "allow_rotate_xy": True},
        ],
    )

    # C02 总体积够但单件尺寸不合：2100 长在 2000 车与 90 度旋转后 2100 宽均超限
    c02 = _base_request(
        "c02", depot,
        [{"id": "S01", "x_km": 3, "y_km": 4, "window_start_min": 500,
          "window_end_min": 600, "service_min": 5}],
        [small_vehicle],
        [
            {"id": "B01", "store_id": "S01", "length_mm": 2100, "width_mm": 500,
             "height_mm": 500, "weight_kg": 50, "fragile": False, "allow_rotate_xy": True},
        ],
    )

    # C03 时间窗无法到达：30km、速度30 → 最早 540，窗口 490..500
    c03 = _base_request(
        "c03", depot,
        [{"id": "S01", "x_km": 30, "y_km": 0, "window_start_min": 490,
          "window_end_min": 500, "service_min": 5}],
        [small_vehicle],
        [
            {"id": "B01", "store_id": "S01", "length_mm": 500, "width_mm": 500,
             "height_mm": 500, "weight_kg": 50, "fragile": False, "allow_rotate_xy": True},
        ],
    )

    # C07 车辆不足与门店原子性：一车 100kg，S1 两箱各 30、S2 一箱 60
    c07_vehicle = dict(small_vehicle, max_weight_kg=100.0)
    c07 = _base_request(
        "c07", depot,
        [
            {"id": "S01", "x_km": 3, "y_km": 4, "window_start_min": 480,
             "window_end_min": 700, "service_min": 5},
            {"id": "S02", "x_km": 6, "y_km": 8, "window_start_min": 480,
             "window_end_min": 700, "service_min": 5},
        ],
        [c07_vehicle],
        [
            {"id": "B01", "store_id": "S01", "length_mm": 500, "width_mm": 500,
             "height_mm": 500, "weight_kg": 30, "fragile": False, "allow_rotate_xy": True},
            {"id": "B02", "store_id": "S01", "length_mm": 500, "width_mm": 500,
             "height_mm": 500, "weight_kg": 30, "fragile": False, "allow_rotate_xy": True},
            {"id": "B03", "store_id": "S02", "length_mm": 500, "width_mm": 500,
             "height_mm": 500, "weight_kg": 60, "fragile": False, "allow_rotate_xy": True},
        ],
    )

    return [c01, c02, c03, c07]


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="生成物流配载案例数据")
    parser.add_argument("--suite", choices=["small", "standard", "stress"],
                        default="small")
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 22, 33])
    parser.add_argument("--output", type=str, default="data/cases")
    args = parser.parse_args()

    out_dir = Path(args.output)
    witness_dir = Path("data/witnesses")

    for case in _fixed_cases():
        _write_json(out_dir / f"{case['case_id']}.json", case)

    for seed in args.seeds:
        request, witness = generate_suite(args.suite, seed)
        _write_json(out_dir / f"{request['case_id']}.json", request)
        _write_json(witness_dir / f"{request['case_id']}.witness.json", witness)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
