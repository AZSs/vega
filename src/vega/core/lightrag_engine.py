"""LightRAG 底座适配器 —— 用 LightRAG 替换 vega 自建抽取/存储底座。

LightRAG(lightrag-hku)原生带自主实体发现 + 共指归一 + 图检索 + source_id 溯源,
解决 vega 自建底座"用户种子驱动"的软肋。vega 保留:插件(注入 entity_types_guidance
+ 领域 prompt)、Mention 溯源(映射 LightRAG source_id→chunk)、权重名归一、结构化画像。

组合(非继承,LightRAG @final):LightRAGEngine 包装 LightRAG 实例,暴露 vega 需要的
ingest / discover_entities / get_entity_with_sources 三个能力。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from ..plugins import DomainPlugin
from .config import VegaConfig
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
        chat: ChatFn | None = None,
        embed: EmbedFn | None = None,
        config: VegaConfig | None = None,
    ) -> None:
        from pathlib import Path

        from lightrag import LightRAG

        from .config import load_config
        from .embed import make_ollama_embedder
        from .llm import make_chat_from_config

        self.doc_id = doc_id
        self.plugin = plugin
        self.config = config or load_config()
        self.working_dir = Path(workdir) / doc_id / "lightrag"
        self.working_dir.mkdir(parents=True, exist_ok=True)

        # chat/embedd 优先用传入的,否则从 config 构造
        chat_fn = chat or make_chat_from_config(self.config, "extract")
        embed_fn = embed or make_ollama_embedder(
            self.config.embedding.base_url, self.config.embedding.model
        )

        guidance = "、".join(plugin.entity_types)
        self.rag = LightRAG(
            working_dir=str(self.working_dir),
            llm_model_func=_wrap_llm(chat_fn),
            embedding_func=_wrap_embed(embed_fn),
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

    async def ingest_parallel(self, text: str, shards: int = 4) -> None:
        """并行分片 ingest(MapReduce):拆 N 片 → N 个 LightRAG 实例并行 → 合并 graph。

        每片独立 working_dir + 独立 graph(小图合并快),N 片并行 ≈ Nx 加速。
        不牺牲质量:每片完整跑 LightRAG 抽取+合并,最后合并 graph(同名实体描述拼接)。
        """
        import asyncio
        import shutil

        document = self.plugin.split_sections(self.doc_id, text)
        chapters = [s.text for s in document.segments if s.text.strip()]
        shard_size = (len(chapters) + shards - 1) // shards

        # 创建 N 个分片引擎(各自独立 working_dir)
        shard_dirs: list[Path] = []
        tasks = []
        for i in range(shards):
            start = i * shard_size
            end = min(start + shard_size, len(chapters))
            if start >= end:
                continue
            shard_text = "\n\n".join(chapters[start:end])
            shard_dir = self.working_dir.parent / f"{self.doc_id}_shard_{i}"
            if shard_dir.exists():
                shutil.rmtree(shard_dir)
            shard_dirs.append(shard_dir)
            eng = LightRAGEngine(
                str(self.working_dir.parent.parent),
                f"{self.doc_id}_shard_{i}",
                self.plugin,
                config=self.config,
            )
            n = end - start
            tasks.append(self._run_shard(i, eng, shard_text, n))

        # 并行跑所有分片(return_exceptions=True:1 个失败不拖垮其余)
        print(f"[vega-lightrag] {self.doc_id} 并行 ingest:{shards} 分片,{len(chapters)} 章")
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查失败的分片(跳过失败的,合并成功的)
        failed_shards = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"[vega-lightrag] 分片 {i} 失败(跳过):{r}")
                failed_shards.append(i)
        if failed_shards:
            # 从 shard_dirs 移除失败的
            shard_dirs = [sd for i, sd in enumerate(shard_dirs) if i not in failed_shards]
            if not shard_dirs:
                print("[vega-lightrag] 所有分片失败,无数据可合并")
                return
            print(f"[vega-lightrag] {len(shard_dirs)}/{shards} 分片成功,合并可用分片")

        # 合并 graph + text_chunks
        self._merge_shards(shard_dirs)
        print(
            f"[vega-lightrag] {self.doc_id} 并行 ingest 完成,{len(chapters)} 章,{shards} 分片已合并"
        )

    async def _run_shard(self, idx: int, eng: LightRAGEngine, text: str, n_chapters: int) -> None:
        """跑单个分片。"""
        print(f"[vega-lightrag] 分片 {idx} 开始 ({n_chapters} 章)")
        await eng.ingest(text)
        print(f"[vega-lightrag] 分片 {idx} 完成")

    def _merge_shards(self, shard_dirs: list[Path]) -> None:
        """合并 N 个分片的 graph + text_chunks 到主 working_dir。"""
        import json
        import shutil

        import networkx as nx

        self.working_dir.mkdir(parents=True, exist_ok=True)

        # 合并 graph(NetworkX union,同名实体描述拼接)
        merged = nx.Graph()
        merged_chunks: dict[str, dict[str, Any]] = {}

        for sd in shard_dirs:
            graphml = sd / "graph_chunk_entity_relation.graphml"
            if graphml.exists():
                g = nx.read_graphml(str(graphml))
                for nid, data in g.nodes(data=True):
                    d = data or {}
                    if merged.has_node(nid):
                        existing = merged.nodes[nid]
                        # 描述拼接 + source_id 合并
                        existing["description"] = (
                            str(existing.get("description", ""))
                            + "<SEP>"
                            + str(d.get("description", ""))
                        )
                        existing["source_id"] = (
                            str(existing.get("source_id", ""))
                            + "<SEP>"
                            + str(d.get("source_id", ""))
                        )
                    else:
                        merged.add_node(nid, **d)
                for u, v, data in g.edges(data=True):
                    d = data or {}
                    if merged.has_edge(u, v):
                        existing = merged.edges[u, v]
                        existing["description"] = (
                            str(existing.get("description", ""))
                            + "<SEP>"
                            + str(d.get("description", ""))
                        )
                    else:
                        merged.add_edge(u, v, **d)

            # 合并 text_chunks KV(供 get_entity_with_sources 反查原文)
            chunks_file = sd / "kv_store_text_chunks.json"
            if chunks_file.exists():
                chunks = json.loads(chunks_file.read_text(encoding="utf-8"))
                merged_chunks.update(chunks)

        # 写入主 working_dir
        nx.write_graphml(merged, str(self.working_dir / "graph_chunk_entity_relation.graphml"))
        (self.working_dir / "kv_store_text_chunks.json").write_text(
            json.dumps(merged_chunks, ensure_ascii=False), encoding="utf-8"
        )
        # 复制第一个分片的 LLM cache(避免重复抽取)
        cache_src = shard_dirs[0] / "kv_store_llm_response_cache.json"
        if cache_src.exists():
            shutil.copy2(str(cache_src), str(self.working_dir / "kv_store_llm_response_cache.json"))

        # 清理分片目录
        for sd in shard_dirs:
            shutil.rmtree(sd, ignore_errors=True)

        print(
            f"[vega-lightrag] 合并完成:{merged.number_of_nodes()} 节点,"
            f"{merged.number_of_edges()} 边,{len(merged_chunks)} chunks"
        )

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
        # LightRAG source_id 用 <SEP> 分隔多个 chunk_key
        chunk_keys = [k for k in str(source_id).split("<SEP>") if k] if source_id else []
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
