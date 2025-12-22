"""Cross-encoder reranker for candidate paragraphs (Milestone 4+).

Default model: ncbi/MedCPT-Cross-Encoder
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional, Sequence

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from retrieval.rerankers.contracts import RerankResult

DEFAULT_CROSS_ENCODER_MODEL_ID = "ncbi/MedCPT-Cross-Encoder"


class CrossEncoderReranker:
    """Score (query, passage) pairs with a transformers sequence classification model."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_CROSS_ENCODER_MODEL_ID,
        device: Optional[str] = None,
        hf_token: Optional[str] = None,
    ) -> None:
        resolved_device = device or _default_device()
        self._device = torch.device(resolved_device)
        token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get(
            "HUGGINGFACE_HUB_TOKEN"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model_id, token=token
        )
        self._model.eval()
        self._model.to(self._device)
        self.model_id = model_id
        self.name = "cross_encoder"

    @property
    def device(self) -> str:
        return str(self._device)

    def rerank(
        self,
        query: str,
        passages: Sequence[str],
        *,
        max_length: int = 512,
        batch_size: int = 8,
    ) -> RerankResult:
        if max_length < 1:
            raise ValueError("max_length must be >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if not passages:
            return RerankResult(scores=[], order=[])

        pairs = [[query, passage] for passage in passages]
        scores: List[float] = []

        for start in range(0, len(pairs), batch_size):
            batch = pairs[start : start + batch_size]
            encoded = self._tokenizer(
                batch,
                truncation=True,
                padding=True,
                return_tensors="pt",
                max_length=max_length,
            )
            encoded = {k: v.to(self._device) for k, v in encoded.items()}

            with torch.inference_mode():
                logits = self._model(**encoded).logits
                batch_scores = _logits_to_relevance_scores(logits)
                batch_scores = batch_scores.to(dtype=torch.float32, device="cpu")

            scores.extend(batch_scores.numpy().tolist())

        order = sorted(range(len(scores)), key=lambda idx: (-scores[idx], idx))
        return RerankResult(scores=scores, order=order)


@lru_cache(maxsize=2)
def get_cross_encoder_reranker(
    model_id: str = DEFAULT_CROSS_ENCODER_MODEL_ID,
    device: Optional[str] = None,
    hf_token: Optional[str] = None,
) -> CrossEncoderReranker:
    """Return a cached cross-encoder reranker instance."""
    return CrossEncoderReranker(model_id=model_id, device=device, hf_token=hf_token)


def _logits_to_relevance_scores(logits: torch.Tensor) -> torch.Tensor:
    """Convert model logits to a scalar relevance score in [0, 1]."""
    if logits.ndim == 2 and logits.shape[1] == 1:
        return torch.sigmoid(logits[:, 0])
    if logits.ndim == 2 and logits.shape[1] == 2:
        probs = torch.softmax(logits, dim=1)
        return probs[:, 1]
    flattened = logits.reshape(logits.shape[0], -1)
    if flattened.shape[1] == 0:
        return torch.zeros((logits.shape[0],), device=logits.device)
    return torch.sigmoid(flattened[:, 0])


def _default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


__all__ = [
    "DEFAULT_CROSS_ENCODER_MODEL_ID",
    "CrossEncoderReranker",
    "get_cross_encoder_reranker",
]

