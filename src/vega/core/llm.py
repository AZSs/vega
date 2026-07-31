"""LLM chat 后端 —— OpenAI 兼容(DeepSeek 等)+ Ollama,可注入。

画像合成需强模型,本地 qwen2.5:7b 偏弱;DeepSeek 等云端模型质量高。
统一 ChatFn 签名,profile/抽取按需选后端。
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from .config import VegaConfig
    from .embed import EmbedFn

ChatFn = Callable[[str, str], Awaitable[str]]


def _role_llm_config(config: VegaConfig, role: str) -> tuple[str, str, str, str]:
    """取某角色的 (provider, model, api_key, base_url)。"""
    from .config import role_llm_config

    return role_llm_config(config, role)


def make_openai_chat(
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
) -> ChatFn:
    """OpenAI 兼容 chat(DeepSeek 等)。base_url/model 可换其他兼容服务。"""

    async def chat(system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"])

    return chat


def make_chat_from_env() -> ChatFn:
    """按环境变量选后端:有 DEEPSEEK_API_KEY 用 DeepSeek,否则 Ollama。"""
    from .embed import make_ollama_chat

    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if key:
        base = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
        return make_openai_chat(key, base_url=base, model=model)
    return make_ollama_chat()


def make_chat_from_config(config: VegaConfig, role: str = "extract") -> ChatFn:
    """按 vega.toml 配置 + 角色选 LLM 后端(extract/query/profile 可不同模型)。"""
    from .embed import make_ollama_chat

    provider, model, api_key, base_url = _role_llm_config(config, role)
    if provider in ("deepseek", "openai") and api_key:
        return make_openai_chat(api_key, base_url, model)
    # fallback ollama
    return make_ollama_chat(base_url or "http://localhost:11434", model)


def make_embedder_from_config(config: VegaConfig) -> EmbedFn:
    """按 vega.toml 配置构造 embedding 函数。"""
    from .embed import make_ollama_embedder

    return make_ollama_embedder(config.embedding.base_url, config.embedding.model)


__all__ = [
    "ChatFn",
    "make_openai_chat",
    "make_chat_from_env",
    "make_chat_from_config",
    "make_embedder_from_config",
]
