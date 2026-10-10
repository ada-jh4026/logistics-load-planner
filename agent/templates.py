"""模板模式解释：只用事实表，确定性输出中文 Markdown。无模型密钥或模型输出不合格时使用。"""
from __future__ import annotations

from typing import Any

from .schemas import Focus

REASON_LABEL = {
    "BOX_TOO_LARGE": "箱件尺寸超过所有车厢",
    "CAPACITY_LIMIT": "载重或容量不足",
    "TIME_WINDOW": "时间窗无法满足",
    "SEARCH_EXHAUSTED": "在搜索范围内未找到可行装载",
    "TIME_LIMIT": "求解时间预算用尽",
}
STATUS_WORD = {"succeeded": "全部配送", "partial": "部分配送", "failed": "求解失败", "queued": "排队中", "running": "计算中"}
METHOD_WORD = {"greedy": "简单贪心基线", "sequential": "先路线后装载（不反馈）", "coupled": "配载与路线协同"}
TERM_WORD = {"completed": "搜索完成", "time_limit": "达到时间预算", "iteration_limit": "达到迭代上限", "internal_error": "内部错误"}


def hhmm(m: float | None) -> str:
    if m is None:
        return "—"
    t = int(round(m))
    return f"{(t // 60) % 24:02d}:{t % 60:02d}"


def pct(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def n1(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.1f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else f"{int(round(v))}"


def render(facts: dict[str, Any], focus: Focus, vehicle_id: str | None = None) -> str:
    if focus == "overview":
        return _overview(facts)
    if focus == "unassigned":
        return _unassigned(facts)
    if focus == "unload":
        return _unload(facts, vehicle_id)
    if focus == "vehicle":
        return _vehicle(facts, vehicle_id)
    raise ValueError(focus)


def _overview(f: dict[str, Any]) -> str:
    m = f["metrics"]
    run = f["run"]
    lines = [
        f"**{STATUS_WORD.get(run['status'], run['status'])}**，方法：{METHOD_WORD.get(run['method'], run['method'])}"
        + (f"，{TERM_WORD.get(run['termination_reason'], run['termination_reason'])}" if run.get("termination_reason") else "")
        + "。",
        "",
        f"- 配送门店 {m['served_stores']} / {m['total_stores']}（完成率 {pct(m['completion_rate'])}），配送箱件 {m['served_boxes']} / {m['total_boxes']}。",
        f"- 启用车辆 {m['used_vehicles']} 辆，总里程 {n1(m['total_distance_km'])} km，总费用 {n1(m['total_cost'])} 元。",
        f"- 准时率 {pct(m['on_time_rate'])}，体积利用率 {pct(m['volume_utilization'])}，载重利用率 {pct(m['weight_utilization'])}，卸货阻挡 {m['unload_block_count']} 处。",
    ]
    for v in f["vehicles"]:
        lines.append(
            f"- {v['vehicle_id']}：{v['stop_count']} 站（{' → '.join(v['store_ids'])}），{v['box_count']} 箱，"
            f"里程 {n1(v['distance_km'])} km，费用 {n1(v['cost'])} 元，{hhmm(v['return_min'])} 回仓，"
            f"体积利用率 {pct(v['volume_utilization'])}，载重 {n1(v['loaded_weight_kg'])} / {n1(v['max_weight_kg'])} kg。"
        )
    waits = [s for s in f["stops"] if (s["wait_min"] or 0) > 0.5]
    for s in waits:
        lines.append(f"- {s['vehicle_id']} 到 {s['store_id']} 于 {hhmm(s['arrival_min'])} 到达，早于时间窗 {hhmm(s['window_start_min'])}，等待 {n1(s['wait_min'])} 分钟。")
    if f["unassigned"]:
        lines.append("")
        lines.append(_unassigned(f))
    lines.append("")
    lines.append("里程与时刻按平面直线距离和固定车速换算，不是真实道路测算。")
    return "\n".join(lines)


def _unassigned(f: dict[str, Any]) -> str:
    if not f["unassigned"]:
        return "所有门店都已安排配送，没有未配送门店。"
    lines = [f"未配送门店 {len(f['unassigned'])} 家："]
    for u in f["unassigned"]:
        lines.append(f"- {u['store_id']}（{u['box_count']} 箱）：{REASON_LABEL.get(u['reason_code'], u['reason_code'])}。{u['message']}")
    lines.append("")
    lines.append("这些门店的箱件全部回到未分配池，不计入完成率；需要调整车辆、时间窗或箱件约束后重新求解。")
    return "\n".join(lines)


def _vehicle(f: dict[str, Any], vehicle_id: str | None) -> str:
    v = next((x for x in f["vehicles"] if x["vehicle_id"] == vehicle_id), None)
    if v is None:
        return f"车辆 {vehicle_id} 没有被启用，车厢为空。"
    lines = [
        f"**{v['vehicle_id']}**：{v['stop_count']} 站，{v['box_count']} 箱，{hhmm(v['return_min'])} 回仓。",
        f"- 费用 {n1(v['fixed_cost'])} + {n1(v['cost_per_km'])} × {n1(v['distance_km'])} = {n1(v['cost'])} 元。",
        f"- 载重 {n1(v['loaded_weight_kg'])} / {n1(v['max_weight_kg'])} kg（{pct(v['weight_utilization'])}），体积利用率 {pct(v['volume_utilization'])}。",
    ]
    for i, s in enumerate([s for s in f["stops"] if s["vehicle_id"] == v["vehicle_id"]], 1):
        wait = f"，等待 {n1(s['wait_min'])} 分钟" if (s["wait_min"] or 0) > 0.5 else ""
        lines.append(
            f"- 第 {i} 站 {s['store_id']}：{hhmm(s['arrival_min'])} 到达，{hhmm(s['service_start_min'])} 开始，时间窗 {hhmm(s['window_start_min'])}–{hhmm(s['window_end_min'])}{wait}。"
        )
    return "\n".join(lines)


def _unload(f: dict[str, Any], vehicle_id: str | None) -> str:
    groups = [g for g in f["unload"] if vehicle_id is None or g["vehicle_id"] == vehicle_id]
    if not groups:
        return f"车辆 {vehicle_id} 没有卸货步骤。"
    lines = ["现场装卸作业单", ""]
    for g in groups:
        lines.append(f"**{g['vehicle_id']}**")
        current_store = None
        for st in g["steps"]:
            if st["store_id"] != current_store:
                current_store = st["store_id"]
                lines.append(f"到站 {current_store}：")
            tag = "（易碎，轻拿轻放，顶面不得承载）" if st.get("fragile") else ""
            lines.append(f"{st['step']}. 从后门取出 {st['box_id']}{tag}")
        lines.append("")
    lines.append("规则：每站卸完全部箱件再前往下一站；先取上层箱，再取被它压住的底箱；箱件沿后门方向水平抽出，不穿过其他箱件。")
    lines.append("装货按上述步骤的逆序进行：最后卸的箱件最先装、靠车头放置；最先卸的箱件最后装、靠后门放置。")
    return "\n".join(lines)
