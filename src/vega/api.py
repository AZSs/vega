"""HTTP 服务 —— 供消费端(如 spica/TS)交互式查询 vega。

跨语言契约:spica 不 import vega,通过 HTTP 调用。
端点:
  GET  /plugins                         列可用插件
  GET  /docs/{doc_id}/entities           列 KG 实体(抽取后)
  GET  /docs/{doc_id}/profile            合成实体画像 ?entity=X&aliases=Y&plugin=novel
  POST /docs/{doc_id}/retrieve           语义检索 {query, top_k}
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .core.embed import make_ollama_embedder
from .core.profile import synthesize_profile
from .plugins import discover_plugins, load_plugin
from .store import VectorStore


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    ollama_url: str = "http://localhost:11434"
    embed_model: str = "bge-m3"


def _dim_of(workdir: str, doc_id: str) -> int | None:
    db_path = Path(workdir) / doc_id / "vectors.sqlite"
    if not db_path.exists():
        return None
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT sql FROM sqlite_master WHERE name='vec'").fetchone()
    con.close()
    if not row or "float[" not in row[0]:
        return None
    return int(row[0].split("float[")[1].split("]")[0])


def create_app(*, workdir: str, config_path: str | None = None) -> FastAPI:
    app = FastAPI(title="vega", description="长文本知识引擎")

    @app.get("/plugins")
    def plugins() -> dict[str, str]:
        return discover_plugins(config_path)

    @app.get("/docs/{doc_id}/entities")
    def entities(doc_id: str) -> list[dict[str, Any]]:
        # KG 实体(抽取后落 kg.sqlite;未抽取时返空)
        kg_path = Path(workdir) / doc_id / "kg.sqlite"
        if not kg_path.exists():
            return []
        con = sqlite3.connect(str(kg_path))
        rows = con.execute("SELECT name, type, aliases FROM entities").fetchall()
        con.close()
        return [{"name": n, "type": t, "aliases": a} for n, t, a in rows]

    @app.get("/docs/{doc_id}/profile")
    async def profile(
        doc_id: str,
        entity: str,
        aliases: str = "",
        plugin: str = "novel",
        refresh: bool = False,
    ) -> dict[str, Any]:
        try:
            plug = load_plugin(plugin, config_path)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()]

        # 缓存:profile 计算慢(203 chunks × LLM),首次算完存 JSON,后续秒返
        import hashlib
        import json as _json

        cache_key = hashlib.md5(
            f"{doc_id}:{entity}:{','.join(alias_list)}:{plugin}".encode()
        ).hexdigest()
        cache_file = Path(workdir) / doc_id / f"profile_cache_{cache_key}.json"

        # 缓存失效:graphml 修改时间 > 缓存时间 → 过期重算
        lightrag_graph = Path(workdir) / doc_id / "lightrag" / "graph_chunk_entity_relation.graphml"
        cache_valid = cache_file.exists() and not refresh
        if cache_valid and lightrag_graph.exists():
            cache_valid = cache_file.stat().st_mtime > lightrag_graph.stat().st_mtime

        if cache_valid:
            return dict[str, Any](_json.loads(cache_file.read_text(encoding="utf-8")))

        # 优先 LightRAG 后端(graphml 存在);回退自建后端(vectors.sqlite)
        if lightrag_graph.exists():
            from .core.profile import build_profile_from_lightrag

            result = await build_profile_from_lightrag(workdir, doc_id, entity, alias_list, plug)
        else:
            dim = _dim_of(workdir, doc_id)
            if dim is None:
                raise HTTPException(404, f"未找到 {doc_id} 的知识库(先 ingest)")
            result = await synthesize_profile(workdir, doc_id, entity, alias_list, plug)
        if result is None:
            raise HTTPException(404, "无命中或合成失败")
        # 写缓存
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(_json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result

    @app.post("/docs/{doc_id}/retrieve")
    async def retrieve(doc_id: str, req: RetrieveRequest) -> list[dict[str, Any]]:
        dim = _dim_of(workdir, doc_id)
        if dim is None:
            raise HTTPException(404, f"未找到 {doc_id} 的知识库")
        embed_fn = make_ollama_embedder(base_url=req.ollama_url, model=req.embed_model)
        vecs = await embed_fn([req.query])
        import numpy as np

        q = np.array(vecs[0], dtype=np.float32).tobytes()
        store = VectorStore(workdir, doc_id, dim=dim)
        hits = store.search(q, top_k=req.top_k)
        store.close()
        return [{"segment_id": h.segment_id, "score": h.score, "text": h.text} for h in hits]

    return app


__all__ = ["create_app"]
