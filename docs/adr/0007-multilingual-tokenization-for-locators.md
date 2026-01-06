# ADR-0007：定位器启用可配置的中英文分词与兜底策略

状态：已接受

背景
- 现有 BM25/规则定位仅按英文分词归一化，中文文本几乎无法命中。
- SPLADE 与 reranker 可直接替换模型，但定位阶段的 BM25/规则定位需要语言感知的分词策略。
- 需要支持中英文混合文本，且在缺少医学词典时仍可用。

决策
- 引入独立分词模块，提供可配置的多策略分词与兜底：
  - `pkuseg(medicine) → pkuseg(default) → jieba → CJK char n-gram`
  - 自动检测中文文本（CJK）时启用上述策略；英文保持原有分词。
- BM25 与规则定位统一使用同一套归一化/分词逻辑。
- 通过运行配置暴露分词策略与 n-gram 参数，便于后续扩展或替换。

实现
- `src/retrieval/tokenization.py`：新增 `tokenize_text()`、`normalize_for_match()` 与策略选择。
- `src/retrieval/engines/bm25.py`：BM25 索引/检索改为使用可配置分词。
- `src/pipelines/graphs/nodes/locators/retrieval_bm25.py`：读取分词配置并回显到 `bm25_config`。
- `src/pipelines/graphs/nodes/locators/rule_based.py`：使用统一归一化，避免中文被过滤。
- 配置透传：
  - `src/core/config.py`：`LOCATOR_TOKENIZER`、`LOCATOR_CHAR_NGRAM`
  - `src/schemas/requests.py`：`locator_tokenizer`、`locator_char_ngram`
  - `src/services/rob2_runner.py`、`src/pipelines/graphs/rob2_graph.py`、`src/cli/commands/config.py`

影响
- 中文检索在 BM25/规则定位中可用且可配置，英文行为保持兼容。
- 不依赖医学词典也能召回；有条件时可启用 `pkuseg(medicine)` 提升效果。
- 为后续接入更多分词器/语言策略提供清晰扩展点。
