"""OpenAI 兼容客户端封装（默认 DeepSeek）。任何异常都由调用方转为回退，不抛到 HTTP 层。

测试里注入 FakeLLM，不依赖网络。
"""
from __future__ import annotations

import logging
from typing import Protocol

from .config import Settings

log = logging.getLogger("agent.llm")


class LLM(Protocol):
    model: str

    def complete(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.2) -> str: ...


class NullLLM:
    """未配置密钥时的占位：调用即抛错，上层回退模板。"""

    model = ""

    def complete(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.2) -> str:
        raise RuntimeError("LLM not configured")


class OpenAICompatLLM:
    def __init__(self, settings: Settings):
        from openai import OpenAI  # 延迟导入，便于无密钥环境不加载

        self.model = settings.model
        self._client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, timeout=settings.timeout_s, max_retries=1)

    def complete(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.2) -> str:
        kwargs = {}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            **kwargs,
        )
        content = resp.choices[0].message.content or ""
        log.info("llm ok model=%s chars=%d", self.model, len(content))
        return content


class FakeLLM:
    """测试用：按顺序返回预设文本，记录收到的提示。"""

    model = "fake"

    def __init__(self, outputs: list[str] | None = None, error: Exception | None = None):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, *, json_mode: bool = False, temperature: float = 0.2) -> str:
        self.calls.append((system, user))
        if self.error is not None:
            raise self.error
        if not self.outputs:
            raise RuntimeError("FakeLLM exhausted")
        return self.outputs.pop(0)


def build_llm(settings: Settings) -> LLM:
    if not settings.configured:
        return NullLLM()
    return OpenAICompatLLM(settings)
