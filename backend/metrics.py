"""B04: 指标纯函数。

遵循 EVALUATION.md「固定公式」：
- completion_rate = served_stores / total_stores；
- on_time_rate = 已服务且 service_start<=window_end 的门店数 / served_stores，零服务为 null；
- total_distance_km = 所有已服务路线「仓库→各店→仓库」距离之和；
- total_cost = 各已用车 fixed_cost + cost_per_km*该车距离 之和；
- volume_utilization = 已服务箱总体积 / 已用车总体积；
  weight_utilization = 已服务箱总重量 / 已用车总载重；
  零使用车辆时两者为 null；不得把未使用车辆计入分母。
"""

from __future__ import annotations

from backend.models import Metrics, Route, SolveRequest
from backend.network import EPS


def compute_metrics(request: SolveRequest, routes: list[Route],
                    unassigned) -> Metrics:
    """从 routes 重新计算指标（不信任调用方传入的 metrics 字段）。

    unassigned 保留以便后续完整性校验（B08）；指标本身只由 routes 与
    request 推导，避免重复计算口径漂移。
    """
    stores = {s.id: s for s in request.stores}
    vehicles = {v.id: v for v in request.vehicles}
    boxes = {b.id: b for b in request.boxes}

    served_store_ids: set[str] = set()
    served_box_ids: list[str] = []
    for route in routes:
        served_store_ids.update(route.store_ids)
        served_box_ids.extend(route.box_ids)

    total_stores = len(request.stores)
    total_boxes = len(request.boxes)
    served_stores = len(served_store_ids)
    served_boxes = len(served_box_ids)
    completion_rate = served_stores / total_stores if total_stores else 0.0

    used_vehicles = len(routes)
    total_distance_km = sum(r.distance_km for r in routes)

    total_cost = 0.0
    for route in routes:
        v = vehicles[route.vehicle_id]
        total_cost += v.fixed_cost + v.cost_per_km * route.distance_km

    # 准时率：已服务且 service_start <= window_end 的门店数 / served_stores
    if served_stores == 0:
        on_time_rate = None
    else:
        on_time = 0
        for route in routes:
            for stop in route.stops:
                if stop.service_start_min - stores[stop.store_id].window_end_min <= EPS:
                    on_time += 1
        on_time_rate = on_time / served_stores

    # 利用率分母仅含已用车
    if used_vehicles == 0:
        volume_utilization = None
        weight_utilization = None
    else:
        served_volume = sum(
            boxes[bid].length_mm * boxes[bid].width_mm * boxes[bid].height_mm
            for bid in served_box_ids
        )
        used_volume = sum(
            vehicles[r.vehicle_id].length_mm
            * vehicles[r.vehicle_id].width_mm
            * vehicles[r.vehicle_id].height_mm
            for r in routes
        )
        volume_utilization = served_volume / used_volume

        served_weight = sum(boxes[bid].weight_kg for bid in served_box_ids)
        used_capacity = sum(vehicles[r.vehicle_id].max_weight_kg for r in routes)
        weight_utilization = served_weight / used_capacity

    return Metrics(
        total_stores=total_stores,
        served_stores=served_stores,
        total_boxes=total_boxes,
        served_boxes=served_boxes,
        completion_rate=completion_rate,
        used_vehicles=used_vehicles,
        total_distance_km=total_distance_km,
        total_cost=total_cost,
        on_time_rate=on_time_rate,
        volume_utilization=volume_utilization,
        weight_utilization=weight_utilization,
        unload_block_count=0,
    )
