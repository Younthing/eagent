# ROB2 Target System Architecture (Standard)

This diagram captures the intended end-to-end architecture described in the requirements.
Scope is **Standard ROB2 only** (no trial-type branching).

```mermaid
flowchart TD
  subgraph Inputs
    A[Paper PDF]
  end

  subgraph Preprocessing
    C[Docling Parser]
    DS[Doc Scope Selector<br/>auto/manual]
    D[Structured Doc JSON<br/>body, sections, spans]
  end

  subgraph Planning
    E[Domain Question Planner<br/>Standard ROB2]
    F[Question Schema + Decision Trees]
  end

  subgraph EvidenceLocation[Evidence Location Layer]
    G1[LLM Locator (ReAct)]
    G2[Rule-Based Locator]
    G3[Retrieval Engine<br/>BM25/SPLADE]
  end

  subgraph EvidenceFusion
    H[Evidence Fusion Agent]
  end

  subgraph Validation
    I1[Existence Validator]
    I2[Relevance Validator]
    I3[Consistency Validator]
    I4[Completeness Validator]
  end

  subgraph Reasoning
    J1[D1 Randomization]
    J2[D2 Deviations]
    J3[D3 Missing Data]
    J4[D4 Outcome Measurement]
    J5[D5 Selective Reporting]
  end

  subgraph Audit
    K[Per-domain Full-Text Audit<br/>patch evidence + rerun]
  end

  subgraph Aggregation
    L[ROB2 Aggregator]
  end

  subgraph Outputs
    M[Report Table + JSON<br/>Evidence citations]
  end

  A --> C
  C --> DS
  DS --> D
  D --> E
  D --> G1
  D --> G2
  D --> G3
  F --> E
  F --> J1
  F --> J2
  F --> J3
  F --> J4
  F --> J5
  E --> G1
  E --> G2
  E --> G3
  G1 --> H
  G2 --> H
  G3 --> H
  H --> I1 --> I2 --> I3 --> I4
  I4 -->|pass| J1
  I4 -->|pass| J2
  I4 -->|pass| J3
  I4 -->|pass| J4
  I4 -->|pass| J5
  I4 -->|fail| G1
  I4 -->|fail| G2
  I4 -->|fail| G3
  J1 --> K
  J2 --> K
  J3 --> K
  J4 --> K
  J5 --> K
  K --> L --> M
```

Render with any Mermaid-compatible viewer (e.g., `npx @mermaid-js/mermaid-cli -i docs/architecture.md -o architecture.svg`).

### Preprocessing Notes

- 在 Docling 解析后引入 Doc Scope Selector，自动识别混排 PDF 的主文章段落范围；默认保守裁剪，低置信度时仅输出 `doc_scope_report` 提醒。
- 手动模式支持段落级 `paragraph_id` 选择，解决“同页多文章”场景；页面范围作为兜底。

### Repository Layout (Reference)

```text
eagent/
├── docs/                          # 需求/架构/ADR/评估基准/标注规范
│   ├── requirements.md
│   ├── architecture.md
│   ├── adr/
│   ├── evaluation/
│   └── rob2_reference/            # ROB2 decision tree/问题映射表/规则说明
│
├── src/
│   ├── api/                       # [Web层] FastAPI 路由与控制器
│   │   ├── dependencies.py        # 依赖注入：settings、clients、graph runner等
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── evaluate.py    # POST /evaluate (PDF->ROB2)
│   │       │   ├── jobs.py        # 可选：任务查询/重跑/下载报告
│   │       │   └── health.py
│   │       └── router.py
│   │
│   ├── core/                      # 配置、日志、异常、可观测性
│   │   ├── config.py              # Pydantic Settings (LLM/Retrieval/Graph flags)
│   │   ├── logging.py             # 结构化日志、request_id/trace_id
│   │   ├── exceptions.py
│   │   ├── telemetry.py           # tracing hooks(可选：OTel/LangSmith等)
│   │   └── feature_flags.py       # 可切换：启用RAG/启用某validator/模型选择
│   │
│   ├── services/                  # [核心服务层] CLI/API 共用的运行入口
│   │   ├── rob2_runner.py          # 统一参数解析/状态构建/图执行
│   │   └── io.py                   # PDF 临时文件处理
│   │
│   ├── reporting/                 # [报告层] HTML/DOCX/PDF 渲染
│   │   ├── __init__.py
│   │   ├── context.py             # 报告上下文/标签
│   │   ├── html.py                # HTML 渲染
│   │   ├── pdf.py                 # PDF 渲染
│   │   ├── docx.py                # DOCX 渲染
│   │   └── templates/
│   │       └── report.html
│   │
│   ├── schemas/                   # [DTO] FastAPI 入参/出参 + 内部契约
│   │   ├── requests.py            # EvaluateRequest (PDF元信息、选项)
│   │   ├── responses.py           # EvaluateResponse (ROB2表+证据引用)
│   │   └── internal/
│   │       ├── state.py           # GraphState（强建议：统一状态结构）
│   │       ├── evidence.py        # EvidenceSpan / EvidenceBundle
│   │       ├── rob2.py            # DomainAnswer / OverallJudgment
│   │       └── errors.py
│   │
│   ├── pipelines/                 # [编排层] 用 LangGraph 组织系统流程（骨架）
│   │   ├── graphs/
│   │   │   ├── rob2_graph.py      # 总图：三引擎定位→融合→验证→D1-5→汇总
│   │   │   ├── nodes/             # 每个节点一个文件，利于测试与复用
│   │   │   │   ├── preprocess.py  # Docling解析/Doc Scope裁剪/参考文献过滤
│   │   │   │   ├── planner.py     # ROB2问题规划
│   │   │   │   ├── locators/      # 证据定位引擎
│   │   │   │   │   ├── llm_locator.py
│   │   │   │   │   ├── rule_based.py
│   │   │   │   │   ├── retrieval_bm25.py
│   │   │   │   │   └── retrieval_splade.py
│   │   │   │   ├── fusion.py      # Evidence Fusion
│   │   │   │   ├── validators/    # Evidence validators (M7)
│   │   │   │   │   ├── existence.py
│   │   │   │   │   ├── relevance.py
│   │   │   │   │   ├── consistency.py
│   │   │   │   │   └── completeness.py
│   │   │   │   ├── domains/       # D1-D5 domain reasoners
│   │   │   │   │   ├── d1_randomization.py
│   │   │   │   │   ├── d2_deviations.py
│   │   │   │   │   ├── d3_missing.py
│   │   │   │   │   ├── d4_measurement.py
│   │   │   │   │   └── d5_reporting.py
│   │   │   │   ├── domain_audit.py # Full-text audit + evidence patch (M9)
│   │   │   │   └── aggregate.py   # ROB2汇总 + 输出整形
│   │   │   └── routing.py         # conditional edges/重试策略/回滚策略
│   │
│   ├── preprocessing/             # [预处理工具] 文档裁剪/范围选择
│   │   ├── __init__.py
│   │   └── doc_scope.py           # 混排PDF主文裁剪/手动段落选择
│   │
│   ├── llm/                       # [LLM层] 模型客户端与提示词资产（LangChain更常用）
│   │   ├── clients.py             # OpenAI/本地模型/多模型路由
│   │   ├── prompts/               # 提示词版本管理（强建议）
│   │   │   ├── evidence_locator/
│   │   │   ├── validators/
│   │   │   └── domains/
│   │   ├── output_parsers.py      # 结构化输出解析/校验
│   │   └── policies.py            # 温度、重试、最大token等策略
│   │
│   ├── retrieval/                 # [检索层] 纯IR能力，和graph节点解耦（可替换）
│   │   ├── index/                 # 索引构建（段落embedding、bm25索引等）
│   │   │   ├── build.py
│   │   │   └── stores.py          # faiss/chroma/elasticsearch/自研
│   │   ├── query_planning/        # LLM-Aware Retrieval
│   │   │   ├── planner.py         # 生成多query（词法/语义/术语/否定）
│   │   │   └── templates.py
│   │   ├── structure/             # Structure-Aware Retrieval
│   │   │   ├── section_prior.py   # Domain->section优先级映射
│   │   │   └── filters.py         # 结构裁剪/段落过滤
│   │   ├── engines/               # BM25/Dense/SPLADE/Hybrid
│   │   │   ├── bm25.py
│   │   │   ├── dense.py
│   │   │   ├── splade.py
│   │   │   └── fusion.py          # RRF等rank fusion
│   │   ├── rerankers/
│   │   │   ├── cross_encoder.py
│   │   │   └── llm_reranker.py
│   │   └── contracts.py           # Retriever接口（便于mock与替换）
│   │
│   ├── evidence/                  # [证据层] 与原文对齐、引用校验、回溯
│   │   ├── align.py               # quote->paragraph对齐/字符范围定位
│   │   ├── cite.py                # 引用格式化（段落id/page/snippet）
│   │   └── verification.py        # “存在性校验”底层工具（非LLM）
│   │
│   ├── rob2/                      # [ROB2知识层] decision tree、规则、映射
│   │   ├── question_bank.py       # ROB2问题清单/ID映射
│   │   ├── decision_rules.py      # 域内决策树规则（硬规则 or 可配置）
│   │   ├── cross_rules.py         # 跨域一致性规则
│   │   └── rubric.py              # 输出标准化（Low/Some concerns/High）
│   │
│   ├── persistence/               # [可选] 审计/缓存/运行记录
│   │   ├── models.py              # ORM：运行记录、证据包、结果快照
│   │   ├── repositories.py
│   │   └── migrations/            # alembic迁移（如你已有）
│   │
│   └── utils/
│       ├── hashing.py
│       ├── text.py                # 分块/清洗/归一化
│       └── timings.py
│
├── tests/
│   ├── unit/
│   │   ├── test_section_prior.py
│   │   ├── test_evidence_existence.py
│   │   ├── test_fusion.py
│   │   └── test_domain_rules.py
│   ├── integration/
│   │   ├── test_graph_smoke.py     # 端到端跑一篇小论文
│   │   ├── test_locators.py        # 三引擎一致性
│   │   └── test_validators.py
│   └── fixtures/
│       ├── pdfs/
│       └── expected_outputs/       # 人工标注/金标准（建议）
│
├── pyproject.toml
├── Dockerfile
├── .dockerignore
├── docker-compose.yml
├── Makefile
└── README.md
```

Notes:
* **pipelines/graphs/** 与 **pipelines/graphs/nodes/** 分离，便于版本演进与节点复用。
* **schemas/internal/** 与 **llm/prompts/** 独立管理，降低状态与提示词耦合。
* 提示词支持语言版本切换：按 `PROMPT_LANG` 选择 `*.{lang}.md`，若不存在则回退到默认 `.md`。
* 证据检索/融合/验证分层，支持单独 mock 与回归测试。
* 运行时与图装配解耦，方便 API 与批处理入口共用。

### Building Blocks & Responsibilities

* **Preprocessing**：解析 PDF，产出可追溯的 DocStructure（body/sections/paragraph_id），并可选提取 `figure`（caption/bbox/page/描述），同时抽取文档元数据（title/authors/year/affiliations/funders）。
* **Domain Question Planner**：输出 Standard ROB2 的问题清单与 decision-tree 绑定。
* **Evidence Location**：规则/检索/LLM ReAct 并集定位候选证据，LLM 线可迭代扩展检索线索。
* **Evidence Fusion**：合并、去重、排序，形成每题 Top-k 证据包。
* **Evidence Validation**：存在性/相关性/一致性/完整性校验，失败仅重试失败问题，重试耗尽触发全文审计降级。
* **Domain Reasoning (D1-D5)**：LLM 产出子问题答案，风险由规则树（`rob2/decision_rules.py`）判定。
* **Full-Text Domain Audit（可选）**：全文审核信号答案，提供引用并补全证据后重跑受影响 domain。
* **ROB2 Aggregator**：汇总五域与 overall risk（ROB2 Standard 规则），输出结构化结果。
* **Batch Exporter**：基于批量 `batch_summary.json` + 各 `result.json` 生成红绿灯图（PNG）与多 sheet 审计工作簿（XLSX）。
* **Runtime/Orchestration**：LangGraph 装配、并行调度与中断恢复。

### Interface Contracts (Data Schemas)

* **DocStructure**: `{ body: str, sections: list[SectionSpan], figures?: list[FigureSpan], document_metadata?: DocumentMetadata, <section_title>: str }`
* **QuestionSet**: `list[{ question_id, domain, text, section_prior? }]`
* **EvidenceCandidate**: `{ question_id, paragraph_id, text, source, score?, supporting_quote? }`
* **EvidenceBundle**: `{ question_id, items: list[EvidenceCandidate] }`
* **ValidatedEvidence**: `{ question_id, items, status, failure_reason? }`
* **DomainDecision**: `{ domain, effect_type?, answers, risk, risk_rationale, missing_questions }`（risk 由规则树判定）
* **Rob2FinalOutput**: `{ overall, domains, citations, document_metadata? }`（见 `src/schemas/internal/results.py`）
  * `citations[*]`: `{ paragraph_id, page, title, text, uses[] }`
  * 额外输出：`rob2_table_markdown`（Markdown 表格，便于人读）
* **Batch Artifacts**: `batch_summary.json/csv` + `batch_traffic_light.png` + `batch_summary.xlsx`

### Subsystem vs Package Boundary

* **子系统**：运行时能力单元（Preprocessing / Evidence Location / Validation 等）。
* **包**：代码组织单元（`pipelines/graphs/`, `pipelines/graphs/nodes/`, `retrieval/`, `rob2/` 等）。
* 一个子系统可以跨多个包实现，但包不得隐式承担多个子系统的职责。

### Layering & Dependencies

* **基础设施层**：`core/`, `llm/`, `persistence/`, `utils/`
* **契约层**：`schemas/`
* **能力层**：`pipelines/graphs/nodes/`, `retrieval/`, `evidence/`, `rob2/`
* **编排层**：`pipelines/graphs/`, `pipelines/runner.py`
* **入口层**：`api/`

依赖规则：入口层 → 编排层 → 能力层 → 契约层 → 基础设施层。禁止反向依赖。

### Component Collaboration Flow

1. PDF 解析产出 DocStructure。
2. Planner 生成 QuestionSet。
3. Evidence Location 产出 EvidenceCandidates（规则/检索/LLM 并集）。
4. Fusion + Validation 形成 ValidatedEvidence；失败仅重试失败问题。
5. D1-D5 推理产出 DomainDecision。
6. 重试耗尽时触发 Full-Text Domain Audit 降级，补全证据并重跑 domain。
7. Aggregator 输出 Rob2FinalOutput。
