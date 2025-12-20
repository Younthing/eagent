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

* 冻结版《需求说明文档》
* 冻结版系统架构图
* Domain 问题清单

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
* 验证 Methods / Results / Supplement 是否完整

### 交付物

* Docling 解析模块
* 原文段落浏览 / 对照工具（哪怕是 CLI）

### DoD

* 任意 paragraph_id 都能回溯到 PDF
* Methods 中的随机化描述不会被拆断或丢失

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

* Discussion 段落不会压过 Methods
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

### DoD

* 对标准 benchmark 论文，domain 判断与专家一致或更保守
* 不出现无证据判断

---

## 🟦 Milestone 9：Cross-Domain Validator

### 🎯 目标

消除 domain 间自相矛盾。

### 核心任务

* 定义跨域一致性规则
* 自动检测冲突
* 触发回滚或重评

### DoD

* 系统输出不再出现逻辑自相矛盾的 ROB2 表

---

## 🟦 Milestone 10：ROB2 Aggregator & Final Output

### 🎯 目标

生成 **可发表、可复核的最终结果**。

### 核心任务

* 汇总五域
* 生成 overall risk
* 输出表格 + JSON + 引文索引

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
