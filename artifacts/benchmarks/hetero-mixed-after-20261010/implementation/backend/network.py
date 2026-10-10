"""B04: 距离、时效纯函数。

遵循 CONTRACT.md「网络模型和时效」：
- distance(a,b)=sqrt((xa-xb)^2+(ya-yb)^2)，分钟=distance/speed*60，不提前四舍五入；
- 第一站 arrival=departure+travel；service_start=max(arrival,window_start)；
  departure=service_start+service_min；
- service_start<=window_end 才合格（浮点容差 1e-6）；
- 回仓计里程与时间，不另设回仓截止。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from backend.models import SolveRequest, Stop, Violation

EPS = 1e-6


def distance_km(ax: float, ay: float, bx: float, by: float) -> float:
    """两点欧氏距离（km）。"""
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


def travel_min(km: float, speed_kmph: float) -> float:
    """行驶时长（分钟），不提前四舍五入。"""
    return km / speed_kmph * 60.0


@dataclass
class RouteSchedule:
    vehicle_id: str
    stops: list[Stop] = field(default_factory=list)
    return_min: float = 0.0
    distance_km: float = 0.0
    violations: list[Violation] = field(default_factory=list)


def schedule_route(request: SolveRequest, vehicle_id: str,
                   store_ids: list[str]) -> RouteSchedule:
    """按给定门店顺序排时刻：包含等待、服务与回仓，并报告时间窗违规。

    不修改 request；仅依据车辆无关的行驶速度与门店时间窗计算。
    """
    depot = request.depot
    stores = {s.id: s for s in request.stores}
    speed = request.options.speed_kmph

    sched = RouteSchedule(vehicle_id=vehicle_id)
    prev_x, prev_y = depot.x_km, depot.y_km
    clock = depot.departure_min

    for sid in store_ids:
        store = stores[sid]
        d = distance_km(prev_x, prev_y, store.x_km, store.y_km)
        sched.distance_km += d
        clock += travel_min(d, speed)
        arrival = clock
        service_start = max(arrival, store.window_start_min)
        departure = service_start + store.service_min
        sched.stops.append(Stop(
            store_id=sid,
            arrival_min=arrival,
            service_start_min=service_start,
            departure_min=departure,
        ))
        if service_start - store.window_end_min > EPS:
            sched.violations.append(Violation(
                code="TIME_WINDOW",
                store_id=sid,
                message=(
                    f"门店 {sid} 服务开始 {service_start} "
                    f"晚于窗口结束 {store.window_end_min}"
                ),
            ))
        clock = departure
        prev_x, prev_y = store.x_km, store.y_km

    # 回仓
    d_back = distance_km(prev_x, prev_y, depot.x_km, depot.y_km)
    sched.distance_km += d_back
    sched.return_min = clock + travel_min(d_back, speed)

    return sched
