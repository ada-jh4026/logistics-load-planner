"""运行配置：全部来自环境变量 / agent/.env。密钥缺失不是错误，服务进入模板模式。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"), override=False)


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    base_url: str
    model: str
    timeout_s: float
    provider: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


def load_settings() -> Settings:
    key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    base = os.getenv("DEEPSEEK_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
    model = os.getenv("AGENT_MODEL") or "deepseek-chat"
    timeout = float(os.getenv("AGENT_TIMEOUT_S") or 30)
    provider = os.getenv("AGENT_PROVIDER") or ("deepseek" if "deepseek" in base else "openai-compatible")
    return Settings(api_key=key, base_url=base, model=model, timeout_s=timeout, provider=provider)
