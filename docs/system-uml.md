# System UML (Current Implementation)

```mermaid
flowchart TD
  subgraph Preprocessing
    A[DoclingLoader] --> B[preprocess_node]
    B --> C[DocStructure]
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
  end

  subgraph EvidenceFusion
    L --> FUS[fusion_node<br/>three-engine merge<br/>M6]
    O --> FUS
    U --> FUS
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

    EE --> CV[consistency_validator_node<br/>optional LLM<br/>M7]
    CV --> CR[consistency_reports]

    EE --> CM[completeness_validator_node<br/>select validated evidence<br/>M7]
    CM --> VE[validated_evidence<br/>FusedEvidenceBundle top-k]
    CM --> CP[completeness_report]
  end

  subgraph Reasoning
    CM --> D1[d1_randomization_node<br/>LLM decision<br/>M8]
    D1 --> D2[d2_deviations_node<br/>LLM decision<br/>M8]
    D2 --> D3[d3_missing_data_node<br/>LLM decision<br/>M8]
    D3 --> D4[d4_measurement_node<br/>LLM decision<br/>M8]
    D4 --> D5[d5_reporting_node<br/>LLM decision<br/>M8]
    P1[src/llm/prompts/domains/d1_system.md] --> D1
    P2[src/llm/prompts/domains/d2_system.md] --> D2
    P3[src/llm/prompts/domains/d3_system.md] --> D3
    P4[src/llm/prompts/domains/d4_system.md] --> D4
    P5[src/llm/prompts/domains/d5_system.md] --> D5
  end

  %% Milestone 7 rollback/retry: failed validation routes back to EvidenceLocation
  CM -. validation_failed / retry .-> J
```

Notes:
- This diagram reflects the currently implemented nodes and data flow in code.
- Evidence location currently includes rule-based, BM25, and SPLADE retrieval locators.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support LLM query planning via LangChain `init_chat_model` (`query_planner=llm`), with deterministic fallback on errors.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional cross-encoder reranking (`reranker=cross_encoder`) after RRF.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional structure-aware filtering/ranking (Milestone 5).
- `relevance_validator_node` annotates fused candidates with an LLM relevance verdict (Milestone 7).
- `existence_validator_node` verifies paragraph_id/text/quote grounding against `doc_structure` (Milestone 7).
- `consistency_validator_node` optionally checks multi-evidence contradictions per question (Milestone 7).
- `completeness_validator_node` selects `validated_evidence` from candidates that passed validations (Milestone 7).
- Validation failures can trigger a retry that rolls back to the evidence location layer (Milestone 7).
- Domain reasoning loads system prompts from `src/llm/prompts/domains/{domain}_system.md`, with a fallback to `rob2_domain_system.md`.
- Domain reasoning normalizes answers and applies decision-tree rules (`src/rob2/decision_rules.py`) to set domain risk when defined.
- Dense/fulltext locators, remaining validation layers, and aggregation are not implemented yet.
