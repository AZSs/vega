# Vega Roadmap

Date: 2026-07-30

## 现状(step 1-2 已落地 + 开源 ✅)

- 内核领域中立 schema 契约(`schemas/`):Entity/Relation/Mention/AttributeValue/Document/Segment/EntityProfile
- core 管线(`core/`):segment/embed(contextual)/extract(并发)/normalize(名归一)/profile(KG聚合)/ingest(断点续跑)
- 插件注册表(`plugins/registry.py`):entry points + 配置 + watch,热插拔可重定义
- HTTP serve(`api.py`):/plugins /profile /retrieve /entities
- 首个领域插件 novel(`plugins/novel/`):CharacterProfile(种族/身世/修为/道果/成仙)
- store:VectorStore(sqlite-vec)+ KnowledgeStore(实体/关系,文档隔离)
- 文档:architecture / references / contract / roadmap
- 开源:https://github.com/AZSs/vega (MIT)
- 46 tests pass,ruff/mypy 绿

真跑《谁让他修仙的》1369 章全文建库 + 2227 块全量抽取验证:
- 不朽仙子画像:race=人族(1830溯源)、不朽道果(668溯源)、575 条关系、2098 mentions
- 权重名归一:不朽仙子(2058)为正名,黄豆豆并入,不朽仙人(另一人)独立
- 灰豆豆:99 mentions,race=人族,origin=薪火王朝时期天庭之主,techniques=仙道杀拳/天魔解体大法
- 每字段带 Mention 溯源,可回查原文(对抗 LLM 幻觉的核心价值)

## 起因(为什么有 vega)

spica 真跑同人时暴露:没读原作就靠脑补,把「黄豆豆(人族)」错写成「灵豆化形」——LLM 幻觉。
vega 用「结构化画像 + 每字段挂 Mention 溯源」对抗幻觉:先把原作读成知识图谱+画像,spica 再 grounded 写。

## 下一步(优先级)

### 1. 切章 + contextual embedding + sqlite-vec 持久化 ⭐ ✅
**价值**:500 万字的地基。先把「可检索 + 持久化 + 按书隔离」做实。
**已做**:
- 切章:`NovelPlugin.split_chapters`(第N章正则,中文/阿拉伯/零补齐数字,无章题降级单段)
- contextual retrieval:`annotate_context_prefix`(LLM 上下文前缀,失败降级空)+ `embed_segments`(prefix+text)
- 向量落 sqlite-vec:`VectorStore`(文档级隔离,余弦 top-k via `k=?` KNN,持久化跨重开)
- 断点续跑:`manifest.json` 记 done 段号,`--resume` 跳过已 done;embed 失败优雅中断可续
- Ollama 真实实现(`make_ollama_embedder`/`make_ollama_chat`)+ 注入点(测试用 fake)
- CLI `vega ingest` 打通
**验证**:26 tests pass(分章/向量库/embed/ingest 全 TDD,注入 fake);CLI 烟测(Ollama 未启时优雅降级)。真实原作召回验证待 Ollama 启 + 原作文本。
**改动**:中。

### 2. 名归一 + 画像合成(纯逻辑 TDD) ✅
**价值**:vega 的核心产物——结构化 EntityProfile,带溯源。
**要做**:
- 名归一:别名/共指合并(merge_aliases + resolve_coreference),中文古风称呼规则
- 画像合成:跨段属性聚合 + 时序去矛盾 + CRAG 自检(无溯源字段丢弃)
**改动**:中(纯逻辑,TDD 主战场)。

### 3. 抽取层落 LLM(接 extract_segment)
**价值**:把段→实体/关系跑通,产真实 KG。
**要做**:extract_segment 调领域 plugin.extract_prompt + LLM,产物挂 Mention,接名归一+画像。
**改动**:中。

### 4. 消费端契约联调(spica 侧)
**价值**:端到端:vega 产 CharacterProfile.json → spica 读它 grounded 写同人。
**要做**:spica 侧加「读 kg/ 画像」入口;按 `docs/contract.md` 联调。
**改动**:小(spica 侧)。

## 更远

- LightRAG 基底二开(名归一/画像合成/时序溯源三模块),见 `references.md`
- RAPTOR 层级摘要(章→弧→卷多级树)
- hybrid 检索 + bge-reranker 精排
- 多领域插件(法律/技术文档)
- 服务化(HTTP 检索/画像接口)

## 建议路径

1. **先做 1**(切章+contextual embedding+sqlite-vec)→ 地基 + 可验证召回
2. **再做 2**(名归一+画像合成纯逻辑)→ 核心产物契约敲实
3. **接 3**(抽取落 LLM)→ 真实 KG
4. **联调 4**(spica 消费)→ 端到端

功能够用后,拿真实原作验证比堆功能更值——验证才暴露名归一/时序的真问题。

---

> 注:本路线图与 spica 的 `docs/roadmap.md` 互补。spica 专注写作层(已完 5 核心 todo),vega 专注读层。两者靠 `docs/contract.md` 衔接。
