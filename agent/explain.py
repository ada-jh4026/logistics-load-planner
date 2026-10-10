"""解释生成：事实表 → （模型 + 数字核对 | 模板）。"""
from __future__ import annotations

import json
import logging

from .facts import build_facts
from .grounding import check_grounding
from .llm import LLM, NullLLM
from .schemas import ExplainRequest, ExplainResponse, Grounding
from .templates import render

log = logging.getLogger("agent.explain")

SYSTEM_PROMPT = """你是城市配送调度员的助手。你只能根据给定的「事实表」说话。
规则：
1. 文中出现的每一个数字（费用、里程、利用率、时刻、件数、分钟）都必须直接来自事实表，可以四舍五入到 1 位小数，不得推算或臆造新的数字。
2. 不要给出任何坐标、路线顺序或装载位置的修改建议；你不做调度决策。
3. 时刻用 HH:MM，分钟数用「N 分钟」，利用率用百分数。
4. 用中文 Markdown，先结论后要点，不超过 220 字；语气平实，不夸大收益。
5. 如果事实表里有未配送门店，必须逐一说明门店与原因码对应的含义。
6. 协同修复只能依据事实表 repair 字段：repair 为 null 时写「此记录未提供修复过程」；status 为 not_needed 时只能说「未触发修复」，不得说修复带来了任何收益；不得把 rejected 的尝试说成已采用；same_served_set 为 false 时不得给出费用变化百分比。"""

FOCUS_HINT = {
    "overview": "请概述本次方案：完成情况、启用车辆、费用与里程、利用率、等待情况、未配送门店及原因；若 repair 字段存在且 status 不是 not_needed，用一两句说明发现了什么冲突、采用了几次搬移、可执行门店从多少变到多少。",
    "unassigned": "请只解释未配送门店：每家门店的原因、这意味着什么、调度员可以从哪些约束入手（时间窗、车辆、箱件标记），不要给具体数值建议。",
    "unload": "请把 unload 中的步骤改写成给现场装卸工的作业单：按车辆、按到站顺序逐步列出，标注易碎箱注意事项；最后说明装货按卸货逆序进行。不要改变步骤顺序。",
    "vehicle": "请只说明指定车辆的行程：各站到达/开始时刻、时间窗、等待、费用构成、载重与体积利用率。",
}


def explain(req: ExplainRequest, llm: LLM) -> ExplainResponse:
    facts = build_facts(req.request, req.response)
    template_text = render(facts, req.focus, req.vehicle_id)
    warnings: list[str] = []

    if isinstance(llm, NullLLM):
        return _template(facts, template_text, ["未配置模型密钥，使用模板模式。"])

    user = _user_prompt(req, facts)
    try:
        text = llm.complete(SYSTEM_PROMPT, user)
        checked, unmatched = check_grounding(text, facts)
        if unmatched:
            retry = user + "\n\n上一版回答里这些数字在事实表中找不到：" + "、".join(unmatched) + "。请只使用事实表中的数字重写。"
            text2 = llm.complete(SYSTEM_PROMPT, retry)
            checked2, unmatched2 = check_grounding(text2, facts)
            if unmatched2:
                warnings.append("模型输出两次数字核对均未通过，已回退模板。未匹配：" + "、".join(unmatched2))
                return _template(facts, template_text, warnings, checked2, unmatched2)
            warnings.append("首轮输出有未匹配数字（" + "、".join(unmatched) + "），重试后通过。")
            text, checked = text2, checked2
        return ExplainResponse(
            mode="llm",
            model=llm.model,
            warnings=warnings,
            text=text,
            facts=facts,
            grounding=Grounding(checked_numbers=checked, unmatched_numbers=[], passed=True),
        )
    except Exception as e:  # 模型侧任何问题都回退
        log.warning("llm failed, fallback to template: %s", e)
        return _template(facts, template_text, [f"模型调用失败（{type(e).__name__}），使用模板模式。"])


def _template(facts, text: str, warnings: list[str], checked: int | None = None, unmatched: list[str] | None = None) -> ExplainResponse:
    c, u = check_grounding(text, facts)
    return ExplainResponse(
        mode="template",
        model=None,
        warnings=warnings,
        text=text,
        facts=facts,
        grounding=Grounding(checked_numbers=checked if checked is not None else c, unmatched_numbers=unmatched or [], passed=not (unmatched or u)),
    )


def _user_prompt(req: ExplainRequest, facts) -> str:
    parts = [FOCUS_HINT[req.focus]]
    if req.focus == "vehicle":
        parts.append(f"指定车辆：{req.vehicle_id}")
    if req.question:
        parts.append(f"调度员的问题：{req.question}")
    parts.append("事实表（JSON）：")
    parts.append(json.dumps(facts, ensure_ascii=False))
    return "\n".join(parts)
