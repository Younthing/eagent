# System UML (Current Implementation)

```mermaid
flowchart TD
  subgraph Preprocessing
    A[DoclingLoader] --> B[preprocess_node<br/>Docling parse]
    B --> DS[doc_scope_selector<br/>auto/manual]
    DS --> FR[filter_reference_sections]
    FR --> DM[document_metadata_extraction<br/>LangExtract]
    DM --> C[DocStructure]
  end

  subgraph Planning
    D[src/rob2/rob2_questions.yaml] --> E[question_bank]
    E --> F[planner_node]
    F --> G[QuestionSet]
  end

  subgraph EvidenceLocation
    H[src/rob2/locator_rules.yaml] --> I[locator_rules]
    C --> J[rule_based_locator_node]
    G --> J
    I --> J
    J --> K[rule_based_evidence<br/>EvidenceBundle top-k]
    J --> L[rule_based_candidates<br/>all scored candidates]

    G --> QP[query_planner<br/>deterministic / LLM<br/>M4]
    I --> QP

    C --> M[bm25_retrieval_locator_node]
    QP --> M
    C --> R[section_prior_filter<br/>optional<br/>M5]
    I --> R
    R --> M
    M --> CE1[cross_encoder_reranker<br/>optional<br/>post-RRF]
    CE1 --> N[bm25_evidence<br/>EvidenceBundle top-k]
    CE1 --> O[bm25_candidates<br/>all fused candidates]
    M --> P[bm25_rankings<br/>per-query top-n]
    M --> Q[bm25_queries]

    C --> S[splade_retrieval_locator_node]
    QP --> S
    R --> S
    S --> CE2[cross_encoder_reranker<br/>optional<br/>post-RRF]
    CE2 --> T[splade_evidence<br/>EvidenceBundle top-k]
    CE2 --> U[splade_candidates<br/>all fused candidates]
    S --> V[splade_rankings<br/>per-query top-n]
    S --> W[splade_queries]

    S --> LL[llm_locator_node<br/>ReAct LLM]
    LL --> FT[fulltext_candidates<br/>LLM evidence]
  end

  subgraph EvidenceFusion
    L --> FUS[fusion_node<br/>three-engine merge<br/>M6]
    O --> FUS
    U --> FUS
    FT --> FUS
    FUS --> FE[fusion_evidence<br/>FusedEvidenceBundle top-k]
    FUS --> FC[fusion_candidates<br/>all fused candidates]
  end

  subgraph Validation
    FC --> RV[relevance_validator_node<br/>optional LLM<br/>M7]
    RV --> RE[relevance_evidence<br/>FusedEvidenceBundle top-k<br/>annotated]
    RV --> RC[relevance_candidates<br/>annotated candidates]

    RC --> EV[existence_validator_node<br/>deterministic<br/>M7]
    EV --> EC[existence_candidates<br/>annotated candidates]
    EV --> EE[existence_evidence<br/>FusedEvidenceBundle top-k<br/>filtered]

    EC --> CV[consistency_validator_node<br/>optional LLM<br/>M7]
    CV --> CR[consistency_reports]

    EC --> CM[completeness_validator_node<br/>select validated evidence<br/>M7]
    CM --> VE[validated_evidence<br/>FusedEvidenceBundle top-k]
    CM --> CP[completeness_report]
  end

  subgraph Reasoning
    CM --> D1[d1_randomization_node<br/>LLM decision<br/>M8]
    D1 --> D2[d2_deviations_node<br/>LLM decision<br/>M8]
    D1 -. audit_mode=llm .-> A1[d1_audit_node<br/>full-text audit + patch + rerun D1<br/>M9]
    A1 --> D2
    D2 --> D3[d3_missing_data_node<br/>LLM decision<br/>M8]
    D2 -. audit_mode=llm .-> A2[d2_audit_node<br/>full-text audit + patch + rerun D2<br/>M9]
    A2 --> D3
    D3 --> D4[d4_measurement_node<br/>LLM decision<br/>M8]
    D3 -. audit_mode=llm .-> A3[d3_audit_node<br/>full-text audit + patch + rerun D3<br/>M9]
    A3 --> D4
    D4 --> D5[d5_reporting_node<br/>LLM decision<br/>M8]
    D4 -. audit_mode=llm .-> A4[d4_audit_node<br/>full-text audit + patch + rerun D4<br/>M9]
    A4 --> D5
    D5 --> AGG[aggregate_node<br/>final output + citations<br/>M10]
    D5 -. audit_mode=llm .-> A5[d5_audit_node<br/>full-text audit + patch + rerun D5<br/>M9]
    A5 -. optional .-> AFinal[final_domain_audit_node<br/>all-domain audit report<br/>M9]
    A5 --> AGG
    AFinal --> AGG
    P1[src/llm/prompts/domains/d1_system.{lang}.md] --> D1
    P2[src/llm/prompts/domains/d2_system.{lang}.md] --> D2
    P3[src/llm/prompts/domains/d3_system.{lang}.md] --> D3
    P4[src/llm/prompts/domains/d4_system.{lang}.md] --> D4
    P5[src/llm/prompts/domains/d5_system.{lang}.md] --> D5
    P6[src/llm/prompts/validators/domain_audit_system.{lang}.md] --> A1
    P6 --> A2
    P6 --> A3
    P6 --> A4
    P6 --> A5
    P6 --> AFinal
    P7[src/llm/prompts/locators/llm_locator_system.md] --> LL
  end

  %% Milestone 7 rollback/retry: failed validation routes back to EvidenceLocation
  CM -. validation_failed / retry .-> J
  CM -. validation_failed / fallback .-> FB[enable_fulltext_fallback_node]
  FB --> D1
```

Notes:
- This diagram reflects the currently implemented nodes and data flow in code.
- Evidence location includes rule-based, BM25, SPLADE, and LLM ReAct locators.
- `llm_locator_node` runs an LLM ReAct loop over seeded candidates (rule-based/BM25/SPLADE), emits `paragraph_id + quote`, and merges into fusion via `fulltext_candidates`.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support LLM query planning via LangChain `init_chat_model` (`query_planner=llm`), with deterministic fallback on errors.
- Preprocessing applies `doc_scope_selector` to trim mixed-document PDFs (auto/manual) and produces `doc_scope_report` in debug/report outputs.
- Preprocessing supports optional figure extraction (`doc_structure.figures`) with Docling image enrichment (`do_picture_description`) and optional external multimodal LLM description.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional cross-encoder reranking (`reranker=cross_encoder`) after RRF.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional structure-aware filtering/ranking (Milestone 5).
- `relevance_validator_node` annotates fused candidates with an LLM relevance verdict (Milestone 7).
- `existence_validator_node` verifies paragraph_id/text/quote grounding against `doc_structure` (Milestone 7).
- `consistency_validator_node` optionally checks multi-evidence contradictions per question (Milestone 7).
- `completeness_validator_node` selects `validated_evidence` from candidates that passed validations (Milestone 7).
- Validation failures trigger retry scoped to failed questions; if retries exhaust, a full-text audit fallback is enabled (Milestone 7/9).
- Domain reasoning loads system prompts from `src/llm/prompts/domains/{domain}_system.{lang}.md` using `PROMPT_LANG` (default `zh`), with fallback to `{domain}_system.md`, then `rob2_domain_system.{lang}.md`, then `rob2_domain_system.md`.
- Domain audit loads system prompts from `src/llm/prompts/validators/domain_audit_system.{lang}.md` (falls back to `domain_audit_system.md` if missing).
- Domain reasoning normalizes answers and applies decision-tree rules (`src/rob2/decision_rules.py`) to set domain risk when defined.
- Per-domain `*_audit_node` steps (Milestone 9) read the full document, propose citations, patch `validated_candidates`, and re-run the corresponding domain only when `domain_audit_mode=llm` and `domain_audit_rerun_domains=true` (default: true).
- `final_domain_audit_node` is optional and emits an all-domain audit report (no rerun) when `domain_audit_mode=llm` and `domain_audit_final=true`.
- `aggregate_node` produces `rob2_result` (JSON) + `rob2_table_markdown` (human-readable).
- CLI now includes `rob2 batch run`, which iterates folder PDFs, auto-resumes via `batch_checkpoint.json`, and invokes `run_rob2` per file while preserving per-run persistence records.
- `rob2 batch run` now auto-generates `batch_traffic_light.png` (classic Overall+D1..D5 traffic-light matrix) by default; `--no-plot` disables it and `--plot-output` overrides the target path.
- CLI now includes `rob2 batch plot`, which renders the same PNG from an existing batch output directory or a `batch_summary.json` file.
- Dense retrieval and cross-domain validation are not implemented yet.
