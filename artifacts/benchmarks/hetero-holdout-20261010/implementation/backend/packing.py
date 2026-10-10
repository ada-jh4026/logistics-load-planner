"""B09: 确定性 3D 配载启发式。

遵循 ALGORITHMS.md A6：
- 箱件按目的站逆配送序、非易碎优先、体积降序、ID 排序（默认排序）；
- 允许每箱两种水平朝向（0/90，受 allow_rotate_xy 约束）；
- 候选位置由地板角、靠车头及已放箱边界生成（x/y 边界与 z 顶面），
  剪掉越界、去重、过滤碰撞/承托/易碎，按「低重心、靠车头」评分选取；
- 候选数量设上限并记录，算法不完备，失败只表示没找到；
- 异构箱先尝试按站分区/逐件可装入的构造，再回退原 3 种稳定排序；
  全放完均模拟卸货并独立校验，候选枚举中检查预算。

失败区分：单件所有朝向均超车厢 → BOX_TOO_LARGE；否则 SEARCH_EXHAUSTED。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import islice

from backend.geometry import find_support, inside_vehicle, intersects, oriented_size
from backend.models import Box, Placement, SolveRequest, UnloadStep, Vehicle
from backend.unloading import generate_unload_steps, _blocks_movement
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
                         boxes: dict[str, Box], vehicle: Vehicle, *, aligned: bool = False,
                         depth_first: bool = False
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
        if aligned:
            # Unequal cartons need support-face alignment, not just adjacency.
            xs.update((p.x_mm, p.x_mm + pl - l))
            ys.update((p.y_mm, p.y_mm + pw - w))
        zs.add(p.z_mm + ph)

    xs = sorted((x for x in xs if 0 <= x <= vehicle.length_mm - l), reverse=True)
    ys = sorted(y for y in ys if 0 <= y <= vehicle.width_mm - w)
    zs = sorted(z for z in zs if 0 <= z <= vehicle.height_mm - h)
    # Generate in score order rather than materializing/sorting a potentially
    # enormous Cartesian product just to retain its first 2,000 points.
    candidates = ((x, y, z) for x in xs for z in zs for y in ys) if depth_first else (
        (x, y, z) for z in zs for x in xs for y in ys)
    return list(islice(candidates, CANDIDATE_LIMIT))


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


def _construct_accessible(request: SolveRequest, vehicle: Vehicle,
                          store_ids: list[str], boxes: dict[str, Box],
                          budget, *, segmented: bool, footprint: bool) -> PackResult:
    """Build in reverse delivery order, proving an insertion path at each step.

    Segmented mode closes a longitudinal slab after each stop. The shared-space
    variant also permits legal stacking across stops. Both retain the existing
    single-box support constraint and independently validate the finished layout.
    """
    placements: list[Placement] = []
    attempts = 0
    ceiling = vehicle.length_mm
    for sid in reversed(store_ids):
        group = sorted((b for b in request.boxes if b.store_id == sid), key=lambda b: (
            b.fragile, -(b.length_mm * b.width_mm if footprint else _volume(b)),
            -b.height_mm, b.id))
        region = vehicle.model_copy(update={"length_mm": ceiling}) if segmented else vehicle
        group_placements: list[Placement] = []
        for box in group:
            if budget is not None:
                if budget.expired():
                    return PackResult(False, reason_code="TIME_LIMIT",
                                      message="配载预算耗尽", candidate_attempts=attempts)
                budget.tick()
            existing = group_placements if segmented else placements
            old_left = min((p.x_mm for p in existing), default=region.length_mm)
            candidates = []
            for rot in ([0, 90] if box.allow_rotate_xy else [0]):
                for x, y, z in _candidate_positions(box, rot, existing, boxes, region,
                                                    aligned=True, depth_first=True):
                    # Fill an existing wall before consuming more vehicle length.
                    candidates.append(((region.length_mm - min(old_left, x), z, y, -x, rot),
                                       rot, x, y, z))
            placed = None
            for _, rot, x, y, z in sorted(candidates)[:CANDIDATE_LIMIT]:
                attempts += 1
                if attempts % 64 == 0 and budget is not None and budget.expired():
                    return PackResult(False, reason_code="TIME_LIMIT",
                                      message="配载预算耗尽", candidate_attempts=attempts)
                if not _can_place(box, rot, x, y, z, existing, boxes, region):
                    continue
                # Each box can physically enter now; reversing these operations
                # unloads the earlier stop first without moving later-stop cargo.
                if any(_blocks_movement(box, x, y, z, rot, boxes[p.box_id],
                                        p.x_mm, p.y_mm, p.z_mm, p.rotation_xy)
                       for p in existing):
                    continue
                placed = Placement(box_id=box.id, x_mm=x, y_mm=y,
                                   z_mm=z, rotation_xy=rot)
                break
            if placed is None:
                return PackResult(False, reason_code="SEARCH_EXHAUSTED",
                                  message=f"卸货感知布局未找到箱 {box.id} 的位置",
                                  candidate_attempts=attempts)
            group_placements.append(placed)
            placements.append(placed)
        if segmented and group_placements:
            ceiling = min(p.x_mm for p in group_placements)
    steps, error = generate_unload_steps(boxes, placements, store_ids)
    if error is not None:
        return PackResult(False, reason_code="SEARCH_EXHAUSTED",
                          message=f"卸货感知布局校验失败：{error.code}", candidate_attempts=attempts)
    violations = validate_vehicle_candidate(request, vehicle.id, store_ids, placements, steps)
    if violations:
        return PackResult(False, reason_code="SEARCH_EXHAUSTED",
                          message=f"独立校验未通过：{[v.code for v in violations]}",
                          candidate_attempts=attempts)
    return PackResult(True, placements=placements, unload_steps=steps, candidate_attempts=attempts)


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

    attempts_total = 0
    heterogeneous = len({(b.length_mm, b.width_mm, b.height_mm) for b in route_boxes}) > 1
    if heterogeneous:
        for segmented, footprint in ((True, True), (False, True), (False, False)):
            constructed = _construct_accessible(request, vehicle, store_ids, boxes,
                                                 budget, segmented=segmented,
                                                 footprint=footprint)
            attempts_total += constructed.candidate_attempts
            if constructed.success or constructed.reason_code == "TIME_LIMIT":
                constructed.candidate_attempts = attempts_total
                return constructed

    sortings = [
        _default_order(route_boxes, store_ids),
        _size_desc_order(route_boxes),
        _fragile_last_order(route_boxes, store_ids),
    ]
    # 去重排序（相邻相同则跳过）
    seen = set()
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
                    if attempts_total % 64 == 0 and budget is not None and budget.expired():
                        return PackResult(False, reason_code="TIME_LIMIT",
                                          message="配载预算耗尽", candidate_attempts=attempts_total)
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
