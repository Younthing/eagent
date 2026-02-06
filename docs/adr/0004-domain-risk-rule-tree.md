# ADR-0004：Domain Risk 采用规则树优先（规则不可算时回退 LLM）

状态：已接受

背景
- Domain 推理阶段目前由 LLM 同时输出子问题答案与 `domain_risk`。
- LLM 输出风险等级不可控，容易与 ROB2 决策树冲突，影响一致性与可复核性。
- `docs/rob2_reference/rob2_questions.md` 已定义 D1–D5 的决策树规则（D2 为 assignment）。

决策
- LLM 负责子问题答案、证据与理由，并继续输出 `domain_risk/domain_rationale` 作为回退字段。
- 领域风险 `domain_risk` 采用“规则树优先”：
  - 规则树见 `src/rob2/decision_rules.py`。
  - 当规则树可计算时，`risk` 直接使用规则结果。
  - 当规则树不可计算时，回退使用 LLM 的 `domain_risk`。
- `risk_rationale` 与 `risk` 来源绑定：
  - 规则树命中时，使用规则侧确定性解释（命中规则 + 关键问答）。
  - 回退 LLM 时，使用 LLM 的 `domain_rationale`。
- 回退路径下若 `domain_risk` 缺失或非法，抛出可定位错误。

影响
- 优点：
  - 风险判定可复核、可解释，与 ROB2 标准一致。
  - 减少 LLM “自报风险”带来的波动，同时保留规则缺失时的可用性。
  - 消除“规则风险 + LLM解释”混合冲突。
- 代价：
  - 若规则树覆盖不完整，需要维护并监控 fallback 行为。
  - 规则树维护成本上升（规则变更需同步到代码与文档）。
- 实现位置：
  - `src/rob2/decision_rules.py`
  - `src/pipelines/graphs/nodes/domains/common.py`
  - `tests/unit/test_domain_rules.py`
