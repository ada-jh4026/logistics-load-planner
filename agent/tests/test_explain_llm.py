from agent.explain import explain
from agent.llm import FakeLLM
from agent.schemas import ExplainRequest


def _req(req_partial, resp_partial, **kw):
    return ExplainRequest(schema_version="0.1", request=req_partial, response=resp_partial, **kw)


def test_llm_grounded_output_passes(req_partial, resp_partial):
    llm = FakeLLM(["**部分配送**。总费用 120 元，体积利用率 50%，S01 等待 10 分钟；S02 未配送，箱件尺寸超过所有车厢。"])
    r = explain(_req(req_partial, resp_partial), llm)
    assert r.mode == "llm" and r.model == "fake" and r.warnings == []
    assert r.grounding.passed and r.grounding.unmatched_numbers == [] and r.grounding.checked_numbers >= 3
    system, user = llm.calls[0]
    assert "事实表" in system and '"total_cost": 120' in user and "x_km" not in user  # 不把坐标发给模型


def test_llm_fabricated_number_retry_then_fallback(req_partial, resp_partial):
    llm = FakeLLM(["总费用 150 元。", "总费用 150 元，还是错的。"])
    r = explain(_req(req_partial, resp_partial), llm)
    assert r.mode == "template" and r.model is None
    assert any("回退模板" in w and "150 元" in w for w in r.warnings)
    assert "120 元" in r.text  # 模板文本
    assert len(llm.calls) == 2 and "150" in llm.calls[1][1]  # 重试提示里带了未匹配数字


def test_llm_fabricated_then_corrected(req_partial, resp_partial):
    llm = FakeLLM(["总费用 150 元。", "总费用 120 元，体积利用率 50%。"])
    r = explain(_req(req_partial, resp_partial), llm)
    assert r.mode == "llm" and r.grounding.passed
    assert any("重试后通过" in w for w in r.warnings)


def test_llm_exception_falls_back(req_partial, resp_partial):
    llm = FakeLLM(error=TimeoutError("boom"))
    r = explain(_req(req_partial, resp_partial), llm)
    assert r.mode == "template" and "TimeoutError" in r.warnings[0]
    assert "部分配送" in r.text


def test_unload_focus_prompt_mentions_steps(req_partial, resp_partial):
    llm = FakeLLM(["V01 到站 S01：1. 取出 B02（易碎）2. 取出 B01。装货按卸货逆序进行。"])
    r = explain(_req(req_partial, resp_partial, focus="unload", vehicle_id="V01"), llm)
    assert r.mode == "llm"
    assert "作业单" in llm.calls[0][1]
