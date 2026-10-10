"""事实表（FactSheet）：从请求与响应确定性推导，模型只看这张表。

单车利用率、载重、等待与松弛时间都在这里按 request 重算，不信任响应里的任何合计。
字段结构见 AGENT_CONTRACT.md「FactSheet」。
"""
from __future__ import annotations

from typing import Any

from .schemas import JobResponse, SolveRequest


def _r(v: float | None, nd: int = 3) -> float | None:
    return None if v is None else round(float(v), nd)


def build_facts(req: SolveRequest, resp: JobResponse) -> dict[str, Any]:
    stores = {s.id: s for s in req.stores}
    boxes = {b.id: b for b in req.boxes}
    vehicles = {v.id: v for v in req.vehicles}
    result = resp.result

    facts: dict[str, Any] = {
        "case": {
            "case_id": req.case_id,
            "store_count": len(req.stores),
            "box_count": len(req.boxes),
            "vehicle_count": len(req.vehicles),
            "depot_departure_min": req.depot.departure_min,
        },
        "run": {
            "status": resp.status,
            "method": resp.method,
            "termination_reason": resp.termination_reason,
            "elapsed_ms": resp.elapsed_ms,
            "is_mock": resp.is_mock,
            "data_source": resp.data_source,
        },
        "metrics": result.metrics.model_dump() if result else None,
        "vehicles": [],
        "stops": [],
        "unassigned": [],
        "unload": [],
        "diagnostics_count": len(result.diagnostics) if result else 0,
    }
    if result is None:
        return facts

    for route in result.routes:
        v = vehicles.get(route.vehicle_id)
        cap_vol = (v.length_mm * v.width_mm * v.height_mm) if v else None
        loaded_vol = sum(boxes[b].length_mm * boxes[b].width_mm * boxes[b].height_mm for b in route.box_ids if b in boxes)
        loaded_w = sum(boxes[b].weight_kg for b in route.box_ids if b in boxes)
        facts["vehicles"].append(
            {
                "vehicle_id": route.vehicle_id,
                "store_ids": list(route.store_ids),
                "stop_count": len(route.store_ids),
                "box_count": len(route.box_ids),
                "distance_km": _r(route.distance_km),
                "cost": _r(route.cost),
                "fixed_cost": v.fixed_cost if v else None,
                "cost_per_km": v.cost_per_km if v else None,
                "return_min": _r(route.return_min),
                "volume_utilization": _r(loaded_vol / cap_vol) if cap_vol else None,
                "weight_utilization": _r(loaded_w / v.max_weight_kg) if v and v.max_weight_kg else None,
                "max_weight_kg": v.max_weight_kg if v else None,
                "loaded_weight_kg": _r(loaded_w),
                "fragile_box_count": sum(1 for b in route.box_ids if b in boxes and boxes[b].fragile),
            }
        )
        for stop in route.stops:
            s = stores.get(stop.store_id)
            facts["stops"].append(
                {
                    "vehicle_id": route.vehicle_id,
                    "store_id": stop.store_id,
                    "arrival_min": _r(stop.arrival_min),
                    "service_start_min": _r(stop.service_start_min),
                    "departure_min": _r(stop.departure_min),
                    "window_start_min": s.window_start_min if s else None,
                    "window_end_min": s.window_end_min if s else None,
                    "service_min": s.service_min if s else None,
                    "wait_min": _r(stop.service_start_min - stop.arrival_min),
                    "slack_min": _r(s.window_end_min - stop.service_start_min) if s else None,
                    "on_time": (stop.service_start_min <= s.window_end_min + 1e-6) if s else None,
                }
            )
        facts["unload"].append(
            {
                "vehicle_id": route.vehicle_id,
                "steps": [
                    {
                        "step": st.step,
                        "store_id": st.store_id,
                        "box_id": st.box_id,
                        "fragile": boxes[st.box_id].fragile if st.box_id in boxes else None,
                    }
                    for st in route.unload_steps
                ],
            }
        )

    for u in result.unassigned:
        facts["unassigned"].append(
            {
                "store_id": u.store_id,
                "box_count": len(u.box_ids),
                "box_ids": list(u.box_ids),
                "reason_code": u.reason_code,
                "message": u.message,
            }
        )
    return facts
