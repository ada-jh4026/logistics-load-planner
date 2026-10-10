"""B14: 基于真实结果的解释与执行指引。

从 Result 的真实 metrics/unassigned/diagnostics 生成确定性文本摘要：
- 总体完成情况与费用/里程；
- 逐车服务门店、费用、利用率；
- 未配送原因（reason_code + message）；
- 装货逆序（= 卸货逆序）指引与模型限制。

只陈述事实，不编造收益（降本声明由 B15 实验对比产生，不属于本模块）；
没有实际修复日志就不声称发生过修复。
"""

from __future__ import annotations

from backend.models import Result, Route, SolveRequest


def loading_guide(route: Route) -> str:
    """单车的装货指引 = 卸货逆序。"""
    if not route.unload_steps:
        return f"车辆 {route.vehicle_id}：无箱件"
    order = list(reversed(route.unload_steps))
    seq = " → ".join(s.box_id for s in order)
    return f"车辆 {route.vehicle_id} 装货顺序（卸货逆序）：{seq}"


def generate_explanation(request: SolveRequest, result: Result) -> str:
    """从真实结果生成确定性文本解释。"""
    m = result.metrics
    vehicle_map = {v.id: v for v in request.vehicles}
    lines: list[str] = []

    # 总体
    lines.append(
        f"配送结果：{m.served_stores}/{m.total_stores} 家门店，"
        f"{m.served_boxes}/{m.total_boxes} 箱，"
        f"总费用 {m.total_cost:.2f} 元，总里程 {m.total_distance_km:.2f} km"
    )
    if m.volume_utilization is not None:
        lines.append(
            f"体积利用率 {m.volume_utilization:.1%}，"
            f"载重利用率 {m.weight_utilization:.1%}"
        )

    # 逐车
    for route in result.routes:
        v = vehicle_map[route.vehicle_id]
        lines.append(
            f"  {route.vehicle_id}（{v.length_mm}x{v.width_mm}x{v.height_mm}mm，"
            f"载重 {v.max_weight_kg:.0f}kg）：服务 {', '.join(route.store_ids)}，"
            f"费用 {route.cost:.2f} 元，里程 {route.distance_km:.2f} km"
        )
        lines.append("    " + loading_guide(route))

    # 未配送
    for u in result.unassigned:
        lines.append(
            f"  未配送 {u.store_id}（{len(u.box_ids)} 箱）："
            f"{u.reason_code} - {u.message}"
        )

    # 模型限制
    lines.append(
        "说明：几何装载为保守启发式，不保证数学最优；未找到布局不代表不可行。"
    )

    return "\n".join(lines)
