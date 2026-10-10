"""B06: 箱体边界、碰撞与承托校验。

遵循 ALGORITHMS.md A2 几何基础：
- 旋转 0 尺寸 (L,W,H)，90 尺寸 (W,L,H)；仅绕 z 轴 0/90 度；
- 两个长方体碰撞当且仅当 x/y/z 三个开区间都存在严格正长度交集（仅面接触合法）；
- 边界 x,y,z>=0 且 x+L<=车长、y+W<=车宽、z+H<=车高；
- z=0 落地；否则须存在单个底箱，其顶面 z 等于该箱底面 z 且完整覆盖底面投影，
  底箱非易碎；不允许浮空或跨两箱承托。
"""

from __future__ import annotations

from backend.models import Box, Placement, Vehicle, Violation


def oriented_size(box: Box, rotation_xy: int) -> tuple[int, int, int]:
    """返回朝向后的 (长, 宽, 高)。rotation 0=(L,W,H)，90=(W,L,H)。"""
    if rotation_xy == 90:
        return box.width_mm, box.length_mm, box.height_mm
    return box.length_mm, box.width_mm, box.height_mm


def rotation_allowed(box: Box, rotation_xy: int) -> bool:
    return rotation_xy == 0 or box.allow_rotate_xy


def _overlap_1d(a_min: int, a_len: int, b_min: int, b_len: int) -> bool:
    """一维开区间是否有严格正长度交集（面接触不算碰撞）。"""
    return min(a_min + a_len, b_min + b_len) - max(a_min, b_min) > 0


def intersects(box_a: Box, ax: int, ay: int, az: int, rot_a: int,
               box_b: Box, bx: int, by: int, bz: int, rot_b: int) -> bool:
    """两个长方体是否碰撞（三个方向都有严格正长度交集）。"""
    al, aw, ah = oriented_size(box_a, rot_a)
    bl, bw, bh = oriented_size(box_b, rot_b)
    return (_overlap_1d(ax, al, bx, bl)
            and _overlap_1d(ay, aw, by, bw)
            and _overlap_1d(az, ah, bz, bh))


def inside_vehicle(box: Box, x: int, y: int, z: int,
                   rot: int, vehicle: Vehicle) -> bool:
    """箱件是否完全位于车厢边界内。"""
    l, w, h = oriented_size(box, rot)
    return (x >= 0 and y >= 0 and z >= 0
            and x + l <= vehicle.length_mm
            and y + w <= vehicle.width_mm
            and z + h <= vehicle.height_mm)


def find_support(box: Box, x: int, y: int, z: int, rot: int,
                 boxes: dict[str, Box],
                 placements: list[Placement]) -> Placement | None:
    """返回承托该箱的单个底箱 Placement，或 None（浮空/跨两箱）。

    调用方负责 z==0（落地）的分支；本函数仅在 z>0 时使用。
    """
    bl, bw, _ = oriented_size(box, rot)
    for other in placements:
        if other.box_id == box.id:
            continue
        ob = boxes[other.box_id]
        ol, ow, oh = oriented_size(ob, other.rotation_xy)
        if other.z_mm + oh == z:  # 顶面恰等于该箱底面
            # 完整覆盖底面投影
            if (other.x_mm <= x and x + bl <= other.x_mm + ol
                    and other.y_mm <= y and y + bw <= other.y_mm + ow):
                return other
    return None


def validate_layout(boxes: dict[str, Box], placements: list[Placement],
                    vehicle: Vehicle) -> list[Violation]:
    """校验给定布局的几何合法性，返回全部违规（定位到具体 box_ids）。"""
    violations: list[Violation] = []

    for p in placements:
        box = boxes[p.box_id]

        if not rotation_allowed(box, p.rotation_xy):
            violations.append(Violation(
                code="UNSUPPORTED",
                box_ids=[p.box_id],
                message=(
                    f"箱 {p.box_id} 不允许旋转（allow_rotate_xy=False）"
                    f"但给出 {p.rotation_xy} 度朝向"
                ),
            ))

        if not inside_vehicle(box, p.x_mm, p.y_mm, p.z_mm,
                              p.rotation_xy, vehicle):
            violations.append(Violation(
                code="OUT_OF_BOUNDS",
                box_ids=[p.box_id],
                message=f"箱 {p.box_id} 超出车厢边界",
            ))

        if p.z_mm != 0:
            support = find_support(box, p.x_mm, p.y_mm, p.z_mm,
                                   p.rotation_xy, boxes, placements)
            if support is None:
                violations.append(Violation(
                    code="UNSUPPORTED",
                    box_ids=[p.box_id],
                    message=f"箱 {p.box_id} 浮空或跨多箱承托",
                ))
            elif boxes[support.box_id].fragile:
                violations.append(Violation(
                    code="FRAGILE_LOAD",
                    box_ids=[p.box_id, support.box_id],
                    message=f"箱 {p.box_id} 承托在易碎箱 {support.box_id} 上",
                ))

    n = len(placements)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = placements[i], placements[j]
            if intersects(boxes[a.box_id], a.x_mm, a.y_mm, a.z_mm, a.rotation_xy,
                          boxes[b.box_id], b.x_mm, b.y_mm, b.z_mm, b.rotation_xy):
                violations.append(Violation(
                    code="OVERLAP",
                    box_ids=[a.box_id, b.box_id],
                    message=f"箱 {a.box_id} 与箱 {b.box_id} 重叠",
                ))

    return violations
