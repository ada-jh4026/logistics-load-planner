"""B07 卸货与装货测试（ACCEPTANCE C05/C06 + ALGORITHMS A3）。"""

from backend.models import Box, Placement
from backend.unloading import (
    generate_loading_steps,
    generate_unload_steps,
    validate_loading_steps,
    validate_unload_steps,
)


def _box(bid, store_id, length=1000, width=1000, height=1000, fragile=False):
    return Box(id=bid, store_id=store_id, length_mm=length, width_mm=width,
               height_mm=height, weight_kg=10, fragile=fragile,
               allow_rotate_xy=True)


def _place(bid, x, y, z):
    return Placement(box_id=bid, x_mm=x, y_mm=y, z_mm=z, rotation_xy=0)


def _vehicle():
    from backend.models import Vehicle
    return Vehicle(id="V01", length_mm=3000, width_mm=1000, height_mm=2000,
                   max_weight_kg=500, fixed_cost=100, cost_per_km=2)


def _codes(violations):
    return {v.code for v in violations}


# --------------------------------------------------------------------------
# C05 卸货阻挡
# --------------------------------------------------------------------------

def test_c05_blocked_by_front_box():
    a = _box("A", "S1")
    b = _box("B", "S2")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 2000, 0, 0), _place("B", 0, 0, 0)]
    steps, error = generate_unload_steps(boxes, placements, ["S1", "S2"])
    # A 在 x=2000 抽出路径被 x=0 的 B 挡住
    assert error is not None
    assert error.code == "UNLOAD_BLOCKED"


def test_c05_swapped_positions_pass():
    a = _box("A", "S1")
    b = _box("B", "S2")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 2000, 0, 0)]
    steps, error = generate_unload_steps(boxes, placements, ["S1", "S2"])
    assert error is None
    assert [s.box_id for s in steps] == ["A", "B"]


# --------------------------------------------------------------------------
# C06 堆叠抽底
# --------------------------------------------------------------------------

def test_c06_cannot_pull_supporting_box():
    a = _box("A", "S1", fragile=False)
    b = _box("B", "S2")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)]
    # A 属早站 S1，B 属晚站 S2：先卸 A 会抽底
    steps, error = generate_unload_steps(boxes, placements, ["S1", "S2"])
    assert error is not None
    assert error.code == "UNLOAD_BLOCKED"


def test_c06_same_store_top_first():
    a = _box("A", "S1", fragile=False)
    b = _box("B", "S1")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)]
    steps, error = generate_unload_steps(boxes, placements, ["S1"])
    assert error is None
    # 先上后下：先 B 再 A
    assert [s.box_id for s in steps] == ["B", "A"]


# --------------------------------------------------------------------------
# 生成器与验证器
# --------------------------------------------------------------------------

def test_validate_accepts_generated_steps():
    a = _box("A", "S1", fragile=False)
    b = _box("B", "S1")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)]
    steps, error = generate_unload_steps(boxes, placements, ["S1"])
    assert error is None
    violations = validate_unload_steps(steps, boxes, placements, ["S1"])
    assert violations == []


def test_validate_rejects_wrong_store_order():
    a = _box("A", "S1")
    b = _box("B", "S2")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 2000, 0, 0)]
    from backend.models import UnloadStep
    # 错误顺序：先卸 B(S2) 再 A(S1)
    steps = [UnloadStep(step=1, store_id="S2", box_id="B"),
             UnloadStep(step=2, store_id="S1", box_id="A")]
    violations = validate_unload_steps(steps, boxes, placements, ["S1", "S2"])
    assert "STEP_MISMATCH" in _codes(violations)


def test_validate_detects_missing_box():
    a = _box("A", "S1")
    b = _box("B", "S1")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 2000, 0, 0)]
    from backend.models import UnloadStep
    steps = [UnloadStep(step=1, store_id="S1", box_id="A")]  # 漏掉 B
    violations = validate_unload_steps(steps, boxes, placements, ["S1"])
    assert "BOX_MISSING" in _codes(violations)


# --------------------------------------------------------------------------
# 装货逆序
# --------------------------------------------------------------------------

def test_loading_is_reverse_of_unloading():
    a = _box("A", "S1", fragile=False)
    b = _box("B", "S1")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)]
    steps, error = generate_unload_steps(boxes, placements, ["S1"])
    assert error is None
    loading = generate_loading_steps(steps)
    # 卸货 [B, A] → 装货 [A, B]
    assert [s.box_id for s in loading] == ["A", "B"]


def test_validate_loading_accepts_reverse():
    a = _box("A", "S1", fragile=False)
    b = _box("B", "S1")
    boxes = {"A": a, "B": b}
    placements = [_place("A", 0, 0, 0), _place("B", 0, 0, 1000)]
    steps, error = generate_unload_steps(boxes, placements, ["S1"])
    loading = generate_loading_steps(steps)
    violations = validate_loading_steps(loading, boxes, placements, _vehicle())
    assert violations == []
