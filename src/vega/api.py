"""HTTP 服务 —— vega API + Web UI + spica 触发。

端点:
  原有: /plugins /docs/{id}/entities /docs/{id}/profile /docs/{id}/retrieve
  新增: /api/upload /api/docs /api/docs/{id}/status
        /api/docs/{id}/write /api/write/{task_id}(SSE)
        /api/docs/{id}/chapters /api/docs/{id}/chapters/{n}
  静态: / ← web-ui/dist/index.html
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .core.embed import make_ollama_embedder
from .core.profile import synthesize_profile
from .plugins import discover_plugins, load_plugin
from .store import VectorStore

_profile_semaphore = asyncio.Semaphore(2)
_write_tasks: dict[str, dict[str, Any]] = {}  # task_id -> {process, logs, status}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    ollama_url: str = "http://localhost:11434"
    embed_model: str = "bge-m3"


class WriteRequest(BaseModel):
    entity: str
    aliases: list[str] = []
    chapters: int = 3
    premise: str = ""


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


def _count_graph_nodes(graphml: Path) -> int:
    if not graphml.exists():
        return 0
    try:
        import networkx as nx

        return int(nx.read_graphml(str(graphml)).number_of_nodes())
    except Exception:
        return 0


def _list_chapters(spica_workdir: Path) -> list[dict[str, Any]]:
    chapters_dir = spica_workdir / "chapters"
    if not chapters_dir.exists():
        return []
    result = []
    for f in sorted(chapters_dir.glob("*.md")):
        n = int(f.stem)
        text = f.read_text(encoding="utf-8")
        first_line = text.split("\n")[0].replace("#", "").strip() if text else ""
        result.append({"chapter": n, "title": first_line, "length": len(text)})
    return result


def create_app(
    *, workdir: str, config_path: str | None = None, spica_path: str | None = None
) -> FastAPI:
    app = FastAPI(title="vega", description="长文本知识引擎")
    webui_dist = Path(__file__).parent.parent.parent / "web-ui" / "dist"

    # ---- 原有 API ----

    @app.get("/plugins")
    def plugins() -> dict[str, str]:
        return discover_plugins(config_path)

    @app.get("/docs/{doc_id}/entities")
    def entities(doc_id: str) -> list[dict[str, Any]]:
        # 优先 LightRAG graph;回退自建 KG
        graphml = Path(workdir) / doc_id / "lightrag" / "graph_chunk_entity_relation.graphml"
        if graphml.exists():
            try:
                import networkx as nx

                g = nx.read_graphml(str(graphml))
                result = []
                for nid, data in g.nodes(data=True):
                    d = data or {}
                    result.append(
                        {
                            "name": d.get("entity_id") or nid,
                            "type": d.get("entity_type", ""),
                            "description": str(d.get("description", ""))[:200],
                            "source_id": d.get("source_id", ""),
                        }
                    )
                return result
            except Exception:
                pass
        # 回退自建 KG
        kg_path = Path(workdir) / doc_id / "kg.sqlite"
        if not kg_path.exists():
            return []
        con = sqlite3.connect(str(kg_path))
        rows = con.execute("SELECT name, type, aliases FROM entities").fetchall()
        con.close()
        return [{"name": n, "type": t, "description": "", "source_id": ""} for n, t, a in rows]

    @app.get("/docs/{doc_id}/profile")
    async def profile(
        doc_id: str, entity: str, aliases: str = "", plugin: str = "novel", refresh: bool = False
    ) -> dict[str, Any]:
        try:
            plug = load_plugin(plugin, config_path)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        alias_list = [a.strip() for a in aliases.split(",") if a.strip()]
        import hashlib

        cache_key = hashlib.md5(
            f"{doc_id}:{entity}:{','.join(alias_list)}:{plugin}".encode()
        ).hexdigest()
        cache_file = Path(workdir) / doc_id / f"profile_cache_{cache_key}.json"
        lightrag_graph = Path(workdir) / doc_id / "lightrag" / "graph_chunk_entity_relation.graphml"
        cache_valid = cache_file.exists() and not refresh
        if cache_valid and lightrag_graph.exists():
            cache_valid = cache_file.stat().st_mtime > lightrag_graph.stat().st_mtime
        if cache_valid:
            return dict[str, Any](json.loads(cache_file.read_text(encoding="utf-8")))
        async with _profile_semaphore:
            if lightrag_graph.exists():
                from .core.profile import build_profile_from_lightrag

                result = await build_profile_from_lightrag(
                    workdir, doc_id, entity, alias_list, plug
                )
            else:
                dim = _dim_of(workdir, doc_id)
                if dim is None:
                    raise HTTPException(404, f"未找到 {doc_id} 的知识库(先 ingest)")
                result = await synthesize_profile(workdir, doc_id, entity, alias_list, plug)
        if result is None:
            raise HTTPException(404, "无命中或合成失败")
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
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

    # ---- 新增:Web UI API ----

    @app.post("/api/upload")
    async def upload(
        file: UploadFile = File(...),
        doc_id: str = Form(...),
        shards: int = Form(4),
        plugin: str = Form("novel"),
    ) -> dict[str, str]:
        content = await file.read()
        doc_dir = Path(workdir) / doc_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        txt_path = doc_dir / "source.txt"
        txt_path.write_bytes(content)

        # 异步触发 ingest(不阻塞响应)
        async def _ingest() -> None:
            try:
                from .core.config import load_config
                from .core.lightrag_engine import LightRAGEngine

                cfg = load_config(config_path)
                plug = load_plugin(plugin, config_path)
                eng = LightRAGEngine(workdir, doc_id, plug, config=cfg)
                if shards > 1:
                    await eng.ingest_parallel(content.decode("utf-8"), shards=shards)
                else:
                    await eng.ingest(content.decode("utf-8"))
            except Exception as e:
                print(f"[upload] ingest 失败: {e}")

        asyncio.create_task(_ingest())
        return {"doc_id": doc_id, "status": "ingesting"}

    @app.get("/api/docs")
    def list_docs() -> list[dict[str, Any]]:
        if not Path(workdir).exists():
            return []
        result = []
        for d in sorted(Path(workdir).iterdir()):
            if not d.is_dir() or d.name.startswith("."):
                continue
            graphml = d / "lightrag" / "graph_chunk_entity_relation.graphml"
            has_lr = graphml.exists()
            entity_count = _count_graph_nodes(graphml) if has_lr else 0
            # spica 章节数(在 spica workdir 找)
            spica_wd = Path("novel") / d.name
            chapter_count = (
                len(list((spica_wd / "chapters").glob("*.md")))
                if (spica_wd / "chapters").exists()
                else 0
            )
            result.append(
                {
                    "doc_id": d.name,
                    "has_lightrag": has_lr,
                    "entity_count": entity_count,
                    "chapter_count": chapter_count,
                }
            )
        return result

    @app.get("/api/docs/{doc_id}/status")
    def doc_status(doc_id: str) -> dict[str, Any]:
        graphml = Path(workdir) / doc_id / "lightrag" / "graph_chunk_entity_relation.graphml"
        has_graph = graphml.exists()
        nodes = _count_graph_nodes(graphml) if has_graph else 0
        # 检查 shard 进度
        shard_count = (
            len(list((Path(workdir) / doc_id).parent.glob(f"{doc_id}_shard_*")))
            if has_graph is False
            else 0
        )
        return {
            "doc_id": doc_id,
            "has_graph": has_graph,
            "graph_nodes": nodes,
            "shards_active": shard_count,
        }

    @app.post("/api/docs/{doc_id}/write")
    async def trigger_write(doc_id: str, req: WriteRequest) -> dict[str, str]:
        if not spica_path:
            raise HTTPException(400, "spica_path 未配置(--spica-path)")
        task_id = str(uuid.uuid4())[:8]
        spica_wd = str(Path("novel") / doc_id)
        cmd = [
            "bun",
            "run",
            "dev",
            "--",
            "--chapters",
            str(req.chapters),
            "--workdir",
            spica_wd,
            "--vega-url",
            "http://127.0.0.1:8765",
            "--vega-doc",
            doc_id,
            "--vega-entity",
            req.entity,
        ]
        if req.aliases:
            cmd += ["--vega-aliases", ",".join(req.aliases)]
        if req.premise:
            cmd += ["--premise", req.premise]
        env = dict(os.environ)

        async def _run() -> None:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=spica_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            _write_tasks[task_id] = {"process": proc, "logs": [], "status": "writing"}
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                _write_tasks[task_id]["logs"].append(line.decode("utf-8", errors="replace").strip())
            await proc.wait()
            _write_tasks[task_id]["status"] = "done" if proc.returncode == 0 else "failed"

        asyncio.create_task(_run())
        return {"task_id": task_id, "status": "writing"}

    @app.get("/api/write/{task_id}")
    async def write_sse(task_id: str) -> StreamingResponse:
        if task_id not in _write_tasks:
            raise HTTPException(404, "task not found")

        from collections.abc import AsyncGenerator

        async def stream() -> AsyncGenerator[str, None]:
            task = _write_tasks[task_id]
            sent = 0
            while True:
                logs = task["logs"]
                while sent < len(logs):
                    yield f"data: {logs[sent]}\n\n"
                    sent += 1
                if task["status"] != "writing":
                    yield f"data: [status:{task['status']}]\n\n"
                    break
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/docs/{doc_id}/chapters")
    def list_chapters(doc_id: str) -> list[dict[str, Any]]:
        spica_wd = Path("novel") / doc_id
        return _list_chapters(spica_wd)

    @app.get("/api/docs/{doc_id}/chapters/{n}")
    def read_chapter(doc_id: str, n: int) -> dict[str, str]:
        path = Path("novel") / doc_id / "chapters" / f"{str(n).zfill(3)}.md"
        if not path.exists():
            raise HTTPException(404, f"章节 {n} 不存在")
        return {"content": path.read_text(encoding="utf-8")}

    # ---- 静态文件:Web UI ----
    if webui_dist.exists():
        app.mount("/assets", StaticFiles(directory=str(webui_dist / "assets")), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(str(webui_dist / "index.html"))

        @app.get("/{path:path}")
        def catch_all(path: str) -> FileResponse:
            f = webui_dist / path
            if f.exists() and f.is_file():
                return FileResponse(str(f))
            return FileResponse(str(webui_dist / "index.html"))

    return app


__all__ = ["create_app"]
