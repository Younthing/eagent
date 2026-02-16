# **ROB2 自动化风险偏倚评估系统

需求说明文档（Requirements Specification）**

---

## 1. 项目背景（Background）

系统评价（Systematic Review）与 Meta-analysis 中，对随机对照试验（Randomized Controlled Trials, RCTs）进行 **Risk of Bias 2 (ROB2)** 评估是一项高度专业、耗时且一致性要求极高的工作。

传统人工评估存在以下问题：

* 成本高、耗时长
* 评估者之间一致性有限
* 难以规模化
* 缺乏可复用的中间证据结构

近年来，大语言模型（LLM）在文本理解与推理方面取得显著进展，为自动化 ROB2 评估提供了可能性。但 **直接使用 LLM 进行端到端判断存在 hallucination、证据不可追溯、决策树不稳定等风险**。

本项目旨在构建一个 **以证据为中心、结构化、可验证、多代理协作的 ROB2 自动识别系统**，优先保证科学正确性与稳健性，而非计算效率。

---

## 2. 总体目标（Overall Objective）

设计并实现一个 **基于 LangGraph 的多代理系统**，能够：

1. 自动识别 RCT 文献中的 ROB2 偏倚问题
2. 精确定位并引用支持判断的原文证据
3. 严格遵循 ROB2 decision-tree 逻辑
4. 输出可解释、可验证、可复现的评估结果

系统应达到 **研究级 / 临床证据级可靠性**，而非仅用于演示或探索。
默认按 **Standard ROB2** 评估，Cluster/Crossover 变体不在当前范围。

---

## 3. 设计原则（Design Principles）

### 3.1 正确性优先（Correctness First）

* 不以 token、时间或系统复杂度为主要约束
* 宁可冗余，也不牺牲准确性
* 不接受“合理但未被证据支持”的判断

### 3.2 证据中心（Evidence-Centric）

* 所有判断必须可追溯到原文证据
* 不允许无证据推断
* 证据必须可被机器验证存在性

### 3.3 多重冗余与交叉验证（Redundancy & Cross-validation）

* 多种证据定位机制并行
* 多级验证代理防止 hallucination
* 域内、域间一致性检查

### 3.4 结构化与可扩展性（Structured & Extensible）

* 系统结构清晰、职责边界明确
* 允许后续引入新 ROB 版本（如 ROBINS-I）
* 允许替换或升级检索与模型组件
* 允许通过配置切换领域推理与审计提示词语言（中文/英文）

---

## 4. 系统输入与输出（System I/O）

### 4.1 输入（Inputs）

* RCT 论文 PDF（可能包含主文与补充材料）

### 4.2 输出（Outputs）

* ROB2 五个 domain 的风险判断
* Overall risk of bias
* 每个 ROB2 子问题的回答
* 对应的原文证据引用（段落级）
* 文档元数据（标题/作者/年份/机构/基金会）
* 结构化输出（表格 + JSON）
* 批量运行时的经典红绿灯图（PNG，Overall + D1..D5 矩阵）
* 批量运行时的可审计 Excel 汇总（XLSX，多 sheet 覆盖总览/决策路径/问答/证据/元信息/审计差异）
* 批量运行支持单机多进程并发、429/超时自适应限流、断点续跑与 checkpoint 兼容

---

## 5. 系统总体架构（High-level Architecture）

系统采用 **LangGraph 状态机 + 多代理并行架构**，主要由以下层级组成：

1. 文档解析与结构化层
2. ROB2 问题规划层
3. 证据定位层（多引擎并行）
4. 证据融合与验证层
5. Domain 推理层（D1–D5）
6. 跨域一致性验证
7. ROB2 汇总与输出层

### 5.1 架构与工程化文档

项目结构、模块分层、接口契约与协作流程详见 `docs/architecture.md`。

---

## 6. 文档解析与结构化层（Preprocessing Layer）

### 6.1 功能需求

* 将 PDF 解析为结构化 JSON（使用 docling 或同类工具）
* 保留：

  * paragraph_id
  * section 层级
  * 页码信息
* 提供全文字符串版本供 LLM 使用
* 解析模型/管线配置可显式指定并记录
* 默认 Docling chunker 模型：`malteos/PubMedNCL`（可通过 `DOCLING_CHUNKER_MODEL` 覆盖）

### 6.2 Doc Scope Selector（混排 PDF 主文裁剪）

* 识别同一 PDF 中混入的第二篇摘要/广告/附录等非主文内容，自动选出主文章段落范围并裁剪（保守策略）
* 支持中英文信号（Abstract/摘要、Keywords/关键词、DOI、Methods/Results/Discussion/References 等）
* 手动模式允许指定 `paragraph_id` 列表进行段落级裁剪；页面范围仅作为兜底
* 输出 `doc_scope_report` 记录置信度与裁剪范围；低置信度时不裁剪，仅提示

### 6.3 设计约束

* 不允许丢失方法学关键段落
* 段落 ID 必须稳定、可追溯

---

## 7. Domain Question Planner（ROB2 问题规划）

### 7.1 功能需求

* 将 ROB2 五个 domain 拆解为标准化子问题
* 每个问题具有唯一 question_id
* 问题粒度与 ROB2 decision-tree 一致

### 7.2 输出要求

* 机器可读的问题列表
* 可作为证据定位的最小查询单元

---

## 8. 证据定位层（Evidence Location Layer）

### 8.1 总体目标

在保证 **高召回（recall）与高精度（precision）** 的前提下，定位与每个 ROB2 子问题相关的原文证据。

### 8.2 设计原则

* 多引擎并行，而非互斥
* 不依赖单一检索技术
* 结构信息优先于纯语义相似度

---

### 8.3 三重证据定位引擎

#### A. FullText Locator

* LLM 在全文上下文中直接查找相关段落
* 优点：语义理解强
* 风险：hallucination（由验证层控制）

#### B. Rule-Based Locator

* 基于论文结构（Methods/Results 等，如存在）
* 基于关键词与启发式规则
* 提供最稳定的“锚点证据”

#### C. Retrieval Engine（高级检索引擎）

##### C.1 LLM-Aware Retrieval

* LLM 自动生成多版本检索 query
* 覆盖术语变体、同义表达、否定线索
* 提高 recall

##### C.2 Structure-Aware Retrieval

* 根据 domain 优先检索特定 section
* 在结构裁剪后的语料中运行检索
* 降低误召回

##### C.3 检索技术组合

* BM25（词法）
* Dense embedding（语义）
* SPLADE（稀疏 transformer）
* Rank fusion（RRF）
* Cross-encoder / LLM reranker

---

## 9. Evidence Fusion Agent（证据融合）

### 9.1 功能需求

* 合并来自三种引擎的证据
* 基于来源一致性赋予置信权重
* 去重、排序、标准化

### 9.2 输出要求

* 每个问题返回有限（3–5）条高置信证据
* 每条证据必须包含 paragraph_id 与原文摘录

---

## 10. Evidence Validation Layer（证据验证层）

为防止 hallucination 与逻辑错误，系统必须包含多级验证代理。

### 10.1 验证类型

1. **Existence Validator**

   * 验证证据文本是否真实存在于原文

2. **Relevance Validator**

   * 验证证据是否真正回答该问题

3. **Consistency Validator**

   * 检查不同引擎或证据之间是否矛盾

4. **Completeness Validator**

   * 确保 domain 所需的关键信息齐全

### 10.2 行为

* 验证失败 → 触发证据重定位或融合重做

---

## 11. Domain Reasoning Agents（D1–D5）

### 11.1 功能需求

* 每个 domain 独立 agent
* 严格按 ROB2 decision-tree 推理
* 输入：问题 + 已验证证据
* 输出：子问题回答 + domain risk

### 11.2 设计约束

* 不允许跨 domain 推理
* 不允许无证据判断
* D5 的 q5_2/q5_3 仅在存在“直接选择性报告证据”时可回答 Y/PY；仅有多时间点/多阈值/多检验/多候选分析信息不足以判 Y/PY。
* 当无法核验预设方案与选择透明度时，D5 的 q5_2/q5_3 默认倾向 NI。

---

## 12. Cross-Domain Validator（跨域一致性）

### 12.1 功能需求

* 检查 domain 之间的逻辑冲突
* 发现冲突时触发回滚或重评

---

## 13. ROB2 Aggregator（汇总）

### 13.1 功能需求

* 汇总五个 domain 风险
* 按当前实现口径生成 overall risk：
  - 任一 domain 为 High → overall High
  - 所有 domain 为 Low → overall Low
  - 无 High 且 Some concerns 的 domain 数量为 4–5 → overall High
  - 无 High 且 Some concerns 的 domain 数量为 1–3 → overall Some concerns
  - 无任何 domain 结果 → overall Not applicable
* 输出结构化结果

---

## 14. 非功能性需求（Non-functional Requirements）

### 14.1 可解释性

* 每个判断必须可追溯到证据

### 14.2 可复现性

* 相同输入在相同配置下应产生一致结果

### 14.3 可扩展性

* 支持引入新检索模型、新验证代理、新 ROB 版本

---

## 15. 明确不在当前范围内（Out of Scope）

* 预测试验质量（非偏倚）
* 自动生成 meta-analysis 结果
* 临床结论推断
* Cluster/Crossover ROB2 变体
* 用户界面设计（UI）

---

## 16. 总结

本系统不是“让 LLM 判断 ROB2”，
而是 **构建一个以证据为核心、多代理协作、严格受控的科学评估系统**。

LLM 的角色是：

* 检索规划者
* 证据筛选者
* 逻辑推理者

而不是：

* 终极裁判
* 自由发挥的文本生成器

这正是系统能够达到 **研究级可信度** 的根本原因。
