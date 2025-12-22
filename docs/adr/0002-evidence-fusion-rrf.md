# ADR-0002：Evidence Fusion 采用基于 rank 的 RRF 融合

状态：已接受

背景
- M6 Evidence Fusion 需要把 Rule-based / BM25 / SPLADE 等定位结果合并为“每题 Top-k 高置信证据”，并显式保留来源与可调试信息。
- 不同引擎的原始分数（rule 分数、BM25、SPLADE、rerank 分数）量纲不一致，直接相加/比较容易引入不可控偏差。
- 系统希望在不引入额外训练/标注的前提下，优先获得“多引擎一致命中”的稳定性提升。

决策
- Fusion 采用 **rank-based RRF**（Reciprocal Rank Fusion）：对每个引擎按候选列表顺序给 rank=1..N，融合分数为 `Σ weight(engine) * 1/(k + rank)`。
- 以 `paragraph_id` 作为去重键；同一段落命中多个引擎时，聚合为一个 fused candidate，并记录 `supports[]`（engine/rank/score/query）。
- Fusion 只依赖各引擎已经产出的候选排序（包括可选的 post-RRF cross-encoder rerank 的结果），不直接比较不同引擎的 raw score。
- 输出同时保留：
  - `fusion_candidates`: 每题全量 fused candidates（便于 debug）
  - `fusion_evidence`: 每题 Top-k `FusedEvidenceBundle`（进入后续 Validation/Reasoning）

影响
- **优点**：多引擎一致命中会自然获得更高 fusion_score；对分数量纲不敏感；实现简单、可解释、可调权重。
- **限制**：融合质量依赖上游候选排序稳定性；无法利用跨引擎的语义互补做更细粒度的相关性估计（后续可在 Fusion 之后接统一 rerank）。
- **实现位置**：核心算法在 `src/evidence/fusion.py`；图节点封装在 `src/pipelines/graphs/nodes/fusion.py`；契约在 `src/schemas/internal/evidence.py`。
