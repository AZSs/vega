"""core/ —— 内核管线(领域中立)。

管线阶段(各模块目前为接口骨架,逐步 TDD 填实现):
  segment → embed(contextual) → extract(实体/关系,调插件 prompt) →
  normalize(名归一) → profile(画像合成+溯源+CRAG自检) → summarize(RAPTOR) →
  retrieve(hybrid+rerank) → ingest(流式管线+断点续跑)

依赖方向:core → schemas + store;core 不 import plugins(经 DomainPlugin 接口注入)。
"""

from .segment import segment_text

__all__ = ["segment_text"]
