# ADR-0005：Milestone 9 采用“全文审核模型 + 证据补全重跑”（不直接覆盖答案）

状态：已接受

背景
- Milestone 7 对证据做了严格的存在性/相关性/一致性/完整性验证，确保“证据是真的”。
- Milestone 8 的 domain agent 只能看到 `validated_candidates`（过滤后的证据），仍可能因为召回不足导致：
  - 子问题回答为 `NI`（漏检）
  - 或基于有限证据得出错误信号判断（误判）
- 进一步增加强制性硬规则（除已实现的决策树风险判定外）会导致系统复杂度上升、可维护性下降。

决策
- 将 Milestone 9 定义为**可开关的全文审核层**：
  1. 审核模型输入 `doc_structure.sections`（全文段落 + `paragraph_id`）与 ROB2 子问题清单。
  2. 输出每个子问题的信号答案（Y/PY/PN/N/NI/NA）与引用（`paragraph_id` + 原文 quote）。
  3. 与 domain agent 的信号答案对比；如发现不一致/缺失，使用审核引用生成“弱定位证据”候选段落。
  4. 候选段落必须通过确定性校验（`paragraph_id` 存在；quote 可选但若提供必须匹配原文）后，合并到 `validated_candidates`。
  5. 在不直接覆盖答案的前提下，**重跑受影响的 domain agent**，让最终答案仍由“证据驱动的 domain agent + 决策树规则”产出。
- 默认关闭（不影响现有流程），通过 `.env` / CLI 开关启用。

影响
- 优点：
  - 审核模型具备全文视野，可用于查漏补缺，提升召回与一致性。
  - 不引入新的强制硬规则；最终答案仍由 domain agent 产出，保持系统主干一致。
  - 审核引用会被确定性校验，避免注入不存在的段落引用。
- 代价：
  - 成本上升（需要额外 LLM 调用 + 可能的 domain 重跑）。
  - 上下文更大（依赖长上下文模型更稳）。

实现位置
- `src/pipelines/graphs/nodes/domain_audit.py`
- `src/llm/prompts/validators/domain_audit_system.md`
- `src/pipelines/graphs/rob2_graph.py`
- `src/core/config.py`、`.env.example`
- `tests/unit/test_domain_audit.py`

