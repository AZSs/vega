"""知识库存储 —— 实体/关系持久化(文档级隔离,SQLite)。

一个 doc_id 一个 kg.sqlite,落在 <workdir>/<doc_id>/kg.sqlite,与向量库同目录。
实体按 name 唯一,累积 mentions + attributes(带溯源);关系按 subject+object+type 去重。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class KnowledgeStore:
    """单文档 KG。文档级隔离边界。"""

    def __init__(self, workdir: str, doc_id: str) -> None:
        self.workdir = Path(workdir)
        self.doc_id = doc_id
        self.path = self.workdir / doc_id / "kg.sqlite"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path))
        self._init_schema()

    def _init_schema(self) -> None:
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS entities"
            " (name TEXT PRIMARY KEY, type TEXT, aliases TEXT, attributes TEXT, mentions TEXT)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS relations"
            " (id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, object TEXT,"
            " type TEXT, mentions TEXT)"
        )
        self.db.commit()

    def get_entity(self, name: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT name, type, aliases, attributes, mentions FROM entities WHERE name=?",
            (name,),
        ).fetchone()
        if not row:
            return None
        return {
            "name": row[0],
            "type": row[1],
            "aliases": json.loads(row[2] or "[]"),
            "attributes": json.loads(row[3] or "{}"),
            "mentions": json.loads(row[4] or "[]"),
        }

    def set_entity(self, entity: dict[str, Any]) -> None:
        """upsert 实体(整对象替换)。"""
        self.db.execute(
            "INSERT INTO entities(name, type, aliases, attributes, mentions)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET"
            " type=excluded.type, aliases=excluded.aliases,"
            " attributes=excluded.attributes, mentions=excluded.mentions",
            (
                entity["name"],
                entity["type"],
                json.dumps(entity.get("aliases", []), ensure_ascii=False),
                json.dumps(entity.get("attributes", {}), ensure_ascii=False),
                json.dumps(entity.get("mentions", []), ensure_ascii=False),
            ),
        )
        self.db.commit()

    def list_entities(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT name, type, aliases, attributes, mentions FROM entities"
        ).fetchall()
        return [
            {
                "name": r[0],
                "type": r[1],
                "aliases": json.loads(r[2] or "[]"),
                "attributes": json.loads(r[3] or "{}"),
                "mentions": json.loads(r[4] or "[]"),
            }
            for r in rows
        ]

    def add_relation(self, subject: str, obj: str, rel_type: str, mention: dict[str, Any]) -> None:
        """加关系(subject/object/type 去重,累积 mentions)。"""
        existing = self.db.execute(
            "SELECT id, mentions FROM relations WHERE subject=? AND object=? AND type=?",
            (subject, obj, rel_type),
        ).fetchone()
        if existing:
            mentions = json.loads(existing[1] or "[]")
            mentions.append(mention)
            self.db.execute(
                "UPDATE relations SET mentions=? WHERE id=?", (json.dumps(mentions), existing[0])
            )
        else:
            self.db.execute(
                "INSERT INTO relations(subject, object, type, mentions) VALUES (?, ?, ?, ?)",
                (subject, obj, rel_type, json.dumps([mention], ensure_ascii=False)),
            )
        self.db.commit()

    def get_relations(self, name: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT subject, object, type, mentions FROM relations WHERE subject=? OR object=?",
            (name, name),
        ).fetchall()
        return [
            {"subject": r[0], "object": r[1], "type": r[2], "mentions": json.loads(r[3] or "[]")}
            for r in rows
        ]

    def count_entities(self) -> int:
        return int(self.db.execute("SELECT COUNT(*) FROM entities").fetchone()[0])

    def clear_entities(self) -> None:
        """清空实体表(名归一后整体替换用)。"""
        self.db.execute("DELETE FROM entities")
        self.db.commit()

    def close(self) -> None:
        self.db.close()


__all__ = ["KnowledgeStore"]
