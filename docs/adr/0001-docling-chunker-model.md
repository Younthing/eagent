# ADR-0001：Docling 分块模型选择

状态：已接受

背景
- Docling 的分块模型可通过 `DOCLING_CHUNKER_MODEL` 配置。
- 切换到 `malteos/PubMedNCL` 后，分块效果明显改善。

决策
- 将 `malteos/PubMedNCL` 作为默认 Docling 分块模型。
- 允许通过 `DOCLING_CHUNKER_MODEL` 覆盖默认值。

影响
- 当前语料的分块质量提升。
- 后续若调整模型，应同步更新该 ADR 与相关配置文档。
