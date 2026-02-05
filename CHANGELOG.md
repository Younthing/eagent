# Changelog

## 0.1.6 - 2026-02-05
- 新增 `rob2 batch plot` 命令，可从批量输出目录或 `batch_summary.json` 生成经典红绿灯矩阵图（PNG）。
- `rob2 batch run` 新增 `--plot/--no-plot` 与 `--plot-output`，默认自动生成 `batch_traffic_light.png`。
- 批量红绿灯图支持 legacy 风险值兼容（`some concerns` / `some-concerns`）。
- 补充批量绘图相关单测/集成测试与 CLI 文档、系统文档同步。

## 0.1.5 - 2026-02-05
- 新增持久化子系统（SQLite 元数据 + 文件系统 artifacts），并输出 `run_id` 方便追踪。
- `run_rob2` 支持持久化/缓存上下文，CLI 增加 `--persist*`、`--batch*`、`--cache*` 参数。
- 确定性阶段缓存（preprocess / BM25 / SPLADE）可复用，`rob2 cache` 新增持久化统计与 `prune` 清理。
- 新增持久化与缓存的单测/集成测试覆盖。

## 0.1.4 - 2026-02-05
- 预处理阶段新增 Doc Scope Selector，自动/手动裁剪混排 PDF 的主文段落范围。
- 支持段落级手动选择与 `doc_scope_report` 输出，配置项与文档同步更新。
- Domain 决策结果新增 `rule_trace`，记录命中的规则路径并透传到最终输出。
- CLI `rob2 run` 默认写入 `./results/result.json`（以及表格/报告按配置输出）。
- HTML/DOCX/PDF 报告新增 `rule_trace` 展示，报告模块拆分为上下文与渲染逻辑。

## 0.1.3 - 2026-02-04
- 新增 LLM ReAct 证据定位线并与检索/规则候选并集融合。
- 证据候选支持 `supporting_quote` 并贯通融合/验证。
- 新增 LLM Locator 配置项与示例环境变量。

## 0.1.2 - 2026-02-03
- 默认将 `validation_max_retries` 提升为 3，并且仅重试失败问题。
- 验证重试耗尽后自动启用全文审计补证并重跑领域。
- 证据定位、融合与验证流程支持局部重试合并。
- 文档与测试更新以覆盖上述流程。
