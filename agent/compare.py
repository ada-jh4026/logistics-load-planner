"""两次方案对比：指标差值、可比性判定（EVALUATION 口径）、叙述文本（模型 + 核对 | 模板）。"""
from __future__ import annotations

import json
import logging
from typing import Any

from .facts import build_facts
from .grounding import check_grounding
from .llm import LLM, NullLLM
from .schemas import CompareRequest, CompareResponse, Grounding, MetricDelta
from .templates import METHOD_WORD, STATUS_WORD, n1, pct

log = logging.getLogger("agent.compare")

METRIC_FIELDS = [
    "total_stores", "served_stores", "total_boxes", "served_boxes", "completion_rate",
    "used_vehicles", "total_distance_km", "total_cost", "on_time_rate",
    "volume_utilization", "weight_utilization", "unload_block_count",
]
METRIC_LABEL = {
    "served_stores": "配送门店", "served_boxes": "配送箱件", "completion_rate": "完成率",
    "used_vehicles": "启用车辆", "total_distance_km": "总里程", "total_cost": "总费用",
    "on_time_rate": "准时率", "volume_utilization": "体积利用率", "weight_utilization": "载重利用率",
    "unload_block_count": "卸货阻挡",
}

SYSTEM_PROMPT = """你是城市配送调度员的助手，负责比较「基线方案」和「候选方案」。只能使用给定事实表里的数字。
规则：
1. 先说服务覆盖的变化（配送门店数、未配送门店变化），再说费用与车辆。
2. 只有当 comparable_cost 为 true 时才可以说费用变化百分比（用 cost_change_rate）；否则明确写「两方案服务的门店集合不同，费用不可直接比较」，不得给任何降本或增本百分比。
3. 数字可四舍五入到 1 位小数；不要推算新的数字。不给调度建议。
4. 中文 Markdown，不超过 200 字。"""


def compare(req: CompareRequest, llm: LLM) -> CompareResponse:
    fb = build_facts(req.baseline.request, req.baseline.response)
    fc = build_facts(req.candidate.request, req.candidate.response)
    mb, mc = fb["metrics"], fc["metrics"]
    warnings: list[str] = []

    deltas: dict[str, MetricDelta] = {}
    for k in METRIC_FIELDS:
        b = mb.get(k) if mb else None
        c = mc.get(k) if mc else None
        d = (c - b) if (b is not None and c is not None) else None
        deltas[k] = MetricDelta(baseline=b, candidate=c, delta=d)

    served_b = {v["store_id"] for v in _served(fb)}
    served_c = {v["store_id"] for v in _served(fc)}
    same_served = served_b == served_c
    both_valid = bool(req.baseline.response.result and req.baseline.response.result.validation.valid and req.candidate.response.result and req.candidate.response.result.validation.valid)
    comparable = bool(same_served and both_valid and mb and mc and mb["total_cost"] > 0)
    rate = ((mc["total_cost"] - mb["total_cost"]) / mb["total_cost"]) if comparable else None

    facts: dict[str, Any] = {
        "baseline": {"run": fb["run"], "metrics": mb, "served_store_ids": sorted(served_b), "unassigned": fb["unassigned"], "vehicles": fb["vehicles"]},
        "candidate": {"run": fc["run"], "metrics": mc, "served_store_ids": sorted(served_c), "unassigned": fc["unassigned"], "vehicles": fc["vehicles"]},
        "deltas": {k: v.model_dump() for k, v in deltas.items()},
        "same_served_set": same_served,
        "both_valid": both_valid,
        "comparable_cost": comparable,
        "cost_change_rate": rate,
        "newly_served": sorted(served_c - served_b),
        "newly_unserved": sorted(served_b - served_c),
        "instruction": req.instruction,
    }
    template_text = _template_text(facts)

    if isinstance(llm, NullLLM):
        return _resp(facts, deltas, template_text, ["未配置模型密钥，使用模板模式。"], mode="template", model=None)

    user = ("调度员说明：" + req.instruction + "\n" if req.instruction else "") + "事实表（JSON）：\n" + json.dumps(facts, ensure_ascii=False)
    try:
        text = llm.complete(SYSTEM_PROMPT, user)
        checked, unmatched = check_grounding(text, facts)
        if unmatched or (not comparable and _mentions_percent_change(text)):
            retry = user + "\n\n上一版回答不合格：" + ("未匹配数字 " + "、".join(unmatched) + "；" if unmatched else "") + ("不可比时不得给费用变化百分比；" if not comparable else "") + "请重写。"
            text2 = llm.complete(SYSTEM_PROMPT, retry)
            checked2, unmatched2 = check_grounding(text2, facts)
            if unmatched2 or (not comparable and _mentions_percent_change(text2)):
                warnings.append("模型输出两次均未通过核对，已回退模板。" + ("未匹配：" + "、".join(unmatched2) if unmatched2 else "不可比却给出费用百分比。"))
                return _resp(facts, deltas, template_text, warnings, mode="template", model=None)
            warnings.append("首轮输出未通过核对，重试后通过。")
            text, checked = text2, checked2
        return _resp(facts, deltas, text, warnings, mode="llm", model=llm.model, grounding=Grounding(checked_numbers=checked, unmatched_numbers=[], passed=True))
    except Exception as e:
        log.warning("llm compare failed: %s", e)
        return _resp(facts, deltas, template_text, [f"模型调用失败（{type(e).__name__}），使用模板模式。"], mode="template", model=None)


def _served(f: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"store_id": sid} for v in f["vehicles"] for sid in v["store_ids"]]


def _mentions_percent_change(text: str) -> bool:
    import re
    return re.search(r"(费用|成本|降本|节省|增加|上升|下降|降低)[^。\n]{0,12}\d+(?:\.\d+)?\s*%", text) is not None


def _resp(facts, deltas, text, warnings, *, mode, model, grounding: Grounding | None = None) -> CompareResponse:
    if grounding is None:
        c, u = check_grounding(text, facts)
        grounding = Grounding(checked_numbers=c, unmatched_numbers=u, passed=not u)
    return CompareResponse(
        mode=mode, model=model, warnings=warnings, deltas=deltas,
        same_served_set=facts["same_served_set"], both_valid=facts["both_valid"],
        comparable_cost=facts["comparable_cost"], cost_change_rate=facts["cost_change_rate"],
        text=text, grounding=grounding,
    )


def _template_text(f: dict[str, Any]) -> str:
    b, c = f["baseline"], f["candidate"]
    mb, mc = b["metrics"], c["metrics"]
    lines = [
        f"基线：{STATUS_WORD.get(b['run']['status'], b['run']['status'])}（{METHOD_WORD.get(b['run']['method'], b['run']['method'])}），配送门店 {mb['served_stores']} / {mb['total_stores']}，启用车辆 {mb['used_vehicles']} 辆，总费用 {n1(mb['total_cost'])} 元，总里程 {n1(mb['total_distance_km'])} km。",
        f"候选：{STATUS_WORD.get(c['run']['status'], c['run']['status'])}（{METHOD_WORD.get(c['run']['method'], c['run']['method'])}），配送门店 {mc['served_stores']} / {mc['total_stores']}，启用车辆 {mc['used_vehicles']} 辆，总费用 {n1(mc['total_cost'])} 元，总里程 {n1(mc['total_distance_km'])} km。",
        "",
    ]
    if f["newly_served"]:
        lines.append(f"- 候选方案新增配送门店：{'、'.join(f['newly_served'])}。")
    if f["newly_unserved"]:
        lines.append(f"- 候选方案不再配送门店：{'、'.join(f['newly_unserved'])}。")
    if not f["same_served_set"]:
        lines.append("- 两方案服务的门店集合不同，费用不可直接比较；先看覆盖变化。")
    elif not f["both_valid"]:
        lines.append("- 至少一方未通过独立校验，费用不可比较。")
    elif f["comparable_cost"]:
        r = f["cost_change_rate"]
        word = "下降" if r < 0 else "上升" if r > 0 else "不变"
        lines.append(f"- 服务门店集合相同且均通过校验：总费用由 {n1(mb['total_cost'])} 元变为 {n1(mc['total_cost'])} 元，{word} {abs(r) * 100:.1f}%。")
    for k in ("used_vehicles", "total_distance_km", "volume_utilization", "weight_utilization", "on_time_rate", "unload_block_count"):
        d = f["deltas"][k]
        if d["delta"] is None or abs(d["delta"]) < 1e-9:
            continue
        if k in ("volume_utilization", "weight_utilization", "on_time_rate"):
            lines.append(f"- {METRIC_LABEL[k]}：{pct(d['baseline'])} → {pct(d['candidate'])}。")
        else:
            lines.append(f"- {METRIC_LABEL[k]}：{n1(d['baseline'])} → {n1(d['candidate'])}。")
    lines.append("")
    lines.append("以上为模拟数据上的对比，不代表真实企业收益。")
    return "\n".join(lines)
