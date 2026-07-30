# Vega 架构

## 一句话

通用长文本知识引擎:长文本 → 结构化实体画像 + 关系图 + 可检索知识库。内核领域中立,领域进插件,消费端读产物。

## 三层

```
消费端(cli/api / spica) → core(管线) → schemas(契约) + store(持久化)
                          ↑
                   plugins(领域)注入 core(依赖倒置),不被 core import
```

- **schemas/**(领域中立):Entity / Relation / AttributeValue / Mention / Document / Segment / EntityProfile / ProfileEvent。最高纪律:不出现领域词。
- **core/**(领域中立管线):segment → embed(contextual)→ extract(经插件 prompt)→ normalize(名归一)→ profile(合成+溯源+CRAG)→ summarize(RAPTOR)→ retrieve(hybrid+rerank)→ ingest(流式+断点续跑)。
- **plugins/**(领域):novel 首例。定义实体/关系 type、属性 schema、抽取 prompt、别名归一规则。
- **store/**(持久化):文档级隔离,每 doc_id 一个 SQLite(向量 + KG)。

## 内核领域中立纪律(最高)

`schemas/` 与 `core/` 严禁出现「角色/伏笔/修为/功法/章节」等任何领域词。内核只认:实体/关系/属性/事件/段/文档。领域概念进 `plugins/<domain>/`。core 不 import plugins,经 `DomainPlugin` 接口注入(依赖倒置)。

## 溯源防幻觉

画像(EntityProfile)每个属性值挂 `Mention`(doc_id + segment_id + 字符区间)。无溯源不上画像。合成时 CRAG 自检:校验属性有原文支撑,否则丢弃。这是 vega 对抗 LLM 幻觉的核心(对应 spica 真跑时「灵豆化形」式翻车)。

## 文档隔离 + 断点续跑

- 每份文档一个知识库(`workdir/<doc_id>/store.sqlite`),互不污染。
- 长文本(百万字级)ingest 必须 checkpoint,中断可续。

## 500 万字挑战与对策

| 挑战 | 对策 |
|---|---|
| 向量库内存不够/丢失 | sqlite-vec 持久化,按文档隔离 |
| 抽取几千次调用/数小时 | 并行 + 限速 + 断点续跑 |
| truth 膨胀爆 prompt | 分层:RAPTOR 远层摘要 + 近层原文 + 结构化检索 |
| 名归一歧义爆炸 | 全局实体注册表 + 别名归一 + 共指消解(领域插件注入规则) |
| 画像跨章矛盾 | 时序合并(timeline 共存,不覆盖) |

## 与 spica 的关系

vega(读层/Python)产 `CharacterProfile.json` + 向量索引 → spica(写层/TS)读它 grounded 写同人。跨语言,文件契约衔接(见 `contract.md`)。星名成对:spica 角宿一(写),vega 织女星(读)。

## 参考与二开

见 `references.md`。基底选 LightRAG(fork),二开三模块:名归一 / 画像合成 / 时序溯源。每处二开由真实失败案例驱动。
