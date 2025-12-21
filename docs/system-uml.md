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
```

Notes:
- This diagram reflects the currently implemented nodes and data flow in code.
- Evidence location, validation, reasoning, and aggregation are not implemented yet.
