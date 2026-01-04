# ADR-0006：Overall Risk 聚合规则采用 ROB2 Standard 规则（非“多 Some concerns 升级 High”）

状态：已接受

背景
- Milestone 10 需要从五个 domain risk 汇总 overall risk。
- 之前实现采用了一个工程化近似：若出现多个 “Some concerns” 则整体升级为 “High”。
- 该策略与我们想要对齐的 ROB2 Standard overall judgement 规则不一致。

决策
采用以下 overall risk 规则（Standard）：
1. 若任一领域为 **High risk**，则 overall risk 为 **High risk**。
2. 若所有领域均为 **Low risk**（且无 High），则 overall risk 为 **Low risk**。
3. 若至少一个领域为 **Some concerns**（且不满足 1/2），则 overall risk 为 **Some concerns**。
4. 若没有提供任何领域评估结果，则 overall risk 为 **Not applicable**。

实现
- `src/pipelines/graphs/nodes/aggregate.py`：`_compute_overall_risk()` 按上述规则计算。
- `src/schemas/internal/results.py`：`Rob2OverallResult.risk` 扩展为包含 `not_applicable`。
- `tests/unit/test_rob2_aggregate.py`：更新 overall risk 的测试用例。

影响
- 输出更贴近 ROB2 Standard，可用于后续评测对齐与论文级输出。
- 去除“多 Some concerns 升级 High”的额外假设，避免过度保守导致与金标准偏离。

