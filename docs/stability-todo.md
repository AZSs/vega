# 稳定性 TODO

Date: 2026-07-31

## 现状：验证过的原型，离生产还差稳定性

端到端跑通（vega 自主发现 → 结构化画像 → spica grounded 写作 → 3 章 pass），但多处脆弱点会导致崩溃/卡死/数据丢失。

---

## P0：会导致流水线中断的（必须修）

### 1. LLM 调用无重试（vega + spica 共同）
- **问题**：DeepSeek 429 限流 / 网络超时 / 临时 502 → 整个流水线崩溃
- **影响**：ingest/profile/write 任何一步 LLM 失败 = 全挂
- **修复**：`core/retry.py` with_retry（指数退避 1s→2s→4s，3 次，超时 60s，失败返降级值不抛）
- **覆盖**：vega `llm.py` make_openai_chat / make_ollama_chat + spica `arbiter/llm.ts` chatCompletion
- **状态**：vega retry.py 已写（待接入），spica 待写

### 2. spica VegaClient 无超时
- **问题**：vega serve 挂了/慢了 → spica `fetch()` 永久卡死
- **影响**：spica 启动时卡在 profile 获取，无法降级
- **修复**：fetch 加 `AbortController` 超时（profile 10s，retrieve 30s），超时后返 null 继续无画像写作
- **文件**：`src/engine/vega-client.ts`

### 3. vega serve profile 无超时保护
- **问题**：build_profile_from_lightrag 跑 7 分钟，HTTP 无超时 → 客户端断开但服务端还在跑
- **影响**：serve 线程被占满
- **修复**：FastAPI 加请求超时（10min）+ 后台任务模式（立即返 202，完成后回调）

### 4. spica revisor 大段重复
- **问题**：第 2 章出现「大段重复」（前半段在后半段重复），revisor edit 误追加
- **影响**：正文质量下降，text-validation 告警但未阻断
- **修复**：harness tool-guard 的 edit/write 限制已设 3000 字，但 revisor 仍可能重复。加 post-revise 去重检查（相似度 >0.8 的段落截断）
- **文件**：`src/engine/multi-chapter.ts` revisor 闭环后 + `src/workflow/text-validation.ts`

---

## P1：影响质量但不崩溃的（应该修）

### 5. vega LightRAG `<|COMPLETE|>` hack 脆弱
- **问题**：靠检查 system_prompt 含 "entity" + "extraction" 判断是否补分隔符，不精确
- **影响**：非抽取的 LLM 调用可能误加分隔符，或抽取调用漏加
- **修复**：LightRAG 有 `entity_extraction_use_json=True` 选项（JSON 模式不需要分隔符），切回 JSON 模式 + 修复之前 JSON 模式的图合并问题

### 6. vega 并行分片 shard 失败无隔离
- **问题**：4 分片并行，1 个失败 → asyncio.gather 全部失败
- **影响**：1 个 shard 的 LLM 故障导致全部重来
- **修复**：`asyncio.gather(*tasks, return_exceptions=True)`，失败的 shard 返空 graph，其余正常合并

### 7. vega profile 缓存无失效机制
- **问题**：缓存永不过期，ingest 新数据后 profile 不更新
- **影响**：增补章节后画像过时
- **修复**：缓存加时间戳，graphml 修改时间 > 缓存时间 → 失效重算；或手动 `?refresh=true`（已实现）

### 8. spica journal 损坏无恢复
- **问题**：journal JSONL 写入中断（Ctrl+C / 崩溃）→ 最后一行截断 → resumeFrom 解析失败
- **影响**：续跑失败，需手动删 journal
- **修复**：loadJournal 加 try-catch 跳过损坏行（已部分实现，需验证）

### 9. spica Ollama 断连无降级
- **问题**：Ollama 服务挂了 → embed 失败 → 向量索引/检索全挂
- **影响**：多路召回只剩结构化路，向量路断
- **现状**：已有 try-catch 降级跳过（`向量检索失败,降级跳过`），但 retry 未接入
- **修复**：embed 调用接 with_retry，3 次后降级

---

## P2：规模化才暴露的（后续修）

### 10. vega serve 无并发控制
- **问题**：多请求同时跑 build_profile → DeepSeek 并发过高 → 429 雪崩
- **修复**：信号量限并发（同时最多 2 个 profile 计算），其余排队

### 11. vega LightRAG 全量 ingest 断点续跑
- **问题**：1369 章跑到 800 章断了 → 只能从头重来（LightRAG 无断点）
- **修复**：分片模式下每 shard 独立续跑（shard 内 LightRAG 有 LLM cache，重跑跳过已缓存 chunk）

### 12. spica 长篇上下文膨胀
- **问题**：写到 100+ 章，arc_summary + retrieval + vega 画像 + 角色状态 → prompt 爆炸
- **现状**：有滚动窗口（arc_summary 最近 5 章）+ 多路召回合并，但未压测
- **修复**：加 prompt token 计数 + 自动截断策略（远章摘要压缩、画像精简）

### 13. 成本监控
- **问题**：不知道跑一本书花多少钱
- **修复**：LLM 调用记 token 数 + 费用 → 每章/全书成本报告

---

## 实施顺序

1. **P0.1** vega retry.py 接入 llm.py + spica llm.ts（最高优先，防崩溃）
2. **P0.2** spica VegaClient fetch 超时（防卡死）
3. **P0.4** spica revisor 去重（防正文质量）
4. **P1.6** vega shard 失败隔离（防分片全挂）
5. **P1.9** spica Ollama retry（防向量断）
6. **P2** 规模化后再做
