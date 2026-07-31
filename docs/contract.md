# Vega ↔ Spica 产物契约

Vega(读层/Python)产出的知识产物,Spica(写层/TS)按此契约消费。跨语言,文件 + JSON/SQLite 衔接。

## 落盘位置

```
<workdir>/<doc_id>/
├── store.sqlite        # KG(实体/关系/画像/段,JSON 列)+ 向量(sqlite-vec)
├── profiles/
│   └── <entity_id>.json   # 实体画像(消费端最常用)
└── manifest.json       # 文档元信息 + ingest 进度(断点续跑)
```

Spica 侧:每本书一个 workdir(与 spica 的 workdir 隔离边界一致),`<workdir>/kg/` 即 vega 产物。

## profiles/<entity_id>.json 形状

对应 vega `EntityProfile`(pydantic)→ JSON。Spica 侧用 zod 写等价 schema 消费(双份定义,跨语言契约本就如此,各自维护)。

```jsonc
{
  "entity_id": "e1",
  "summary": "黄豆豆,人族,本是……(LLM 合成,带溯源约束)",
  "attributes": {
    "race": { "value": "人族", "mentions": [{"doc_id":"d1","segment_id":2,"char_start":0,"char_end":5}], "confidence": 0.95 },
    "origin": { "value": "...", "mentions": [...] },
    "cultivation_stages": { "value": [...], "mentions": [...] }
  },
  "relations": [
    { "id":"r1", "subject":"e1", "object":"e2", "type":"师徒", "mentions":[...] }
  ],
  "events": [
    { "order":0, "segment_id":0, "desc":"登场", "mentions":[...] }
  ],
  "provenance": [ {"doc_id":"d1","segment_id":0,"char_start":0,"char_end":3} ]
}
```

**关键**:每个属性值都带 `mentions`(原文出处)。Spica 写作时若要核对"黄豆豆种族",读 `attributes.race.value` + 可回查 mentions,不再幻觉。

## 检索接口(HTTP)

vega 以服务形态运行(`vega serve`),暴露 HTTP,供 spica 交互式查询:
```
GET  /plugins                            → {name: "module:Class"}  可用插件(注册表)
GET  /docs/{doc_id}/entities             → [{name,type,aliases}]   KG 实体(抽取后)
GET  /docs/{doc_id}/profile?entity=X&aliases=Y&plugin=novel  → 画像 JSON
POST /docs/{doc_id}/retrieve  {query, top_k}  →  [{segment_id, score, text}]
```
- ingest(建库,批处理慢)→ 文件契约;query/profile(写作期实时)→ HTTP。
- spica 永不 import vega(Python),靠 HTTP + JSON schema 契约。

## 契约演进

- 字段新增只加不删,Spica 侧 optional 消费。
- pydantic(TS 侧 zod)双向校验;manifest.json 记 schema 版本。
