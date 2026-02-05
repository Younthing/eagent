from persistence.hashing import (
    bm25_cache_key,
    hash_payload,
    preprocess_cache_key,
    sha256_bytes,
    splade_cache_key,
)


def test_hash_payload_stable_order() -> None:
    payload_a = {"b": 1, "a": 2}
    payload_b = {"a": 2, "b": 1}
    assert hash_payload(payload_a) == hash_payload(payload_b)


def test_cache_keys_are_deterministic() -> None:
    doc_hash = sha256_bytes(b"example")
    preprocess_key = preprocess_cache_key(
        doc_hash,
        {"layout": "x"},
        {"mode": "auto"},
        {"drop_references": True},
    )
    assert preprocess_key == preprocess_cache_key(
        doc_hash,
        {"layout": "x"},
        {"mode": "auto"},
        {"drop_references": True},
    )

    bm25_key = bm25_cache_key(doc_hash, {"mode": "auto", "char_ngram": 2})
    assert bm25_key == bm25_cache_key(doc_hash, {"char_ngram": 2, "mode": "auto"})

    splade_key = splade_cache_key(doc_hash, "model", 128)
    assert splade_key == splade_cache_key(doc_hash, "model", 128)
