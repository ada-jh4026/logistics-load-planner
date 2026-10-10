"""Capture a real coupled solve and independent validation for consumer handoff."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.models import SolveRequest
from backend.solver import solve_coupled
from backend.validation import validate_solution


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="保存真实修复记录和独立校验")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if raw.get("is_mock") is True:
        raise ValueError("mock 输入不能用于真实修复记录")
    request = SolveRequest.model_validate(raw)
    if request.options.method != "coupled":
        raise ValueError("该脚本只捕获 coupled 求解")
    result = solve_coupled(request)
    violations = validate_solution(request, result)
    write_json(args.output / "request.json", request.model_dump())
    write_json(args.output / "response.json", result.model_dump())
    write_json(args.output / "validation.json", {
        "valid": not violations,
        "violations": [v.model_dump() for v in violations],
    })
    print(f"case={request.case_id} status={result.repair_trace.status} "
          f"served={result.metrics.served_stores}/{result.metrics.total_stores} "
          f"attempted={result.repair_trace.attempted_count} "
          f"accepted={result.repair_trace.accepted_count} valid={not violations}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
