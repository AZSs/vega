"""标注驱动 prompt 体系 —— 用户标示例,系统自动生成 few-shot prompt。

用户不写 prompt 字符串,只标注 5-10 个 chunk 的正确属性(领域知识)。
系统从 schema + 标注自动拼装 prompt,标注同时是 test case(pass/fail 验证)。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Annotation:
    """单条标注:一段原文 → 正确属性(用户标的)。同时是 few-shot 示例 + test case。"""

    chunk: str
    facts: dict[str, str] = field(default_factory=dict)
    note: str = ""


def build_prompt_from_annotations(
    schema: str,
    fields: str,
    annotations: list[Annotation],
    entity: str,
    aliases: list[str],
) -> str:
    """从 schema + 标注自动拼装 system prompt(few-shot 示例驱动)。

    用户不写 prompt,只标示例。系统拼装:任务描述 + 字段列表 + few-shot 示例。
    """
    alias_note = f"(别名:{'、'.join(aliases)})" if aliases else ""
    parts = [
        f"你从小说片段中提取【只关于{entity}{alias_note}】的结构化事实。",
        "只提取关于目标角色的事实,其他角色的忽略。",
        f"字段:{fields}",
        "",
        "【示例】参考以下标注,学习提取规则:",
    ]
    for ann in annotations:
        facts_str = "; ".join(f"{k}={v}" for k, v in ann.facts.items())
        parts.append(f"原文:{ann.chunk[:200]}")
        parts.append(f"→ {facts_str}")
        parts.append("")
    parts.append("无则 facts 空数组。只输出 JSON。")
    return "\n".join(parts)
