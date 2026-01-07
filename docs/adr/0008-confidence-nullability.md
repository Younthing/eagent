# ADR-0008：置信度字段允许为空并由模型自报

状态：已接受

背景
- `result.json` 与验证报告中包含 `confidence` 字段，但运行结果出现 `null`。
- 当前系统并未对置信度做规则化计算，字段值仅来自模型输出或验证器返回。
- 在缺少 LLM、模型未返回置信度或调用失败时，需要有明确的处理策略。

决策
- `confidence` 保持可选字段，仅在模型明确返回时填写。
- 当 LLM 未启用、失败或未返回置信度时，统一保留为 `null`，不进行默认值或启发式补齐。
- 下游消费方需要容忍 `null`，将其视作“未知置信度”。

实现
- 领域推理输出：`src/schemas/internal/decisions.py` 的 `DomainAnswer.confidence` 为可选；`src/pipelines/graphs/nodes/domains/common.py` 仅透传 LLM 的 `confidence`。
- 最终结果：`src/schemas/internal/results.py` 的 `Rob2AnswerResult.confidence` 可选；`src/pipelines/graphs/nodes/aggregate.py` 直接透传。
- 验证输出：`src/schemas/internal/evidence.py` 的 `RelevanceVerdict`/`ConsistencyVerdict` 均为可选；相关验证器在缺少模型或失败时返回 `confidence=None`。

影响
- 输出中 `confidence` 可能为 `null` 属于预期行为。
- 若未来需要强制置信度或补齐策略，应在提示词或规则层新增 ADR 并实现对应逻辑。
