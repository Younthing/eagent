# ADR-0009：Overall Risk 采用分层保守聚合，并收紧 D5 q5_2/q5_3 的 Y 判定

状态：已接受（Supersedes ADR-0006）

背景
- 现有实现希望在 overall 风险上对“广泛但未达单域 High 的系统性疑虑”进行上调，避免低估总体偏倚风险。
- D5 在实务中容易因“仅存在多重性”而误判 q5_2/q5_3 为 Y/PY，导致选择性报告偏倚高估。
- 需要把实现口径、提示词口径与文档口径统一，避免代码与规范不一致。

决策
- Overall risk 改为分层保守聚合：
  1. 任一领域为 **High** → overall **High**。
  2. 所有领域为 **Low** → overall **Low**。
  3. 无 High 且 **Some concerns** 领域数为 4-5 → overall **High**。
  4. 无 High 且 **Some concerns** 领域数为 1-3 → overall **Some concerns**。
  5. 无领域结果 → overall **Not applicable**。
- D5 q5_2/q5_3 采用“直接证据门槛”：
  - 仅出现多时间点/多阈值/多检验/多候选分析，不足以判 Y/PY。
  - 只有存在直接选择性报告证据（如预设与发表结果不一致且无说明、方法列多选但结果无透明选择）时，才可判 Y/PY。
  - 无法核验预设与选择透明度时，默认倾向 NI。

实现
- `src/pipelines/graphs/nodes/aggregate.py`：更新 `_compute_overall_risk()` 的 overall 聚合逻辑。
- `src/llm/prompts/domains/d5_system.md`
- `src/llm/prompts/domains/d5_system.en.md`
- `src/llm/prompts/domains/d5_system.zh.md`
- `docs/rob2_reference/rob2_questions.md`：补充 D5 判定口径与 overall 聚合规则参考。

影响
- 优点：
  - overall 结果对多域“Some concerns”更敏感，降低总体低估风险。
  - D5 对 q5_2/q5_3 的 Y/PY 判定更依赖直接证据，减少“仅因多重性导致的误报”。
- 代价：
  - Overall 规则与 ROB2 Standard 的经典口径不同，需要在评测/对外说明中显式标注当前实现规则。
  - 文档、评测基准和下游解释口径必须同步更新，避免混淆。
