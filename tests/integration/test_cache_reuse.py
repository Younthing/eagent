from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from persistence.cache import CacheManager
from persistence.sqlite_store import SqliteStore
from pipelines.graphs.nodes.preprocess import preprocess_node
from pipelines.graphs.nodes.locators import retrieval_splade
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.rob2 import QuestionSet, Rob2Question


def test_preprocess_cache_reuse(tmp_path: Path, monkeypatch) -> None:
    call_count = {"n": 0}

    def fake_parse(source: str, *, overrides: dict | None = None) -> DocStructure:
        call_count["n"] += 1
        return DocStructure(
            body="Body",
            sections=[SectionSpan(paragraph_id="p1", title="Methods", text="Text")],
        )

    monkeypatch.setattr(
        "pipelines.graphs.nodes.preprocess.parse_docling_pdf", fake_parse
    )

    store = SqliteStore(tmp_path / "metadata.sqlite")
    cache = CacheManager(tmp_path, store, scope="deterministic")

    state = {
        "pdf_path": "dummy.pdf",
        "doc_hash": "hash",
        "cache_manager": cache,
        "doc_scope_mode": "auto",
        "doc_scope_min_pages": 1,
        "doc_scope_min_confidence": 0.5,
        "doc_scope_abstract_gap_pages": 1,
        "preprocess_drop_references": True,
    }

    out1 = preprocess_node(state)
    out2 = preprocess_node(state)
    assert call_count["n"] == 1
    assert out1["doc_structure"] == out2["doc_structure"]


def test_splade_cache_reuse(tmp_path: Path, monkeypatch) -> None:
    store = SqliteStore(tmp_path / "metadata.sqlite")
    cache = CacheManager(tmp_path, store, scope="deterministic")

    spans = [
        SectionSpan(paragraph_id="p1", title="Methods", text="Alpha"),
        SectionSpan(paragraph_id="p2", title="Methods", text="Beta"),
        SectionSpan(paragraph_id="p3", title="Methods", text="Gamma"),
    ]
    doc_structure = DocStructure(body="Alpha\nBeta\nGamma", sections=spans)
    question = Rob2Question(
        question_id="q1",
        rob2_id="1.1",
        domain="D1",
        text="randomization",
        options=["Y", "N"],
        order=1,
    )
    question_set = QuestionSet(version="1.0", variant="standard", questions=[question])

    doc_call_count = {"n": 0}

    class DummyEncoder:
        device = "cpu"

        def encode(self, texts, *, max_length: int, batch_size: int = 8):
            if len(texts) == len(spans):
                doc_call_count["n"] += 1
            return np.ones((len(texts), 4), dtype=np.float32)

    monkeypatch.setattr(
        retrieval_splade, "get_splade_encoder", lambda **kwargs: DummyEncoder()
    )

    def fake_build_ip_index(vectors: np.ndarray):
        return {"vectors": vectors, "ntotal": vectors.shape[0], "d": vectors.shape[1]}

    def fake_search_ip(index, queries: np.ndarray, *, top_n: int):
        k = min(top_n, index["ntotal"])
        scores = np.zeros((queries.shape[0], k), dtype=np.float32)
        indices = np.tile(np.arange(k, dtype=np.int64), (queries.shape[0], 1))
        return scores, indices

    monkeypatch.setattr(retrieval_splade, "build_ip_index", fake_build_ip_index)
    monkeypatch.setattr(retrieval_splade, "search_ip", fake_search_ip)

    state = {
        "doc_structure": doc_structure.model_dump(),
        "question_set": question_set.model_dump(),
        "query_planner": "deterministic",
        "reranker": "none",
        "top_k": 1,
        "per_query_top_n": 1,
        "rrf_k": 60,
        "use_structure": False,
        "section_bonus_weight": 0.0,
        "splade_model_id": "dummy",
        "splade_doc_max_length": 16,
        "splade_query_max_length": 8,
        "splade_batch_size": 2,
        "doc_hash": "hash",
        "cache_manager": cache,
    }

    retrieval_splade.splade_retrieval_locator_node(state)
    retrieval_splade.splade_retrieval_locator_node(state)

    assert doc_call_count["n"] == 1
