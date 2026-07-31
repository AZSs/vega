"""vega.toml 配置加载 —— LLM / embedding / per-role 模型配置。

优先级:CLI flag > 环境变量 > vega.toml > 默认值。
api_key 支持 ${ENV_VAR} 引用(不硬编码密钥)。
per-role:extract/query/profile 可各用不同模型(抽取用强模型,查询用便宜的)。
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_ENV_REF = re.compile(r"\$\{(\w+)\}")


@dataclass
class LlmConfig:
    provider: str = "deepseek"  # deepseek / openai / ollama
    model: str = "deepseek-chat"
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    roles: dict[str, dict[str, str]] = field(default_factory=dict)


@dataclass
class EmbeddingConfig:
    provider: str = "ollama"
    model: str = "bge-m3"
    base_url: str = "http://localhost:11434"
    dim: int = 1024


@dataclass
class VegaConfig:
    llm: LlmConfig = field(default_factory=LlmConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)


def _resolve_env(value: str) -> str:
    """${ENV_VAR} → 环境变量值。"""
    return _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), value)


def load_config(path: str | None = None) -> VegaConfig:
    """加载 vega.toml 配置。无文件用默认值 + 环境变量。"""
    cfg_path = Path(path) if path else Path("vega.toml")
    if not cfg_path.exists():
        return _from_env_defaults()

    data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    llm_data = data.get("llm", {})
    emb_data = data.get("embedding", {})

    llm = LlmConfig(
        provider=llm_data.get("provider", "deepseek"),
        model=llm_data.get("model", "deepseek-chat"),
        api_key=_resolve_env(llm_data.get("api_key", "")),
        base_url=llm_data.get("base_url", "https://api.deepseek.com"),
        roles=llm_data.get("roles", {}),
    )
    embedding = EmbeddingConfig(
        provider=emb_data.get("provider", "ollama"),
        model=emb_data.get("model", "bge-m3"),
        base_url=emb_data.get("base_url", "http://localhost:11434"),
        dim=emb_data.get("dim", 1024),
    )
    # 环境变量覆盖 api_key(优先于配置文件)
    if os.environ.get("DEEPSEEK_API_KEY") and not llm.api_key:
        llm.api_key = os.environ["DEEPSEEK_API_KEY"]
    return VegaConfig(llm=llm, embedding=embedding)


def _from_env_defaults() -> VegaConfig:
    """无配置文件时:从环境变量构造默认配置。"""
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return VegaConfig(
        llm=LlmConfig(
            provider="deepseek" if key else "ollama",
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat" if key else "qwen2.5:7b"),
            api_key=key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        ),
    )


def role_llm_config(config: VegaConfig, role: str) -> tuple[str, str, str, str]:
    """取某角色的 (provider, model, api_key, base_url),继承 [llm] + 覆盖 [llm.roles]。"""
    base = config.llm
    override = base.roles.get(role, {})
    return (
        override.get("provider", base.provider),
        override.get("model", base.model),
        override.get("api_key", base.api_key),
        override.get("base_url", base.base_url),
    )


__all__ = [
    "VegaConfig",
    "LlmConfig",
    "EmbeddingConfig",
    "load_config",
    "role_llm_config",
]
