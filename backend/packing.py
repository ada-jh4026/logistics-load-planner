"""B09: 确定性 3D 配载启发式。

遵循 ALGORITHMS.md A6：
- 箱件按目的站逆配送序、非易碎优先、体积降序、ID 排序（默认排序）；
- 允许每箱两种水平朝向（0/90，受 allow_rotate_xy 约束）；
- 候选位置由地板角、靠车头及已放箱边界生成（x/y 边界与 z 顶面），
  剪掉越界、去重、过滤碰撞/承托/易碎，按「低重心、靠车头」评分选取；
- 候选数量设上限并记录，算法不完备，失败只表示没找到；
- 全放完再模拟卸货并独立校验；最多 3 种稳定排序；定期检查预算。

失败区分：单件所有朝向均超车厢 → BOX_TOO_LARGE；否则 SEARCH_EXHAUSTED。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.geometry import find_support, inside_vehicle, intersects, oriented_size
from backend.models import Box, Placement, SolveRequest, UnloadStep, Vehicle
from backend.unloading import generate_unload_steps
from backend.validation import validate_vehicle_candidate

CANDIDATE_LIMIT = 2000
MAX_SORTINGS = 3


@dataclass
class PackResult:
    success: bool
    placements: list[Placement] = field(default_factory=list)
    unload_steps: list[UnloadStep] = field(default_factory=list)
    reason_code: str | None = None  # BOX_TOO_LARGE / SEARCH_EXHAUSTED / TIME_LIMIT
    message: str | None = None
    candidate_attempts: int = 0


def _volume(box: Box) -> int:
    return box.length_mm * box.width_mm * box.height_mm


def _default_order(route_boxes: list[Box], store_ids: list[str]) -> list[Box]:
    store_order = {sid: i for i, sid in enumerate(store_ids)}
    return sorted(route_boxes, key=lambda b: (
        -store_order[b.store_id],  # 后送店优先（装货逆序）
        int(b.fragile),            # 非易碎优先
        -_volume(b),               # 体积降序
        b.id,                      # ID 稳定排序
    ))


def _size_desc_order(route_boxes: list[Box]) -> list[Box]:
    return sorted(route_boxes, key=lambda b: (-_volume(b), b.id))


def _fragile_last_order(route_boxes: list[Box], store_ids: list[str]) -> list[Box]:
    # 默认序基础上，同站易碎箱排到该站末尾
    ordered = _default_order(route_boxes, store_ids)
    return sorted(ordered, key=lambda b: (
        -{sid: i for i, sid in enumerate(store_ids)}[b.store_id],
        int(b.fragile),
        b.id,
    ))


def _box_too_large(box: Box, vehicle: Vehicle) -> bool:
    rots = [0, 90] if box.allow_rotate_xy else [0]
    return all(
        oriented_size(box, r)[0] > vehicle.length_mm
        or oriented_size(box, r)[1] > vehicle.width_mm
        or oriented_size(box, r)[2] > vehicle.height_mm
        for r in rots
    )


def _candidate_positions(box: Box, rot: int, placements: list[Placement],
                         boxes: dict[str, Box], vehicle: Vehicle
                         ) -> list[tuple[int, int, int]]:
    l, w, h = oriented_size(box, rot)
    xs = {0, vehicle.length_mm - l}
    ys = {0, vehicle.width_mm - w}
    zs = {0}

    for p in placements:
        pl, pw, ph = oriented_size(boxes[p.box_id], p.rotation_xy)
        xs.add(p.x_mm + pl)
        xs.add(p.x_mm - l)
        ys.add(p.y_mm + pw)
        ys.add(p.y_mm - w)
        zs.add(p.z_mm + ph)

    xs = [x for x in xs if 0 <= x <= vehicle.length_mm - l]
    ys = [y for y in ys if 0 <= y <= vehicle.width_mm - w]
    zs = [z for z in zs if 0 <= z <= vehicle.height_mm - h]

    candidates = [(x, y, z) for z in zs for x in xs for y in ys]
    # 低重心（z 小）、靠车头（x 大）、y 小
    candidates.sort(key=lambda c: (c[2], -c[0], c[1]))
    return candidates[:CANDIDATE_LIMIT]


def _can_place(box: Box, rot: int, x: int, y: int, z: int,
               placements: list[Placement], boxes: dict[str, Box],
               vehicle: Vehicle) -> bool:
    if not inside_vehicle(box, x, y, z, rot, vehicle):
        return False
    for p in placements:
        if intersects(box, x, y, z, rot, boxes[p.box_id],
                      p.x_mm, p.y_mm, p.z_mm, p.rotation_xy):
            return False
    if z != 0:
        support = find_support(box, x, y, z, rot, boxes, placements)
        if support is None or boxes[support.box_id].fragile:
            return False
    return True


def pack_route(request: SolveRequest, vehicle_id: str, store_ids: list[str],
               budget=None) -> PackResult:
    vehicle = next(v for v in request.vehicles if v.id == vehicle_id)
    boxes = {b.id: b for b in request.boxes}
    route_boxes = [b for b in request.boxes if b.store_id in store_ids]

    # 确证尺寸问题：单件所有朝向都超车厢
    for b in route_boxes:
        if _box_too_large(b, vehicle):
            return PackResult(
                success=False, reason_code="BOX_TOO_LARGE",
                message=f"箱 {b.id} 所有允许朝向均超过车厢尺寸")

    sortings = [
        _default_order(route_boxes, store_ids),
        _size_desc_order(route_boxes),
        _fragile_last_order(route_boxes, store_ids),
    ]
    # 去重排序（相邻相同则跳过）
    seen = set()
    attempts_total = 0
    last_reason = None

    for ordered in sortings:
        key = tuple(b.id for b in ordered)
        if key in seen:
            continue
        seen.add(key)

        if budget is not None and budget.expired():
            return PackResult(success=False, reason_code="TIME_LIMIT",
                              message="时间预算耗尽", candidate_attempts=attempts_total)

        placements: list[Placement] = []
        ok = True
        for box in ordered:
            if budget is not None and budget.expired():
                return PackResult(success=False, reason_code="TIME_LIMIT",
                                  message="时间预算耗尽", candidate_attempts=attempts_total)

            if budget is not None:
                budget.tick()
            placed = None
            for rot in ([0, 90] if box.allow_rotate_xy else [0]):
                cands = _candidate_positions(box, rot, placements, boxes, vehicle)
                for (x, y, z) in cands:
                    attempts_total += 1
                    if _can_place(box, rot, x, y, z, placements, boxes, vehicle):
                        placed = Placement(box_id=box.id, x_mm=x, y_mm=y,
                                           z_mm=z, rotation_xy=rot)
                        break
                if placed is not None:
                    break
            if placed is None:
                ok = False
                last_reason = f"箱 {box.id} 在当前排序下未找到可行位置"
                break
            placements.append(placed)

        if not ok:
            continue

        # 全放完：生成卸货并独立校验
        steps, error = generate_unload_steps(boxes, placements, store_ids)
        if error is not None:
            last_reason = f"卸货序列生成失败：{error.code}"
            continue

        violations = validate_vehicle_candidate(
            request, vehicle_id, store_ids, placements, steps)
        if violations:
            last_reason = f"独立校验未通过：{[v.code for v in violations]}"
            continue

        return PackResult(success=True, placements=placements,
                          unload_steps=steps, candidate_attempts=attempts_total)

    return PackResult(
        success=False, reason_code="SEARCH_EXHAUSTED",
        message=last_reason or "所有排序均未找到可行布局",
        candidate_attempts=attempts_total)
