"""B12: 协同修复候选生成（A7）。

为失败的路线生成有限修复候选：把冲突门店移到其他已有车的最佳可行插入位，
或移到未使用车辆。候选仅做结构生成，可行性由 solver 重新 pack + 校验确认。
"""

from __future__ import annotations

from backend.models import SolveRequest, Vehicle


def relocation_candidates(request: SolveRequest, store_id: str,
                          current_routes: list[tuple[str, list[str]]],
                          ) -> list[tuple[str, list[str]]]:
    """生成把 store_id 移到其他车的候选 (vehicle_id, new_store_ids)。

    current_routes 是 [(vehicle_id, store_ids)] 的已有路线列表。
    """
    candidates: list[tuple[str, list[str]]] = []
    used = {vid for vid, _ in current_routes}

    # 移到已有车的每个插入位置
    for vid, store_ids in current_routes:
        for pos in range(len(store_ids) + 1):
            new_ids = store_ids[:pos] + [store_id] + store_ids[pos:]
            candidates.append((vid, new_ids))

    # 移到未使用车辆（新路线）
    for v in sorted(request.vehicles, key=lambda v: v.id):
        if v.id not in used:
            candidates.append((v.id, [store_id]))

    return candidates
