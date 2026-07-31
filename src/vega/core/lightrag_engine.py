"""LightRAG 底座适配器 —— 用 LightRAG 替换 vega 自建抽取/存储底座。

LightRAG(lightrag-hku)原生带自主实体发现 + 共指归一 + 图检索 + source_id 溯源,
解决 vega 自建底座"用户种子驱动"的软肋。vega 保留:插件(注入 entity_types_guidance
+ 领域 prompt)、Mention 溯源(映射 LightRAG source_id→chunk)、权重名归一、结构化画像。

组合(非继承,LightRAG @final):LightRAGEngine 包装 LightRAG 实例,暴露 vega 需要的
ingest / discover_entities / get_entity_with_sources 三个能力。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from ..plugins import DomainPlugin
from .embed import EmbedFn
from .llm import ChatFn


def _wrap_llm(chat: ChatFn) -> Callable[..., Awaitable[str]]:
    """vega ChatFn(system,user)->str 适配 LightRAG llm_model_func(prompt,system_prompt)。

    DeepSeek 不输出 LightRAG 要求的完成分隔符 <|COMPLETE|>,导致抽取结果被判不完整→
    实体不并入图。此处补上(仅抽取解析检查该分隔符,查询路径不检查,安全)。
    """

    async def llm_func(
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[Any] | None = None,
        **kwargs: Any,
    ) -> str:
        resp = await chat(system_prompt or "", prompt)
        # 仅抽取响应补完成分隔符(DeepSeek 不输出 <|COMPLETE|>,导致抽取被判不完整)
        # 合并/摘要/查询响应不补(会破坏其解析)
        if (
            system_prompt
            and "entity" in system_prompt
            and "extraction" in system_prompt
            and "<|COMPLETE|>" not in resp
        ):
            resp = resp + "\n<|COMPLETE|>"
        return resp

    return llm_func


def _wrap_embed(embed: EmbedFn) -> Any:
    """vega embed(texts)->list[list[float]] 适配 LightRAG EmbeddingFunc(texts)->np.ndarray。"""
    import numpy as np
    from lightrag.base import EmbeddingFunc

    async def _fn(texts: list[str]) -> np.ndarray:
        vecs = await embed(texts)
        return np.array(vecs, dtype=np.float32)

    return EmbeddingFunc(embedding_dim=1024, func=_fn)


class LightRAGEngine:
    """LightRAG 底座适配器。文档级隔离:working_dir=<workdir>/<doc_id>/lightrag。"""

    def __init__(
        self,
        workdir: str,
        doc_id: str,
        plugin: DomainPlugin,
        *,
        chat: ChatFn,
        embed: EmbedFn,
    ) -> None:
        from pathlib import Path

        from lightrag import LightRAG

        self.doc_id = doc_id
        self.plugin = plugin
        self.working_dir = Path(workdir) / doc_id / "lightrag"
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # 注入领域 entity_types 引导(插件→LightRAG)
        guidance = "、".join(plugin.entity_types)
        # 用插件 extract_prompt 的领域引导覆盖默认抽取 system prompt(保留 LightRAG 模板骨架)
        # 仅注入领域类型,不破坏 LightRAG 的 JSON 输出契约
        self.rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=_wrap_llm(chat),
            embedding_func=_wrap_embed(embed),
            addon_params={"entity_types_guidance": guidance, "language": "Chinese"},
        )
        self._initialized = False

    async def _ensure_init(self) -> None:
        if not self._initialized:
            await self.rag.initialize_storages()
            self._initialized = True

    async def ingest(self, text: str) -> None:
        """喂 LightRAG ainsert(自主切 chunk + 抽实体/关系 + 合并图)。

        注:用 ainsert 非 ainsert_custom_chunks —— 后者跳过 Phase3 图合并(实体不入图)。
        vega 切章在此底座不适用(LightRAG 自切),章级分段留 self 后端。
        """
        await self._ensure_init()
        # 大文本分批 ainsert(单次过大 LLM 抽取易超时),每批 ~20 章
        document = self.plugin.split_sections(self.doc_id, text)
        chapters = [s.text for s in document.segments if s.text.strip()]
        batch = 20
        for i in range(0, len(chapters), batch):
            await self.rag.ainsert("\n\n".join(chapters[i : i + batch]))
            done_n = min(i + batch, len(chapters))
            print(f"[vega-lightrag] {self.doc_id} 已喂 {done_n}/{len(chapters)} 章")
        print(f"[vega-lightrag] {self.doc_id} ingest 完成,{len(chapters)} 章")

    async def discover_entities(self) -> list[dict[str, Any]]:
        """自主发现全量实体(不靠用户种子)。从 graph storage 读所有节点。"""
        await self._ensure_init()
        graph = self.rag.chunk_entity_relation_graph
        entities: list[dict[str, Any]] = []
        try:
            for d in await graph.get_all_nodes():
                entities.append(
                    {
                        "name": d.get("entity_id") or d.get("id", ""),
                        "type": d.get("entity_type", ""),
                        "description": d.get("description", ""),
                        "source_id": d.get("source_id", ""),
                    }
                )
        except Exception as e:
            print(f"[vega-lightrag] discover 实体失败:{e}")
        return entities

    async def get_entity_with_sources(self, name: str) -> dict[str, Any] | None:
        """取实体节点 + 其 source chunks 原文(source_id→kv_storage 反查)+ 邻居关系。"""
        await self._ensure_init()
        graph = self.rag.chunk_entity_relation_graph
        node_data: dict[str, Any] | None = None
        for d in await graph.get_all_nodes():
            if d.get("entity_id") == name or d.get("id") == name:
                node_data = d
                break
        if node_data is None:
            return None
        source_id = node_data.get("source_id", "")
        chunk_keys = [k for k in str(source_id).split() if k] if source_id else []
        chunks: list[str] = []
        for key in chunk_keys:
            try:
                chunk = await self.rag.text_chunks.get_by_id(key)
                if chunk and isinstance(chunk, dict):
                    chunks.append(chunk.get("content", ""))
            except Exception:
                pass
        # 邻居关系:get_all_edges 过滤含该实体的
        relations: list[dict[str, Any]] = []
        try:
            for e in await graph.get_all_edges():
                if e.get("src_id") == name or e.get("tgt_id") == name:
                    relations.append(
                        {
                            "target": e.get("tgt_id")
                            if e.get("src_id") == name
                            else e.get("src_id"),
                            "type": e.get("weight", 1.0),
                            "description": e.get("description", ""),
                        }
                    )
        except Exception:
            pass
        return {
            "name": node_data.get("entity_id", name),
            "type": node_data.get("entity_type", ""),
            "description": node_data.get("description", ""),
            "source_chunks": chunks,
            "source_chunk_keys": chunk_keys,
            "relations": relations,
        }


__all__ = ["LightRAGEngine"]
