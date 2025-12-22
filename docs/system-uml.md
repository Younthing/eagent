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
```

Notes:
- This diagram reflects the currently implemented nodes and data flow in code.
- Evidence location currently includes rule-based, BM25, and SPLADE retrieval locators.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support LLM query planning via LangChain `init_chat_model` (`query_planner=llm`), with deterministic fallback on errors.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional cross-encoder reranking (`reranker=cross_encoder`) after RRF.
- `bm25_retrieval_locator_node` / `splade_retrieval_locator_node` support optional structure-aware filtering/ranking (Milestone 5).
- Dense/fulltext locators, validation, reasoning, and aggregation are not implemented yet.
