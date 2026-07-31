# 贡献指南

感谢关注 Vega!这是一个把长文本织成知识图谱的通用引擎。

## 核心纪律(贡献前必读)

1. **内核领域中立(最高纪律)**:`src/vega/schemas/` 和 `src/vega/core/` 严禁出现任何领域词(角色/伏笔/修为/章节...)。内核只认通用概念:实体/关系/属性/事件/段/文档。领域概念一律进 `src/vega/plugins/<domain>/`。
2. **溯源防幻觉**:画像每个属性值必须挂 `Mention`(原文出处),无溯源不上画像。
3. **文档隔离**:每份文档一个知识库,互不污染。
4. **TDD**:pytest,纯逻辑(切段/名归一/聚合/合并)先单测再实现。

## 开发流程

```bash
uv sync --extra dev --extra serve --extra watch   # 装依赖
uv run pytest -q                                   # 跑测试
uv run ruff check src tests && uv run mypy src     # lint + 类型
```

提交前:ruff / mypy / pytest 全绿。

## 加一个新领域插件

1. 写个包,声明 entry point:
   ```toml
   [project.entry-points."vega.plugins"]
   legal = "your_pkg.legal:LegalPlugin"
   ```
2. 实现 `DomainPlugin`(`split_sections`/`focus_keywords`/`profile_*`/`extract_prompt`...)。
3. `pip install your-pkg` 后,`vega` 自动发现,`--plugin legal` 即用。内核一行不改。

参考:`src/vega/plugins/novel/`。

## 提交

- 中文 commit message,简述改动。
- 功能分支 + PR。
