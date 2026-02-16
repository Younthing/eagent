# ADR-0010：Batch Run 采用单机多进程并行 + 自适应限流

状态：已接受

背景
- `rob2 batch run` 原实现为严格串行，1000+ 文献场景吞吐不足。
- 运行过程中存在上游模型 429/超时抖动，固定高并发容易导致失败率上升。
- 现有批处理依赖 `batch_checkpoint.json`（v2）与 `batch_summary.json/csv`，需要保持兼容，支持历史目录续跑。

决策
- 批处理执行从串行改为“主进程调度 + worker 并行执行”：
  - 文献级并行由 `--workers` 控制（单机多进程）。
  - 主进程仍是 checkpoint/summary 的唯一写入方，避免并发写冲突。
- 引入并发控制与抗抖机制：
  - `--rate-limit-mode adaptive|fixed`
  - `--rate-limit-init`、`--rate-limit-max`
  - `--retry-429-max`、`--retry-429-backoff-ms`（指数退避）
- 维持 checkpoint 兼容性：
  - 保持 `batch_checkpoint.json` 版本为 v2。
  - 仅追加 `runtime_meta` 运行指标，不改变既有字段语义。

实现
- `src/cli/commands/batch.py`
  - 新增并行任务执行器与调度循环。
  - 新增 `_AdaptiveConcurrencyController` 与可重试错误识别。
  - 新增批处理运行时参数：`--workers`、`--max-inflight-llm`、`--rate-limit-*`、`--retry-429-*`、`--prefetch`。
  - `batch_summary.json` 新增 `runtime_meta`（吞吐、平均耗时、p95 等）。
- `src/core/config.py`
  - 新增 `BATCH_WORKERS`、`MAX_INFLIGHT_LLM`、`RATE_LIMIT_*`、`RETRY_429_*` 配置。
- `src/schemas/requests.py`
  - 新增并发/限流相关运行字段，便于 API/CLI 对齐。

影响
- 优点：
  - 在单机条件下显著提高批量吞吐。
  - 在 429/超时场景下，通过自适应收敛降低失败率与重跑成本。
  - 与既有 checkpoint/summary 消费链保持兼容。
- 代价：
  - 实现复杂度增加（调度、重试、并发状态管理）。
  - 运行日志与状态转换更复杂，需要更完整测试覆盖。
