# Evaluation Framework (Placeholder)

本目录用于存放 ROB2 评测框架相关说明与结果归档。当前先落地框架说明与 TODO，后续补齐基准论文与对齐结果。

## 范围

- 评测目标：验证 D1–D5 领域判定是否与专家一致或更保守。
- 评测输入：标准论文 PDF + 期望答案（子问题 + domain risk）。
- 评测输出：逐域评分 + 汇总报告（可追溯证据）。

## 计划结构

- `docs/evaluation/README.md`：评测说明与流程
- `docs/evaluation/results/`：评测报告（按日期/版本归档）
- `docs/evaluation/fixtures/`：基准论文与期望结果（后续补齐）
- `scripts/evaluate_rob2.py`：评测脚本（后续实现）

## 评测流程（草案）

1. 准备基准论文与期望输出（Y/PY/PN/N/NI/NA + domain risk）。
2. 运行 pipeline 产出系统结果（含证据引用）。
3. 逐题对齐并评分（exact / partial / conservative）。
4. 输出报告（覆盖率、偏差、错误类型）。

## TODO

- [ ] 明确 4 篇标准论文清单与来源
- [ ] 建立期望输出格式（JSON schema）
- [ ] 实现评测脚本入口与评分规则
- [ ] 输出示例报告与统计指标
