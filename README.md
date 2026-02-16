# eAgent / ROB2

**eAgent** 是一个用于 **ROB2（Risk of Bias 2）风险偏倚评估**的自动化流水线与调试工具，面向临床试验文献（PDF）。
系统以 *可追溯、可验证、可纠错* 为核心设计目标，将 ROB2 评估过程工程化为一条显式、可审计、可复现的工作流。

与基于“单轮问答”的评估方式不同，eAgent 并不直接生成判断结果，而是将 **证据定位 → 验证 → 领域推理 → 聚合决策** 拆解为多个有状态节点，并通过验证失败回滚与领域审计机制形成闭环。

---

## 快速开始

```bash
uv run rob2 -h
uv run rob2 run /path/to.pdf --json
```

### 批量并行运行（1000+ 文献）

```bash
uv run rob2 batch run /path/to/pdfs \
  --workers 4 \
  --max-inflight-llm 8 \
  --rate-limit-mode adaptive \
  --rate-limit-init 2 \
  --rate-limit-max 4 \
  --retry-429-max 4 \
  --retry-429-backoff-ms 800
```

说明：
* `--workers` 控制文献级并发（单机多进程）。
* `--rate-limit-mode adaptive` 在出现 429/超时时会自动下调并发额度，连续成功后再小步回升。
* 批量 summary 会保留 `runtime_meta`（吞吐、平均耗时、p95 等运行指标）。

---

## 系统概览

eAgent 基于 **LangGraph** 构建，用于自动执行 **Standard ROB2** 风险偏倚评估流程。
整体流程分为六个阶段：

1. 文档预处理与结构化建模
2. 多策略证据定位与融合
3. 证据验证与失败回滚
4. D1–D5 领域推理与规则决策
5. 可选领域 / 全域审计
6. 结果聚合与工程化输出

每一阶段都会生成可追踪的中间产物，并显式记录证据来源、验证结论与决策路径。

---

## 设计目标与核心思想

eAgent 的设计并非追求“更聪明的模型”，而是关注 **ROB2 评估本身的可靠性**：

* **流程显式化**：每一步都对应明确的评估阶段
* **证据优先**：判断必须绑定可定位的原文证据
* **验证驱动**：不满足验证条件的证据不会进入推理
* **失败可纠错**：通过回滚与审计减少遗漏与幻觉
* **结果可解释**：最终结论可回溯到证据与规则

---

## 工作流与方法

### 总体工作流

```text
preprocess
  → planner
    → locators (rule / bm25 / splade / llm)
      → fusion
        → validators
          → domains (D1–D5)
            → aggregate
```

---

### 1. 文档预处理与建模

系统首先对 PDF 文献进行结构化解析，建立可用于检索与引用的文档表示：

* 基于 Docling 的正文与段落解析
* 自动或手动的文档范围裁剪
* 参考文献段落过滤（基于标题规则）
* 文献元信息抽取（可选 LLM）
* 图像与图表内容提取与描述（可选 LLM）

预处理结果会被缓存，当文档内容未发生变化时可直接复用。

---

### 2. 多策略证据定位与融合

为降低单一检索策略的系统性偏差，eAgent 采用并行、多源的证据定位方式：

* 基于规则的定位（ROB2 特定模式）
* BM25 关键词检索
* 中文检索分词：`pkuseg_medicine` / `pkuseg` / `jieba`（含 CJK n-gram 兜底）
* SPLADE 稀疏向量检索（RAG）
* LLM 驱动定位（可选）

检索结果在进入推理前会经过统一融合：

* RRF（Reciprocal Rank Fusion）排序
* 可配置的融合权重
* section priors 与 section bonus 加权
* 可选交叉编码重排

---

### 3. 证据验证与失败回滚

所有候选证据必须通过验证层，验证包括：

* **相关性验证**：证据是否回答当前问题
* **存在性验证**：证据是否真实存在于原文
* **一致性验证**：证据之间是否存在冲突
* **完整性验证**：是否覆盖必要信息

当验证失败时，系统不会继续推理，而是：

* 回滚至证据定位阶段
* 放宽检索约束、扩大召回范围
* 重新进入验证链

对于确实无法获取信息的情况，系统采用显式的 **NI（No Information）策略**，而非直接给出判断。

---

### 4. D1–D5 领域推理与规则决策

ROB2 的五个领域（D1–D5）分别由独立节点处理：

* 每个领域基于验证通过的证据进行推理
* 统一采用结构化 JSON 输出
* 决策由规则树完成，并输出可解释的 `rule_trace`
* D2 支持 *assignment* 与 *adherence* 双分支题集

领域推理仅在证据充分且验证通过的前提下执行。

---

### 5. 领域审计与补丁机制

为降低遗漏证据带来的风险，eAgent 支持可选的审计流程：

* 针对单一领域或全部领域触发
* 基于全文重新补充证据
* 更新候选集合并重跑该领域推理

该机制允许系统在初次判断后进行自我修正，而不是一次性冻结结果。

---

### 6. 结果聚合与输出

最终聚合阶段生成标准化的 ROB2 输出，并保留完整的证据与决策轨迹：

* `result.json`：标准 ROB2 结构化结果
* Markdown 汇总表
* HTML / Word / PDF 报告（可选）
* 验证报告与审计报告
* 调试状态快照

系统支持批量处理、checkpoint 恢复与跨文档汇总。

---

## 模型与运行配置

eAgent 继承 LangChain / LangGraph 的模型抽象层，支持多模型、多提供商组合使用，包括但不限于：

* OpenAI
* Anthropic
* Google (Gemini)
* Hugging Face Hub
* Azure OpenAI
* AWS Bedrock
* Ollama（本地模型）

不同阶段可使用不同模型，例如检索规划、验证、领域推理与审计。

---

## 追踪、复现与工程能力

* LangSmith 在线追踪（节点级输入输出）
* SQLite + 文件制品持久化
* 运行缓存与结果复用
* 批量处理与结果汇总（CSV / Excel / 交通灯图）

---

## LangSmith 评估

eAgent 使用 **LangSmith ** 做评估与优化：

* **Dataset 管理**：可在 LangSmith 持续添加/维护评测样本
* **批量评测（Evaluations）**：基于数据集对不同版本进行批量对比
* **提示词优化**：结合失败样例与 Trace 迭代提示词，再次发起批测验证
* **本地处理联动**：`rob2 run` / `rob2 batch run` 的调用链会归档到同一项目，便于统一分析

环境变量配置：

```bash
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=lsv2-...
LANGSMITH_PROJECT=literature-agent
```

推荐使用流程：

1. 在 LangSmith 中在线创建或补充 Dataset（评测样本持续沉淀）。
2. 本地运行 `uv run rob2 batch run <pdf_dir> --json` 生成一轮结果与 Trace。
3. 在 LangSmith Evaluations 中选择 Dataset 与目标版本，执行在线批量评测。
4. 根据评测结果优化 `src/llm/prompts/`，再回到步骤 2-3 做闭环迭代。

---

## API（轻量）

```bash
uv run uvicorn api.main:app --reload
```

* `GET /health`
* `GET /config`
* `POST /preprocess`
* `POST /graph/run`

---
