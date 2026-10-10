"""B07: 卸货序列生成与验证，装货逆序指引。

遵循 ALGORITHMS.md A3 卸货：
- 按路线依次处理门店，当站所有箱件卸完才能进入下一站；
- 每步在当站未卸箱中按 (z 降序, x 升序, id 升序) 找可取箱：
  1. 不存在仍由它承托的其他箱（否则 SUPPORT_DEPENDENCY）；
  2. 沿 -x 抽出不被阻挡（扫掠 x 区间 [0, x+L] 与箱体 y/z 区间，严格正交集）；
  3. 移除后剩余承托仍成立；
- 全部候选不可取则 UNLOAD_BLOCKED；后站箱件不临时搬出；
- 生成器与验证器分离；装货指引取卸货逆序并验证逐步放入。
"""

from __future__ import annotations

from backend.geometry import find_support, oriented_size
from backend.models import Box, Placement, UnloadStep, Vehicle, Violation


def _blocks_movement(target: Box, tx: int, ty: int, tz: int, trot: int,
                     other: Box, ox: int, oy: int, oz: int, orot: int) -> bool:
    """other 是否阻挡 target 沿 -x 抽出（或沿 +x 放入，扫掠区间相同）。"""
    tl, tw, th = oriented_size(target, trot)
    ol, ow, oh = oriented_size(other, orot)
    overlap_x = min(tx + tl, ox + ol) - max(0, ox) > 0
    overlap_y = min(ty + tw, oy + ow) - max(ty, oy) > 0
    overlap_z = min(tz + th, oz + oh) - max(tz, oz) > 0
    return overlap_x and overlap_y and overlap_z


def _supports_other(box_id: str, boxes: dict[str, Box],
                    others: list[Placement]) -> bool:
    """box_id 是否承托 any 其他箱（存在其他箱的承托恰指向它）。"""
    for other in others:
        if other.box_id == box_id:
            continue
        support = find_support(boxes[other.box_id], other.x_mm, other.y_mm,
                               other.z_mm, other.rotation_xy, boxes, others)
        if support is not None and support.box_id == box_id:
            return True
    return False


def generate_unload_steps(boxes: dict[str, Box], placements: list[Placement],
                          store_ids: list[str]):
    """生成卸货序列。返回 (steps, error)，error 为 None 表示成功。"""
    remaining: dict[str, Placement] = {p.box_id: p for p in placements}
    steps: list[UnloadStep] = []
    step_no = 1

    for sid in store_ids:
        while True:
            candidates = [p for bid, p in remaining.items()
                          if boxes[bid].store_id == sid]
            if not candidates:
                break

            candidates.sort(key=lambda p: (-p.z_mm, p.x_mm, p.box_id))
            others = list(remaining.values())

            picked = None
            for cand in candidates:
                box = boxes[cand.box_id]
                if _supports_other(cand.box_id, boxes, others):
                    continue
                blocked = any(
                    _blocks_movement(box, cand.x_mm, cand.y_mm, cand.z_mm,
                                     cand.rotation_xy,
                                     boxes[o.box_id], o.x_mm, o.y_mm, o.z_mm,
                                     o.rotation_xy)
                    for o in others if o.box_id != cand.box_id
                )
                if blocked:
                    continue
                picked = cand
                break

            if picked is None:
                return steps, Violation(
                    code="UNLOAD_BLOCKED",
                    store_id=sid,
                    message=f"门店 {sid} 无箱可取（阻挡或承托依赖）",
                )

            steps.append(UnloadStep(step=step_no, store_id=sid,
                                    box_id=picked.box_id))
            step_no += 1
            del remaining[picked.box_id]

    return steps, None


def validate_unload_steps(steps: list[UnloadStep], boxes: dict[str, Box],
                          placements: list[Placement],
                          store_ids: list[str]) -> list[Violation]:
    """独立验证给定卸货序列：次序、完整性、每步可取性。"""
    violations: list[Violation] = []
    remaining: dict[str, Placement] = {p.box_id: p for p in placements}
    store_index = {sid: i for i, sid in enumerate(store_ids)}
    last_index = -1

    for step in steps:
        idx = store_index.get(step.store_id, -1)
        if idx < 0:
            violations.append(Violation(
                code="STEP_MISMATCH", store_id=step.store_id,
                box_ids=[step.box_id],
                message=f"步骤引用了不在路线中的门店 {step.store_id}"))
            continue
        if idx < last_index:
            violations.append(Violation(
                code="STEP_MISMATCH", store_id=step.store_id,
                box_ids=[step.box_id],
                message="卸货步骤违反门店配送次序"))
        last_index = max(last_index, idx)

        if step.box_id not in remaining:
            violations.append(Violation(
                code="BOX_MISSING", box_ids=[step.box_id],
                message=f"箱 {step.box_id} 重复或不属于本车"))
            continue

        cand = remaining[step.box_id]
        if boxes[step.box_id].store_id != step.store_id:
            violations.append(Violation(
                code="STEP_MISMATCH", store_id=step.store_id,
                box_ids=[step.box_id],
                message=f"箱 {step.box_id} 不属于门店 {step.store_id}"))

        # 可取性：不承托其他 + 不被阻挡
        others = list(remaining.values())
        box = boxes[step.box_id]
        if _supports_other(step.box_id, boxes, others):
            violations.append(Violation(
                code="SUPPORT_DEPENDENCY", box_ids=[step.box_id],
                message=f"箱 {step.box_id} 仍承托其他箱，不可先卸"))
        if any(_blocks_movement(box, cand.x_mm, cand.y_mm, cand.z_mm,
                                cand.rotation_xy,
                                boxes[o.box_id], o.x_mm, o.y_mm, o.z_mm,
                                o.rotation_xy)
               for o in others if o.box_id != cand.box_id):
            violations.append(Violation(
                code="UNLOAD_BLOCKED", box_ids=[step.box_id],
                message=f"箱 {step.box_id} 抽出路径被阻挡"))

        del remaining[step.box_id]

    if remaining:
        violations.append(Violation(
            code="BOX_MISSING",
            box_ids=sorted(remaining.keys()),
            message=f"卸货序列遗漏箱件 {sorted(remaining.keys())}"))

    return violations


def generate_loading_steps(unload_steps: list[UnloadStep]) -> list[UnloadStep]:
    """装货指引 = 卸货逆序。"""
    return list(reversed(unload_steps))


def validate_loading_steps(loading_steps: list[UnloadStep],
                           boxes: dict[str, Box], placements: list[Placement],
                           vehicle: Vehicle) -> list[Violation]:
    """验证装货序：从空车起逐步沿 +x 放入，路径无阻挡且承托成立。"""
    violations: list[Violation] = []
    placed: dict[str, Placement] = {}
    pos_by_id = {p.box_id: p for p in placements}

    for step in loading_steps:
        box = boxes[step.box_id]
        target = pos_by_id[step.box_id]
        others = list(placed.values())

        # 放入路径（沿 +x）不被已放箱阻挡
        if any(_blocks_movement(box, target.x_mm, target.y_mm, target.z_mm,
                                target.rotation_xy,
                                boxes[o.box_id], o.x_mm, o.y_mm, o.z_mm,
                                o.rotation_xy)
               for o in others):
            violations.append(Violation(
                code="UNLOAD_BLOCKED", box_ids=[step.box_id],
                message=f"箱 {step.box_id} 放入路径被已放箱阻挡"))

        # 放入后承托成立
        if target.z_mm != 0:
            support = find_support(box, target.x_mm, target.y_mm, target.z_mm,
                                   target.rotation_xy, boxes, others)
            if support is None:
                violations.append(Violation(
                    code="UNSUPPORTED", box_ids=[step.box_id],
                    message=f"箱 {step.box_id} 放入时无承托（承托箱尚未放入）"))

        placed[step.box_id] = target

    return violations
