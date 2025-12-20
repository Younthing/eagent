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
    D[Structured Doc JSON<br/>body, sections, spans]
  end

  subgraph Planning
    E[Domain Question Planner<br/>Standard ROB2]
    F[Question Schema + Decision Trees]
  end

  subgraph EvidenceLocation[Evidence Location Layer]
    G1[FullText Locator LLM]
    G2[Rule-Based Locator]
    G3[Retrieval Engine<br/>BM25/Dense/SPLADE]
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

  subgraph CrossDomain
    K[Cross-Domain Validator]
  end

  subgraph Aggregation
    L[ROB2 Aggregator]
  end

  subgraph Outputs
    M[Report Table + JSON<br/>Evidence citations]
  end

  A --> C
  C --> D
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

Render with any Mermaid-compatible viewer (e.g., `npx @mermaid-js/mermaid-cli -i docs/system-architecture.md -o architecture.svg`).

### Interface Contracts (Data Schemas)

* **DocStructure**: `{ body: str, sections: list[SectionSpan], <section_title>: str }`
* **QuestionSet**: `list[{ question_id, domain, text, section_prior? }]`
* **EvidenceCandidate**: `{ question_id, paragraph_id, text, source, score? }`
* **EvidenceBundle**: `{ question_id, items: list[EvidenceCandidate] }`
* **ValidatedEvidence**: `{ question_id, items, status, failure_reason? }`
* **DomainDecision**: `{ domain, answers, risk, evidence_refs }`
* **FinalReport**: `{ domain_results, overall_risk, citations, json }`
