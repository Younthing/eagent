# ADR-0004：Domain Risk 采用规则树判定（LLM 仅回答子问题）

状态：已接受

背景
- Domain 推理阶段目前由 LLM 同时输出子问题答案与 `domain_risk`。
- LLM 输出风险等级不可控，容易与 ROB2 决策树冲突，影响一致性与可复核性。
- `docs/rob2_reference/rob2_questions.md` 已定义 D1–D5 的决策树规则（D2 为 assignment）。

决策
- LLM 仅负责子问题答案、证据与理由。
- 领域风险 `domain_risk` 由规则树计算结果覆盖：
  - 规则树见 `src/rob2/decision_rules.py`。
  - 若某域规则缺失（当前 D2 adherence），保留 LLM 风险作为 fallback。

影响
- 优点：
  - 风险判定可复核、可解释，与 ROB2 标准一致。
  - 减少 LLM “自报风险”带来的波动。
- 代价：
  - 若规则树覆盖不完整，需要明确 fallback 行为。
  - 规则树维护成本上升（规则变更需同步到代码与文档）。
- 实现位置：
  - `src/rob2/decision_rules.py`
  - `src/pipelines/graphs/nodes/domains/common.py`
  - `tests/unit/test_domain_rules.py`
