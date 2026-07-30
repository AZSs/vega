# 参考项目与开源依赖

Vega 站在开源肩上,不重造轮子。以下项目是 Vega 的参考/依赖/二开基底,按「直接用 / 二开 / 仅参考」分类。

## 一、直接用(依赖或现成组件)

| 项目 | 仓库 | 用途 | 取舍 |
|---|---|---|---|
| **Ollama + bge-m3** | https://github.com/ollama/ollama | 本地 embedding(bge-m3 1024 维),免费离线 | 首选 embedding;可换 |
| **sqlite-vec** | https://github.com/asg017/sqlite-vec | 向量持久化(轻量、单文件、按文档隔离) | 500 万字级够用;替代内存余弦 |
| **pydantic** | https://github.com/pydantic/pydantic | 内核契约 schema(领域中立) | 核心依赖 |
| **ruff / mypy / pytest** | — | Python lint/类型/测试 | 工具链 |

## 二、二开基底(选一个 fork,叠加 Vega 专用层)

| 项目 | 仓库 | 现成能力 | Vega 要二开的缺口 |
|---|---|---|---|
| **LightRAG**(首选基底) | https://github.com/HKUDS/LightRAG | 实体中心图 + 双层检索 + 实体关系抽取,轻量 | 1) 中文角色名归一 2) 结构化 CharacterProfile 合成 3) 时序关系演化 + 章号溯源 |
| **nano-graphrag**(备选基底) | https://github.com/gusye1234/nano-graphrag | GraphRAG 极简实现,~1000 行,易改 | 要最大掌控时选它(近乎重写级二开) |
| **Graphiti**(时序刚需时) | https://github.com/getzep/graphiti | bi-temporal 知识图谱,Neo4j 后端,关系演化追踪 | 通用实体模型不够小说用,需加领域 schema;代价是背 Neo4j |

**基底选择决策**:默认 fork **LightRAG**(轻、无 Neo4j、好改)。仅当「关系时序演化查询」成刚需且愿背 Neo4j 时才转 Graphiti。nano-graphrag 仅作最小验证/全掌控备选。

## 三、仅参考(思路借鉴,不依赖)

| 项目/技术 | 出处 | 借鉴点 |
|---|---|---|
| **Contextual Retrieval** | https://www.anthropic.com/news/contextual-retrieval | 给每段加 LLM 上下文前缀再 embedding,降召回失准 49%——Vega 切段后必做 |
| **RAPTOR** | https://arxiv.org/abs/2401.18059 | 层级摘要树(段→簇→更高层),Vega 多级摘要借鉴 |
| **Microsoft GraphRAG** | https://github.com/microsoft/graphrag | 社区检测 + 层级社区摘要(全局问答思路);但 500 万字建索引太贵,不直接用 |
| **CRAG(Corrective RAG)** | https://arxiv.org/abs/2401.15884 | 检索质量评估 + 纠正——Vega 画像合成的自检防幻觉借鉴 |
| **Late Chunking** | https://jina.ai/news/late-chunking-in-long-context-embedding-models | 长上下文 embedding 先整体后切——contextual retrieval 的替代/补充思路 |
| **HyDE** | https://arxiv.org/abs/2212.10496 | 假设文档嵌入——查询改写思路参考 |
| **bge-reranker** | https://github.com/FlagOpen/FlagEmbedding | cross-encoder rerank——多路召回合并后精排 |

## 四、消费端(读 Vega 产物)

| 项目 | 仓库 | 关系 |
|---|---|---|
| **spica** | 本地 `../spica` | 首个消费端:读 Vega 的 CharacterProfile + 向量索引,grounded 写同人。TS,跨语言靠 JSON/SQLite 契约 |

## 五、二开纪律

- **不 fork 整仓重写**:只在基底上叠加 Vega 专用层(名归一 / 画像合成 / 时序溯源),主干尽量跟 upstream。
- **每处二开要有失败案例驱动**:先跑原版看哪里不行(如把"豆豆"和"黄豆豆"建成两实体),再针对性改,不盲改。
- **缺口 = Vega 价值**:通用工具给的是非结构化 entity description;Vega 给的是结构化、带溯源、时序的 EntityProfile——这是二开的根本理由。

## 六、参考调研记录

- RAG 最新技术调研见会话记录(2026-07):Agentic RAG / Self-RAG / CRAG / HyDE / Contextual Retrieval / Late Chunking / RAPTOR / GraphRAG / LightRAG / Hybrid 检索 / Long Context 互补。
- 长文本→知识图谱的 500 万字挑战:向量库持久化、抽取断点续跑、truth 膨胀分层注入、名归一、时序合并——见 `docs/architecture.md`。
