"""B06 几何校验测试（ACCEPTANCE C04 + ALGORITHMS A2）。"""

from backend.geometry import (
    find_support,
    inside_vehicle,
    intersects,
    oriented_size,
    validate_layout,
)
from backend.models import Box, Placement, Vehicle


def _box(bid, length=1000, width=1000, height=1000, fragile=False,
         allow_rotate=True):
    return Box(id=bid, store_id="S01", length_mm=length, width_mm=width,
               height_mm=height, weight_kg=10, fragile=fragile,
               allow_rotate_xy=allow_rotate)


def _place(bid, x, y, z, rot=0):
    return Placement(box_id=bid, x_mm=x, y_mm=y, z_mm=z, rotation_xy=rot)


def _vehicle(length=2000, width=1000, height=2000):
    return Vehicle(id="V01", length_mm=length, width_mm=width,
                   height_mm=height, max_weight_kg=500, fixed_cost=100,
                   cost_per_km=2)


def _boxes_dict(*boxes):
    return {b.id: b for b in boxes}


def _codes(violations):
    return {v.code for v in violations}


# --------------------------------------------------------------------------
# 基础函数
# --------------------------------------------------------------------------

def test_oriented_size_rotation():
    b = _box("B", length=2000, width=1000, height=500)
    assert oriented_size(b, 0) == (2000, 1000, 500)
    assert oriented_size(b, 90) == (1000, 2000, 500)


def test_intersects_face_contact_not_overlap():
    a = _box("A")
    b = _box("B")
    # A 在 (0,0,0)，B 在 (1000,0,0)：面接触，不碰撞
    assert intersects(a, 0, 0, 0, 0, b, 1000, 0, 0, 0) is False


def test_intersects_1mm_overlap():
    a = _box("A")
    b = _box("B")
    # B 在 (999,0,0)：x 方向 1mm 重叠
    assert intersects(a, 0, 0, 0, 0, b, 999, 0, 0, 0) is True


def test_inside_vehicle_boundary():
    b = _box("B")
    v = _vehicle(2000, 1000, 2000)
    assert inside_vehicle(b, 0, 0, 0, 0, v) is True
    assert inside_vehicle(b, 1000, 0, 0, 0, v) is True  # 贴边合法
    assert inside_vehicle(b, 1001, 0, 0, 0, v) is False  # 越界


# --------------------------------------------------------------------------
# validate_layout 正反案例
# --------------------------------------------------------------------------

def test_ground_level_ok():
    a = _box("A")
    v = _vehicle()
    violations = validate_layout(_boxes_dict(a), [_place("A", 0, 0, 0)], v)
    assert violations == []


def test_support_exact_top_ok():
    a = _box("A", fragile=False)
    b = _box("B")
    v = _vehicle()
    # B 底面恰等于 A 顶面，合法
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)], v)
    assert violations == []


def test_fragile_load_rejected():
    a = _box("A", fragile=True)
    b = _box("B")
    v = _vehicle()
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)], v)
    assert "FRAGILE_LOAD" in _codes(violations)


def test_fragile_false_supports():
    a = _box("A", fragile=False)
    b = _box("B")
    v = _vehicle()
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)], v)
    assert "FRAGILE_LOAD" not in _codes(violations)


def test_unsupported_partial_projection():
    a = _box("A", fragile=False)
    b = _box("B")
    v = _vehicle()
    # B 在 (500,0,1000)，底面 x 范围 500..1500 超出 A 的 0..1000
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 500, 0, 1000)], v)
    assert "UNSUPPORTED" in _codes(violations)


def test_unsupported_floating():
    a = _box("A", fragile=False)
    b = _box("B")
    v = _vehicle()
    # B.z = 1100，浮空（A 顶面 1000）
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 0, 0, 1100)], v)
    assert "UNSUPPORTED" in _codes(violations)


def test_unsupported_cross_two_boxes():
    a1 = _box("A1", length=500, fragile=False)
    a2 = _box("A2", length=500, fragile=False)
    b = _box("B")
    v = _vehicle(3000, 1000, 2000)
    # B 宽 1000 跨 A1(0..500) 与 A2(500..1000)，无单箱完整承托
    violations = validate_layout(
        _boxes_dict(a1, a2, b),
        [_place("A1", 0, 0, 0), _place("A2", 500, 0, 0), _place("B", 0, 0, 1000)],
        v)
    assert "UNSUPPORTED" in _codes(violations)


def test_out_of_bounds():
    b = _box("B")
    v = _vehicle(2000, 1000, 2000)
    violations = validate_layout(_boxes_dict(b), [_place("B", 1500, 0, 0)], v)
    # 1500 + 1000 = 2500 > 2000
    assert "OUT_OF_BOUNDS" in _codes(violations)


def test_overlap_two_boxes():
    a = _box("A")
    b = _box("B")
    v = _vehicle()
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 500, 0, 0)], v)
    assert "OVERLAP" in _codes(violations)


def test_rotation_not_allowed():
    b = _box("B", length=2000, width=1000, allow_rotate=False)
    v = _vehicle()
    violations = validate_layout(_boxes_dict(b), [_place("B", 0, 0, 0, rot=90)], v)
    assert "UNSUPPORTED" in _codes(violations)


def test_violation_locates_box_ids():
    a = _box("A", fragile=True)
    b = _box("B")
    v = _vehicle()
    violations = validate_layout(
        _boxes_dict(a, b), [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)], v)
    fragile = [v for v in violations if v.code == "FRAGILE_LOAD"][0]
    assert set(fragile.box_ids) == {"A", "B"}
