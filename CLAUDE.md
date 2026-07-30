# CLAUDE.md

本文件为 Claude Code 在本仓库工作时提供指引。**所有规则必须严格遵守。**

## 1. 项目总纲

- **Vega** 是通用长文本知识引擎：长文本 → 结构化实体画像 + 关系图 + 可检索知识库。
- 与 **spica**（`../spica`，TS 写作引擎）成对：vega 负责读与懂，spica 负责写。一写一读。
- 不是小说专用。**首个领域插件是小说，首个消费端是 spica**，但内核领域中立。

## 2. 语言约束

- 所有回复、日志解析、报错分析**统一简体中文**。代码标识符保留英文。

## 3. 铁律:内核领域中立(最高纪律)

- `src/vega/schemas/` 和 `src/vega/core/` **严禁**出现任何领域词:角色 / 伏笔 / 修为 / 功法 / 章节 / 卷弧……
- 内核只认通用概念:**实体(Entity)/ 关系(Relation)/ 属性(Attribute)/ 事件(Event)/ 段(Segment)/ 文档(Document)**。
- 领域概念一律进 `src/vega/plugins/<domain>/`。内核不得 import 插件。
- 违反领域中立 = 架构腐化,必须改。

## 4. 依赖方向(不反向)

```
消费端(cli/api) → core(管线) → schemas(契约) + store(持久化)
                 ↑
              plugins(领域)注入 core,不被 core import
```

- core 不 import plugins;plugins 实现 core 定义的接口(依赖倒置)。
- store 不 import core;schemas 不 import 任何上层。

## 5. 溯源防幻觉

- 画像(EntityProfile)的每个属性值必须挂 `Mention`(原文出处:doc_id + segment_id + 字符区间)。
- 无溯源的字段不得进画像。CRAG 自检:合成时校验属性有原文支撑,否则丢弃。
- 这是 vega 的核心价值:对抗 LLM 幻觉(对应 spica 真跑时「灵豆化形」式翻车)。

## 6. 文档隔离

- 每份文档一个知识库(独立 SQLite + 向量索引),互不污染。
- workdir/文档id 是隔离边界。多文档不得共享存储。

## 7. 技术栈

- **Python 3.11+ + uv + pydantic v2**。
- 向量持久化:sqlite-vec。embedding:Ollama bge-m3(可换)。
- 与 spica(TS)跨语言,靠 JSON/SQLite 文件契约衔接(契约 schema 见 `docs/contract.md`)。
- 消费开源:LightRAG/GraphRAG/Graphiti 等可用则用,缺口(名归一/画像合成/时序溯源)二开,不重造。参考项目清单见 `docs/references.md`。

## 8. 方法论:TDD + SDD

- **SDD 先行**:`schemas/` 用 pydantic 定义契约(实体/关系/画像形状),内核与消费端全消费同一份。
- **TDD**:pytest,纯逻辑(切段/名归一/聚合/合成)先单测再实现。
- 长文本管线必须可断点续跑(checkpoint)。

## 9. 提交前检查

- `ruff check` + `ruff format --check`(lint/格式)
- `mypy src` (类型)
- `pytest`(全绿)
- test 必须全绿才允许提交。

## 10. 目录结构

```
vega/
├── src/vega/
│   ├── schemas/     # 通用内核契约(pydantic,领域中立)——最高纪律
│   ├── core/        # 内核管线(切段/embed/抽取/名归一/画像/摘要/检索/ingest)
│   ├── plugins/     # 领域插件(novel 首例)
│   │   └── novel/   # 小说插件(CharacterProfile:修为/功法/成仙路径)
│   └── store/       # 持久化(文档隔离:sqlite-vec + KG)
├── tests/           # pytest
├── docs/            # architecture.md / contract.md
└── examples/        # 示例输入
```

## 11. 阅读顺序(给新接手的 Claude/人)

1. README.md —— 项目定位 + 架构图
2. CLAUDE.md(本文件)—— 纪律
3. `src/vega/schemas/` —— 领域中立契约(先看这个理解内核形状)
4. `src/vega/plugins/base.py` —— 插件接口
5. `src/vega/plugins/novel/` —— 首个领域插件样例
6. `docs/architecture.md` —— 详细设计
