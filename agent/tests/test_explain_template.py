from fastapi.testclient import TestClient

from agent import app as app_module
from agent.llm import NullLLM


def _client(monkeypatch):
    monkeypatch.setattr(app_module, "llm", NullLLM())
    return TestClient(app_module.app)


def test_health_without_key(monkeypatch):
    monkeypatch.setattr(app_module, "settings", app_module.settings.__class__(api_key=None, base_url="https://api.deepseek.com", model="deepseek-chat", timeout_s=30, provider="deepseek"))
    c = _client(monkeypatch)
    r = c.get("/agent/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["schema_version"] == "0.1"
    assert body["llm"] == {"provider": None, "model": None, "configured": False}


def test_explain_overview_template(monkeypatch, req_partial, resp_partial):
    c = _client(monkeypatch)
    r = c.post("/agent/explain", json={"schema_version": "0.1", "request": req_partial, "response": resp_partial, "focus": "overview"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["mode"] == "template" and b["model"] is None
    assert "未配置模型密钥" in b["warnings"][0]
    assert "部分配送" in b["text"] and "S02" in b["text"] and "箱件尺寸超过所有车厢" in b["text"]
    assert "120 元" in b["text"] and "等待 10 分钟" in b["text"]
    assert b["grounding"]["passed"] is True and b["grounding"]["unmatched_numbers"] == []
    assert b["facts"]["metrics"]["total_cost"] == 120


def test_explain_unassigned_and_vehicle_and_unload(monkeypatch, req_partial, resp_partial):
    c = _client(monkeypatch)
    base = {"schema_version": "0.1", "request": req_partial, "response": resp_partial}
    r = c.post("/agent/explain", json={**base, "focus": "unassigned"})
    assert r.status_code == 200 and "S02" in r.json()["text"] and "BOX_TOO_LARGE" not in r.json()["text"]
    r = c.post("/agent/explain", json={**base, "focus": "vehicle", "vehicle_id": "V01"})
    assert r.status_code == 200 and "100 + 2 × 10 = 120 元" in r.json()["text"]
    r = c.post("/agent/explain", json={**base, "focus": "unload", "vehicle_id": "V01"})
    t = r.json()["text"]
    assert r.status_code == 200 and t.index("B02") < t.index("B01") and "易碎" in t and "逆序" in t


def test_explain_rejects_failed_and_missing_vehicle(monkeypatch, req_success, resp_failed, resp_success):
    c = _client(monkeypatch)
    r = c.post("/agent/explain", json={"schema_version": "0.1", "request": req_success, "response": resp_failed})
    assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_INPUT"
    r = c.post("/agent/explain", json={"schema_version": "0.1", "request": req_success, "response": resp_success, "focus": "vehicle"})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["path"] == "vehicle_id"


def test_explain_invalid_body_422(monkeypatch):
    c = _client(monkeypatch)
    r = c.post("/agent/explain", json={"schema_version": "0.1", "request": {"case_id": "x"}, "response": {}})
    assert r.status_code == 422
    b = r.json()
    assert b["error"]["code"] == "INVALID_INPUT" and b["error"]["details"]
