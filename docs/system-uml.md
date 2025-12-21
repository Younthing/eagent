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

    C --> M[bm25_retrieval_locator_node]
    G --> M
    I --> M
    M --> N[bm25_evidence<br/>EvidenceBundle top-k]
    M --> O[bm25_candidates<br/>all fused candidates]
    M --> P[bm25_rankings<br/>per-query top-n]
    M --> Q[bm25_queries]
  end
```

Notes:
- This diagram reflects the currently implemented nodes and data flow in code.
- Evidence location currently includes rule-based and BM25 retrieval locators.
- Dense/SPLADE/fulltext locators, fusion, validation, reasoning, and aggregation are not implemented yet.
