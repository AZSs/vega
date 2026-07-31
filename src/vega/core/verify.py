"""标注验证 —— 用 annotated_examples() 当 test case,跑抽取对比 pass/fail。

用户标 5-10 个 chunk 的正确属性,系统跑抽取后对比:
  标注 dao_fruit=不朽道果(拥有) → 抽取出 dao_fruit=不朽道果 → PASS
  标注 age=16 → 抽取出 age=null → FAIL

这是 prompt 质量的客观度量,不靠人看画像"觉得准不准"。
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..plugins import DomainPlugin
from .llm import ChatFn, make_chat_from_env


async def verify_annotations(
    plugin: DomainPlugin,
    *,
    chat_fn: ChatFn | None = None,
) -> dict[str, Any]:
    """跑标注验证:对每条标注,跑抽取 prompt → 对比标注事实 → pass/fail 报告。

    返回 {total, passed, failed, details: [{chunk, field, expected, got, pass}]}
    """
    chat = chat_fn or make_chat_from_env()
    annotations = plugin.annotated_examples()
    if not annotations:
        return {"total": 0, "passed": 0, "failed": 0, "details": [], "error": "无标注"}

    extract_sys = plugin.profile_extract_system()
    fields = plugin.profile_fields()

    details: list[dict[str, Any]] = []
    passed = 0
    failed = 0

    for i, ann in enumerate(annotations):
        # 跑抽取
        extract_user = (
            f"目标角色:黄豆豆(别名:不朽仙子)\n片段:[标注{i}] {ann.chunk}\n"
            f'输出 {{"facts":[{{"field":"{fields}","value":"...","seg":"标注{i}"}}]}}'
        )
        try:
            raw = await chat(extract_sys, extract_user)
            m = re.search(r"\{[\s\S]*\}", raw)
            facts_data = json.loads(m.group(0)).get("facts", []) if m else []
        except Exception:
            facts_data = []

        # 抽取结果按 field 聚合
        extracted: dict[str, str] = {}
        for f in facts_data:
            field = str(f.get("field", ""))
            value = str(f.get("value", ""))
            if field and value:
                extracted[field] = value

        # 逐字段对比
        for expected_field, expected_value in ann.facts.items():
            got = extracted.get(expected_field, "")
            # 模糊匹配:标注值的关键词在抽取结果中出现即 pass
            is_pass = _fuzzy_match(expected_value, got)
            if is_pass:
                passed += 1
            else:
                failed += 1
            details.append(
                {
                    "chunk": ann.chunk[:60],
                    "field": expected_field,
                    "expected": expected_value,
                    "got": got or "(空)",
                    "pass": is_pass,
                }
            )

    total = passed + failed
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": f"{passed}/{total}" if total else "0/0",
        "details": details,
    }


def _fuzzy_match(expected: str, got: str) -> bool:
    """模糊匹配:expected 的关键词在 got 中出现即 pass。

    标注 "不朽道果(拥有)" → 抽出 "不朽道果" → pass(关键词"不朽道果"在结果中)
    """
    if not expected or not got:
        return False
    # 取标注值的主体部分(去掉括号说明)
    key = expected.split("(")[0].strip()
    if not key:
        key = expected
    return key in got


__all__ = ["verify_annotations"]
