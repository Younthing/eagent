# Introduction

<cite>
**Referenced Files in This Document**   
- [docs/requirements.md](file://docs/requirements.md)
- [docs/architecture.md](file://docs/architecture.md)
- [docs/Milestones.md](file://docs/Milestones.md)
- [src/cli/app.py](file://src/cli/app.py)
- [src/services/rob2_runner.py](file://src/services/rob2_runner.py)
- [src/pipelines/graphs/rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py)
- [src/rob2/question_bank.py](file://src/rob2/question_bank.py)
- [src/retrieval/query_planning/planner.py](file://src/retrieval/query_planning/planner.py)
- [src/evidence/fusion.py](file://src/evidence/fusion.py)
- [src/rob2/decision_rules.py](file://src/rob2/decision_rules.py)
- [docs/rob2_reference/rob2_questions.md](file://docs/rob2_reference/rob2_questions.md)
</cite>

The eagent repository implements a sophisticated CLI tool designed to automate the Risk of Bias 2 (ROB2) assessment process for clinical trial publications. This system leverages LangGraph-based agent workflows to transform the traditionally manual, time-consuming, and expertise-intensive task of systematic review into a streamlined, reproducible, and evidence-driven process. Its core value proposition lies in its ability to significantly accelerate research integrity evaluation and meta-analysis by providing a robust, transparent, and auditable framework for bias assessment.

The primary use cases of eagent are centered on enhancing the efficiency and reliability of systematic reviews. Researchers can use this tool to rapidly evaluate the methodological quality of a large corpus of clinical trials, ensuring that meta-analyses are built upon a foundation of rigorously assessed evidence. By automating the ROB2 protocol, eagent reduces the burden on human reviewers, minimizes inter-rater variability, and allows researchers to focus their expertise on higher-level synthesis and interpretation rather than the laborious task of data extraction and initial bias screening.

The technical architecture of eagent is a multi-layered, agent-based system built on the LangGraph framework. The process begins with the integration of Docling, a state-of-the-art document intelligence tool, which parses input PDFs into a structured JSON format. This parsing preserves critical metadata such as paragraph IDs, section hierarchies, and page numbers, creating a stable and verifiable "textual ground" that ensures all subsequent evidence references are traceable to their original source. Following preprocessing, a Domain Question Planner decomposes the ROB2 assessment into a standardized set of sub-questions for each of the five bias domains (randomization, deviations, missing data, measurement, and reporting).

To locate relevant evidence for each sub-question, eagent employs a sophisticated multi-strategy retrieval system. This includes a rule-based locator that uses section titles and keywords as anchors, and an advanced retrieval engine that utilizes a combination of BM25, dense embeddings, and SPLADE models. These engines operate in parallel, generating multiple candidate evidence passages. The system then applies an evidence fusion pipeline, which uses Reciprocal Rank Fusion (RRF) to combine results from the different retrieval strategies, prioritizing passages that are consistently identified across multiple engines. This fusion step is critical for maximizing recall while minimizing noise.

The heart of the system's robustness is its multi-stage evidence validation pipeline. Before any reasoning occurs, candidate evidence is rigorously validated for existence (confirming the text is present in the source), relevance (ensuring it answers the specific question), consistency (checking for contradictions), and completeness (verifying all required information is present). This layered validation acts as a safeguard against hallucination and logical errors, ensuring that only high-confidence, verifiable evidence is used for final assessment. The domain-specific reasoning is performed by a series of specialized agents (D1-D5), which use large language models to analyze the validated evidence and answer the ROB2 sub-questions. Crucially, the final risk judgment for each domain is not made by the LLM but is determined by a hard-coded decision rule tree (implemented in `decision_rules.py`), which strictly adheres to the official ROB2 guidelines, guaranteeing scientific correctness.

Key features of eagent include its configurable validation modes, which allow users to adjust the strictness of the evidence checks, and its advanced audit capabilities. The audit system can perform a full-text review after the initial domain assessments to identify and patch any missing evidence, then re-run the affected domains, thereby improving the assessment's comprehensiveness. The tool is primarily accessed via a CLI interface, which provides a powerful and scriptable way to process individual papers or batches of documents. Underlying this CLI is the `rob2_runner` service, which serves as a unified execution engine and could be extended to support API-based usage in future developments.

The project's maturity level is well-documented through a comprehensive milestone tracking system. As of the current state, the repository has successfully achieved milestones up to and including the implementation of the full ROB2 reasoning agents (Milestone 8) and the domain audit system (Milestone 9). The system is built upon a foundation of frozen scientific logic and requirements, ensuring stability. While a final scientific validation milestone (M11) is marked as optional, the existing architecture, with its emphasis on evidence-centricity, cross-validation, and rule-based final judgments, is designed to achieve research-grade reliability, making it a powerful tool for accelerating high-quality systematic reviews.

**Section sources**
- [docs/requirements.md](file://docs/requirements.md#L1-L309)
- [docs/architecture.md](file://docs/architecture.md#L1-L288)
- [docs/Milestones.md](file://docs/Milestones.md#L1-L328)
- [src/cli/app.py](file://src/cli/app.py#L1-L146)
- [src/services/rob2_runner.py](file://src/services/rob2_runner.py#L1-L443)
- [src/pipelines/graphs/rob2_graph.py](file://src/pipelines/graphs/rob2_graph.py#L1-L426)
- [src/rob2/question_bank.py](file://src/rob2/question_bank.py#L1-L44)
- [src/retrieval/query_planning/planner.py](file://src/retrieval/query_planning/planner.py#L1-L93)
- [src/evidence/fusion.py](file://src/evidence/fusion.py#L1-L112)
- [src/rob2/decision_rules.py](file://src/rob2/decision_rules.py#L1-L195)
- [docs/rob2_reference/rob2_questions.md](file://docs/rob2_reference/rob2_questions.md#L1-L141)