# **ROB2 自动评估系统 – Implementation Milestones**


## 🟦 Milestone 0：需求冻结与科学基线确认（Baseline Lock）

### 🎯 目标

在任何代码实现之前，**冻结科学逻辑与系统边界**，避免后期返工。

### 核心任务

* 确认 ROB2 版本（Standard）
* 冻结五个 domain 的 decision-tree 逻辑
* 明确“什么算可接受证据，什么不算”
* 冻结证据粒度（段落级，而非句子级）

### 交付物（Deliverables）

* 冻结版 requirements.md（当前为 `docs/requirements.md`）
* 冻结版 architecture.md（当前为 `docs/architecture.md`）
* Domain 问题清单（归档于 `docs/rob2_reference/`，当前为 `docs/rob2_reference/rob2_questions.md`）

### 完成定义（DoD）

* 任何 domain 逻辑问题都有唯一、不可歧义的解释
* 评估者（人类）对该文档达成一致

> ⚠️ 没有完成这个里程碑，后续所有工程都是不稳的。

---

## 🟦 Milestone 1：文档解析与结构稳定性（Document Grounding）

### 🎯 目标

建立 **不可动摇的“文本地基”**，确保所有证据引用真实存在。

### 核心任务

* 使用 docling 解析 PDF → JSON
* 稳定生成：

  * paragraph_id
  * section hierarchy
  * page number
* 记录结构化 section（如 Abstracts/ Methods / Results / Supplement，若存在）

### 交付物

* Docling 解析模块
* 原文段落浏览 / 对照工具（CLI 或可视化）

### DoD

* 任意 paragraph_id 都能回溯到 PDF
* Docling 模型配置可显式指定并记录（通过 .env）

> ✅ 这是系统“反 hallucination”的第一道物理防线。

---

## 🟦 Milestone 2：Domain Question Planner

### 🎯 目标

让系统**知道要问哪些 ROB2 子问题**。

### 核心任务

* 实现 Domain Question Planner
* 输出规范化 ROB2 子问题列表

### 交付物

* 标准化 ROB2 question schema

### DoD

* 对同一篇论文，planner 输出稳定一致
> 这是 **问题拆解正确性** 的关键里程碑。

---

## 🟦 Milestone 3：Rule-Based Locator（结构优先证据定位）

### 🎯 目标

先构建 **最稳、最低 hallucination 风险的证据定位引擎**。

### 核心任务

* 基于 section title 的定位规则
* 基于关键词的候选段落筛选
* LLM 在候选段落中做 relevance 判断

### 交付物

* Rule-based evidence locator
* 每个 domain 的 section prior 规则表

### DoD

* 能在 ≥80% RCT 中稳定找到随机化、失访等关键段
* 不产生任何“原文不存在”的引用

> 📌 这是整个系统的 **Anchor Engine**。

---

## 🟦 Milestone 4：LLM-Aware Retrieval（多查询语义检索）

### 🎯 目标

提升 **证据召回率（Recall）**，防止规则漏检。

### 核心任务

* LLM Query Planner
* Multi-query generation
* BM25 + Dense + SPLADE 并行召回
* Rank fusion（RRF）

### 交付物

* Retrieval Engine（无结构裁剪）
* 检索结果分析工具（召回 vs 噪声）

### DoD

* 在复杂或写作不规范论文中，找到 rule-based 漏掉的证据
* 不直接进入 Domain 推理（仍是候选）

---

## 🟦 Milestone 5：Structure-Aware Retrieval（结构约束检索）

### 🎯 目标

显著降低 **IR 噪声和误召回**。

### 核心任务

* Domain → section priority 映射
* 在裁剪语料中运行 BM25 / Dense / SPLADE
* Section-weighted ranking

### 交付物

* 结构约束检索模块
* Section 权重配置表

### DoD

* Discussion 段落不会压过方法/结果类 section（若存在）
* 与 ROB2 domain 明显无关段落显著减少

---

## 🟦 Milestone 6：Evidence Fusion Agent（三引擎融合）

### 🎯 目标

把“多个可能对的证据”变成“少量高置信证据”。

### 核心任务

* 三引擎证据去重
* 一致性加权
* 来源标注
* Top-k 精选

### 交付物

* Evidence Fusion Agent
* 证据置信评分策略文档

### DoD

* 同一证据多引擎命中 → 自动提升优先级
* 单一来源、低置信证据不直接进入 Domain 推理

---

## 🟦 Milestone 7：Evidence Validation Layer（多级验证）

### 🎯 目标

**系统性消灭 hallucination 和逻辑污染**。

### 核心任务

* Evidence Existence Validator
* Relevance Validator
* Consistency Validator
* Completeness Validator

### 交付物

* 验证代理集合
* 回滚 / 重试逻辑
* 工作流装配与验证入口（`src/pipelines/graphs/rob2_graph.py`，`scripts/check_rob2_graph.py`）

### DoD

* 无法构造“伪证据通过系统”的反例
* 验证失败会自动回退到定位阶段

> 🚨 这是从“能跑”到“可信”的分水岭。

---

## 🟦 Milestone 8：Domain Reasoning Agents（D1–D5）

### 🎯 目标

让系统真正完成 **ROB2 decision-tree 推理**。

### 核心任务

* 每个 domain 独立 agent
* 子问题级别推理
* domain-level risk 生成

### 交付物

* D1–D5 Reasoning Agents
* decision-tree 对照测试用例

### 当前实现

* D1–D5 领域推理节点已落地，并接入 `rob2_graph`
* domain risk 由规则树判定（`src/rob2/decision_rules.py`），LLM 仅负责子问题答案与理由
* D1–D5 单元测试覆盖条件 NA 与规则判定

### 待补项

* 标准 benchmark 论文对齐与评测报告（见 `docs/evaluation/`）

### DoD

* 对标准 benchmark 论文，domain 判断与专家一致或更保守
* 不出现无证据判断

---

## 🟦 Milestone 9：Full-Text Domain Audit（全文审核与证据补全）

### 🎯 目标

在不改变“证据定位 → 过滤 → 领域推理”主干的前提下，引入一个**全文审核模型**：
对 D1–D5 的信号问题答案做一致性审核，**用原文引用补齐证据**，减少遗漏与误判。

### 核心任务

* 分域审核：每个 domain agent 后紧跟一个 audit（一次只看该域问题）
* 全文输入：audit 读取 `doc_structure.sections`（paragraph_id + text）并输出信号答案 + 引用（`paragraph_id` + quote）
* 补全与重跑：发现不一致/缺失时，把审核引用转成候选段落并合并到 `validated_candidates`，**立即重跑本域**（可开关）
* 可选：D5 后再跑一次 “all domains” final audit（仅做最终一致性报告）

### 交付物

* per-domain audit nodes（`d1_audit_node`…`d5_audit_node`，可开关）+ 可选 `final_domain_audit_node`
* 审核报告（mismatch 列表、补全证据、重跑域）
* `.env` / CLI 参数示例

### DoD

* 默认关闭（不影响现有流程），开启后能产出审核报告并可自动补全证据重跑
* 无法注入“doc_structure 不存在的 paragraph_id”（补全证据必须经过确定性校验）

---

## 🟦 Milestone 10：ROB2 Aggregator & Final Output

### 🎯 目标

生成 **可发表、可复核的最终结果**。

### 核心任务

* 汇总五域
* 生成 overall risk（当前实现口径：任一 High→High；全 Low→Low；无 High 且 4-5 个 Some concerns→High；无 High 且 1-3 个 Some concerns→Some concerns；无域结果→Not applicable）
* 输出表格 + JSON + 引文索引

### 当前实现

* `aggregate_node` 已接入工作流，产出：
  * `rob2_result`：结构化 JSON（含 overall、domains、citations）
  * `rob2_table_markdown`：可读表格（Markdown）

### DoD

* 输出可直接用于 systematic review
* 人类评估者可逐条追溯证据

---

## 🟩 Milestone 11（可选）：系统评估与科学验证

### 🎯 目标

证明系统“真的比人或 baseline 好”。

### 核心任务

* 与人工 ROB2 评估对比
* inter-rater agreement 分析
* error taxonomy

### 交付物

* 评估报告
* failure mode 分析

---

# 📌 总体实施节奏建议

| 阶段     | 目的         |
| ------ | ---------- |
| M0–M2  | 科学正确性与逻辑冻结 |
| M3–M5  | 证据定位能力最大化  |
| M6–M7  | 稳健性与可信度    |
| M8–M10 | 完整 ROB2 系统 |
| M11    | 学术/工程验证    |

---
