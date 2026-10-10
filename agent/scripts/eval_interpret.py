"""模型模式指令解析评估：对 agent/tests/data/instructions.jsonl 逐条调用真实模型，统计准确率。

用法（仓库根目录）：
  .venv\\Scripts\\python.exe -m agent.scripts.eval_interpret --output artifacts/evidence/A03_eval.json
需要 agent/.env 里有密钥；没有则退出码 2。
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.config import load_settings  # noqa: E402
from agent.interpret import interpret  # noqa: E402
from agent.llm import build_llm  # noqa: E402
from agent.schemas import InterpretRequest  # noqa: E402
from agent.tests.checks import load_request, verify  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="artifacts/evidence/A03_eval.json")
    ap.add_argument("--data", default="agent/tests/data/instructions.jsonl")
    args = ap.parse_args()

    settings = load_settings()
    if not settings.configured:
        print("未配置模型密钥，跳过模型模式评估。")
        return 2
    llm = build_llm(settings)
    cases = [json.loads(l) for l in (ROOT / args.data).read_text(encoding="utf-8").splitlines() if l.strip()]

    rows = []
    ok = 0
    for c in cases:
        original = load_request(c["request"])
        req = InterpretRequest(schema_version="0.1", request=original, instruction=c["instruction"])
        t0 = time.perf_counter()
        r = interpret(req, llm)
        ms = round((time.perf_counter() - t0) * 1000)
        patched = r.patched_request.model_dump() if r.patched_request else None
        errs = verify(original, patched, c["expect"], r.model_dump())
        passed = not errs and r.mode == "llm"
        ok += passed
        rows.append({
            "id": c["id"], "instruction": c["instruction"], "mode": r.mode, "elapsed_ms": ms,
            "passed": passed, "errors": errs, "intent_ops": [o.model_dump() for o in r.intent_ops],
            "patch": [p.model_dump() for p in r.patch], "rejected": [x.model_dump() for x in r.rejected_ops],
            "summary": r.summary, "warnings": r.warnings,
        })
        print(f"[{'PASS' if passed else 'FAIL'}] {c['id']:7s} {ms:5d}ms  {c['instruction']}" + ("" if passed else f"  ← {errs or r.warnings}"))

    out = {
        "date": datetime.date.today().isoformat(),
        "model": settings.model, "base_url": settings.base_url, "temperature": 0.0,
        "total": len(cases), "passed": ok, "accuracy": round(ok / len(cases), 3),
        "median_ms": sorted(r["elapsed_ms"] for r in rows)[len(rows) // 2],
        "max_ms": max(r["elapsed_ms"] for r in rows),
        "note": "输入为 docs/playbook/examples 样例（模拟数据）；准确率指 patched_request 与期望完全一致且由模型模式产出。",
        "rows": rows,
    }
    p = ROOT / args.output
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{ok}/{len(cases)} 通过，准确率 {out['accuracy']}，中位耗时 {out['median_ms']} ms。已保存 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
