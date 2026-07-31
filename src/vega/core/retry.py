"""LLM 调用重试 + 超时 + 降级 —— 对抗 429 限流 / 网络超时 / 临时故障。

vaga 和 spica 共用同一套重试策略:
- 429(限流): 指数退避重试(1s→2s→4s),最多 3 次
- 500/502/503(服务端): 同上
- 超时: 30s,超时后重试
- 全部失败: 返降级值(不崩溃,流水线继续)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 3
BASE_DELAY = 1.0  # 秒,指数退避基数
TIMEOUT = 60  # 秒


async def with_retry(
    fn: Callable[[], Awaitable[Any]],
    *,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    timeout: float = TIMEOUT,
    fallback: Any = None,
    label: str = "llm",
) -> Any:
    """带重试+超时的异步调用。全部失败返 fallback(不抛)。

    用法:
        result = await with_retry(lambda: chat(sys, user), fallback="", label="extract")
    """
    import httpx

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(fn(), timeout=timeout)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUS and attempt < max_retries:
                delay = base_delay * (2**attempt)
                print(
                    f"[retry] {label} HTTP {e.response.status_code},"
                    f"{delay}s 后重试({attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
                continue
            print(f"[retry] {label} HTTP {e.response.status_code} 不可重试,降级")
            return fallback
        except (TimeoutError, httpx.TimeoutException):
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                print(f"[retry] {label} 超时,{delay}s 后重试({attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)
                continue
            print(f"[retry] {label} 超时({timeout}s),降级")
            return fallback
        except (httpx.ConnectError, httpx.NetworkError) as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                print(f"[retry] {label} 网络错误,{delay}s 后重试({attempt + 1}/{max_retries})")
                await asyncio.sleep(delay)
                continue
            print(f"[retry] {label} 网络错误,降级:{e}")
            return fallback
        except Exception as e:
            print(f"[retry] {label} 不可恢复错误,降级:{e}")
            return fallback
    return fallback


__all__ = ["with_retry", "RETRYABLE_STATUS", "MAX_RETRIES", "TIMEOUT"]
