"""B03 数据生成测试。

覆盖完成标准：固定种子稳定、ID 唯一、见证文件有完整路线/布局；
以及样例可解析、两种车型出现、布局不越界、每店箱数约 4。
"""

from collections import Counter

import pytest
from pydantic import ValidationError

from backend.models import SolveRequest
from scripts.generate_cases import (
    _fixed_cases,
    _floor_layout,
    generate_suite,
)


def test_fixed_cases_parse():
    for case in _fixed_cases():
        req = SolveRequest.model_validate(case)
        assert req.case_id in {"c01", "c02", "c03", "c07"}


def test_fixed_case_ids_stable():
    ids = [c["case_id"] for c in _fixed_cases()]
    assert ids == ["c01", "c02", "c03", "c07"]


def test_fixed_c02_box_too_large_data():
    c02 = [c for c in _fixed_cases() if c["case_id"] == "c02"][0]
    assert c02["boxes"][0]["length_mm"] == 2100
    assert c02["vehicles"][0]["length_mm"] == 2000
    assert c02["boxes"][0]["length_mm"] > c02["vehicles"][0]["length_mm"]


def test_suite_deterministic_same_seed():
    r1, w1 = generate_suite("small", 11)
    r2, w2 = generate_suite("small", 11)
    assert r1 == r2
    assert w1 == w2


def test_suite_diff_seed_differs():
    r1, _ = generate_suite("small", 11)
    r2, _ = generate_suite("small", 22)
    assert r1["stores"] != r2["stores"]


def test_all_suites_parse():
    for suite, seed in [("small", 11), ("standard", 22), ("stress", 44)]:
        req, _ = generate_suite(suite, seed)
        SolveRequest.model_validate(req)


def test_ids_unique():
    req, _ = generate_suite("standard", 11)
    assert len({b["id"] for b in req["boxes"]}) == len(req["boxes"])
    assert len({s["id"] for s in req["stores"]}) == len(req["stores"])
    assert len({v["id"] for v in req["vehicles"]}) == len(req["vehicles"])


def test_both_vehicle_types_present():
    req, _ = generate_suite("standard", 11)
    lengths = {v["length_mm"] for v in req["vehicles"]}
    assert lengths == {2000, 3000}


def test_boxes_per_store_about_four():
    req, _ = generate_suite("small", 11)
    counts = Counter(b["store_id"] for b in req["boxes"])
    assert all(3 <= c <= 5 for c in counts.values())


def test_witness_complete():
    req, witness = generate_suite("small", 11)
    assert witness["case_id"] == req["case_id"]
    assert len(witness["routes"]) == len(req["vehicles"])

    all_box_ids = [b["id"] for b in req["boxes"]]
    witness_box_ids = [bid for r in witness["routes"] for bid in r["box_ids"]]
    # 每个箱恰好出现一次，无缺失、无重复
    assert sorted(witness_box_ids) == sorted(all_box_ids)

    for route in witness["routes"]:
        assert len(route["placements"]) == len(route["box_ids"])
        assert len(route["unload_steps"]) == len(route["box_ids"])


def test_witness_placements_within_vehicle():
    req, witness = generate_suite("small", 11)
    vehicle_spec = {v["id"]: v for v in req["vehicles"]}
    box_spec = {b["id"]: b for b in req["boxes"]}
    for route in witness["routes"]:
        v = vehicle_spec[route["vehicle_id"]]
        for p in route["placements"]:
            b = box_spec[p["box_id"]]
            assert p["x_mm"] >= 0 and p["y_mm"] >= 0 and p["z_mm"] >= 0
            # rotation 全为 0，直接按原始尺寸校验边界
            assert p["x_mm"] + b["length_mm"] <= v["length_mm"]
            assert p["y_mm"] + b["width_mm"] <= v["width_mm"]
            assert p["z_mm"] + b["height_mm"] <= v["height_mm"]


def test_floor_layout_fits_vehicle():
    # 大车 3000x1500x1500，500 箱：6x3x3 = 54 容量
    layout = _floor_layout(54, 3000, 1500, 1500)
    assert len(layout) == 54
    for px, py, pz in layout:
        assert px + 500 <= 3000
        assert py + 500 <= 1500
        assert pz + 500 <= 1500
