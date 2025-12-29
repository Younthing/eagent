# ADR-0003：Validation 模式配置与 Completeness 放宽策略

状态：已接受

背景
- M7 验证层在 LangGraph 工作流中反复重试，validator 节点会输出 `*_validator` 的元数据。
- 之前配置与输出共用同一 key（例如 `relevance_validator`），导致重试时配置被覆盖，引发模式识别失败。
- 当 `relevance_mode=none`（不使用 LLM 相关性判断）时，Completeness 仍要求 relevance 通过，会导致所有题目“缺证据”，阻塞后续推理。
- 需要明确区分配置与输出，保证无 LLM 也能产出可用证据。

决策
- 将 validator 的模式配置明确为输入键：
  - `relevance_mode` / `consistency_mode`
  - `*_validator` 仅作为输出元数据保留
- Completeness 新增 `completeness_require_relevance`：
  - 默认：当 `relevance_mode != "none"` 时要求 relevance；当 `relevance_mode == "none"` 时不要求。
- 重试放宽策略（可控开关 `validation_relax_on_retry`）：
  - 降低 `relevance_min_confidence`
  - 关闭 quote/text 严格匹配
  - 强制 `completeness_require_relevance=False`

影响
- 优点：
  - 配置与输出分离，避免状态污染与重试失败。
  - 关闭 LLM 相关性时仍能提供证据，保证后续代理可继续推理。
  - 放宽策略集中在重试路径，默认仍保留严格校验。
- 代价：
  - 放宽后证据质量下降，需要在结果解释/审计时标注。
  - 这是一次不向后兼容的变更：调用侧需改为使用 `*_mode`。
- 实现位置：
  - `src/pipelines/graphs/rob2_graph.py`
  - `src/pipelines/graphs/nodes/validators/relevance.py`
  - `src/pipelines/graphs/nodes/validators/consistency.py`
  - `src/pipelines/graphs/nodes/validators/completeness.py`
  - `scripts/check_rob2_graph.py`
