# Vega

> 把长文本织成知识图谱的通用引擎。

Vega 是一个**通用长文本知识引擎**：吃进任意长文本（小说、法律文书、技术文档、财报……），产出结构化的实体画像 + 关系图 + 可检索知识库，供下游消费（写作、问答、关系分析）。

## 定位

```
              Vega(读层 / 通用内核)
              ┌──────────────────────────────────┐
              │  切段 + contextual embedding      │
              │  实体/关系抽取(通用 schema)        │
              │  名归一(中英文别名/共指)           │
              │  实体画像合成 + 章节溯源           │
              │  RAPTOR 层级摘要                  │
              │  hybrid 检索 + rerank + CRAG 自检 │
              │  文档级隔离                       │
              └──────────────┬───────────────────┘
                             │ 领域插件(可插拔)
              ┌──────────────┴───────────────────┐
              │ 小说插件   法律插件   技术文档插件 …│
              └──────────────┬───────────────────┘
                             │ 产物契约(JSON/SQLite)
              ┌──────────────┴───────────────────┐
              │ 消费端:spica(写作) · 通用QA · 关系分析 …│
              └──────────────────────────────────┘
```

- **spica**（角宿一，写作引擎）负责写；**vega**（织女星，知识引擎）负责读与懂。一写一读，星名成对。
- 内核**领域中立**——不出现「角色 / 伏笔 / 修为」等任何领域词，只认「实体 / 关系 / 属性 / 事件」。领域概念进 `plugins/`。
- 首个领域插件：**小说**（CharacterProfile 含修为/功法/成仙路径）。首个消费端：**spica**（读画像 grounded 写同人）。

## 技术栈

- **Python + uv + pydantic**（RAG 生态成熟，二开 LightRAG 等顺手）
- 向量持久化：sqlite-vec
- embedding：Ollama 本地（bge-m3），可换
- 与 spica（TS）跨语言，靠 JSON/SQLite 文件契约衔接

## 快速开始

```bash
uv sync --extra dev --extra serve --extra watch

# 1. 建库:长文本 → 切章 + contextual embedding + 向量持久化
vega ingest book1 --file novel.txt --workdir ./ws

# 2. 抽取:全量逐块抽实体/关系 → KG(带溯源)
export DEEPSEEK_API_KEY=...   # 用强模型抽取(可选,否则走 Ollama)
vega extract book1 --workdir ./ws --filter "主角,主角别名" --limit 300

# 3. 画像:KG 聚合(全量+溯源,无 LLM 二次合成)
vega profile book1 --entity 主角 --aliases "别名1,别名2" --workdir ./ws --kg

# 4. 检索 / 服务
vega query book1 "问题" --workdir ./ws
vega serve --workdir ./ws         # HTTP: /profile /retrieve /entities /plugins
```

## 插件(领域可插拔)

切换领域 = 实现一个 `DomainPlugin`,内核不改:

```bash
vega plugins                    # 列可用插件(注册表:entry points + 配置 + 内置)
vega ingest ... --plugin novel  # 用 novel 插件(分章/修仙画像)
```

别人 `pip install vega-legal-plugin`(声明 entry point)→ 自动发现,`--plugin legal` 即用。
本地开发:`vega.toml` `[plugins] legal = "my.mod:LegalPlugin"`。详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 状态

🚧 step 1-2 已落地(切章/embedding/sqlite-vec + KG 抽取/名归一/画像聚合),真跑《谁让他修仙的》验证:黄豆豆画像 race=人族(228溯源)、不朽道果已拥有、143 条关系,每字段可回查原文。
详见 [docs/roadmap.md](docs/roadmap.md)。

## 核心纪律

1. **内核领域中立**：`src/vega/schemas/` 和 `src/vega/core/` 不得 import 任何领域插件。领域概念一律 `plugins/`。
2. **溯源防幻觉**：画像每个属性字段挂原文出处（Mention），可回查。无溯源的字段不上画像。
3. **文档隔离**：每份文档一个知识库，互不污染。
4. **可断点续跑**：长文本（百万字级）ingest 必须 checkpoint，中断可续。
5. **TDD**：pytest，schema 与纯逻辑先行。

## 状态

🚧 骨架阶段。详见 [docs/architecture.md](docs/architecture.md)。
