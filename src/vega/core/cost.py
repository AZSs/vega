"""成本监控 —— LLM 调用记 token + 费用,每章/全书成本报告。

DeepSeek 价格(2026-07,参考):
- deepseek-chat: 输入 ¥0.5/百万 token(缓存命中 ¥0.1),输出 ¥8/百万 token
- 粗估:每次抽取 ~3000 输入 + ~500 输出 ≈ ¥0.005

用法:
  tracker = CostTracker()
  tracker.record("extract", input_tokens=3000, output_tokens=500)
  report = tracker.report()  # {calls, input_tokens, output_tokens, cost_yuan}
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# DeepSeek 价格(元/百万 token)
PRICE_INPUT = 0.5
PRICE_OUTPUT = 8.0
# Ollama 本地免费
PRICE_OLLAMA = 0.0


@dataclass
class CallRecord:
    role: str  # extract / profile / query / embed
    input_tokens: int
    output_tokens: int
    cost_yuan: float
    timestamp: float


@dataclass
class CostTracker:
    records: list[CallRecord] = field(default_factory=list)

    def record(
        self,
        role: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        is_ollama: bool = False,
    ) -> None:
        if is_ollama:
            cost = 0.0
        else:
            cost = (input_tokens / 1_000_000 * PRICE_INPUT) + (
                output_tokens / 1_000_000 * PRICE_OUTPUT
            )
        self.records.append(
            CallRecord(
                role=role,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_yuan=cost,
                timestamp=time.time(),
            )
        )

    def report(self) -> dict[str, Any]:
        total_input = sum(r.input_tokens for r in self.records)
        total_output = sum(r.output_tokens for r in self.records)
        total_cost = sum(r.cost_yuan for r in self.records)
        by_role: dict[str, dict[str, float]] = {}
        for r in self.records:
            if r.role not in by_role:
                by_role[r.role] = {"calls": 0, "cost": 0.0, "input": 0, "output": 0}
            by_role[r.role]["calls"] += 1
            by_role[r.role]["cost"] += r.cost_yuan
            by_role[r.role]["input"] += r.input_tokens
            by_role[r.role]["output"] += r.output_tokens
        return {
            "total_calls": len(self.records),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_yuan": round(total_cost, 4),
            "by_role": by_role,
        }

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.report(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def print_report(self) -> None:
        r = self.report()
        by_role = r["by_role"]
        print("\n=== 成本报告 ===")
        print(f"总调用: {r['total_calls']} 次")
        print(f"总 token: 输入 {r['total_input_tokens']:,} + 输出 {r['total_output_tokens']:,}")
        print(f"总费用: ¥{r['total_cost_yuan']}")
        for role, stats in by_role.items():
            print(f"  {role}: {stats['calls']:.0f} 次, ¥{stats['cost']:.4f}")


__all__ = ["CostTracker", "CallRecord"]
