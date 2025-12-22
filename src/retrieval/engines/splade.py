"""SPLADE encoder (sparse expansion via masked language model)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

import numpy as np
import torch
from transformers import AutoModelForMaskedLM, AutoTokenizer

DEFAULT_SPLADE_MODEL_ID = "naver/splade-v3"


class SpladeEncoder:
    """Encode text into a SPLADE sparse vector (dense vocab-sized array)."""

    def __init__(
        self,
        *,
        model_id: str = DEFAULT_SPLADE_MODEL_ID,
        device: Optional[str] = None,
        hf_token: Optional[str] = None,
    ) -> None:
        resolved_device = device or _default_device()
        self._device = torch.device(resolved_device)
        token = hf_token or os.environ.get("HF_TOKEN") or os.environ.get(
            "HUGGINGFACE_HUB_TOKEN"
        )
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
        self._model = AutoModelForMaskedLM.from_pretrained(model_id, token=token)
        self._model.eval()
        self._model.to(self._device)
        self.model_id = model_id
        self.vocab_size = int(getattr(self._model.config, "vocab_size", 0) or 0)
        if self.vocab_size <= 0:
            raise ValueError("Unable to infer vocab_size from SPLADE model config.")

    @property
    def device(self) -> str:
        return str(self._device)

    def encode(
        self,
        texts: List[str],
        *,
        max_length: int,
        batch_size: int = 8,
    ) -> np.ndarray:
        """Return a float32 matrix of shape (len(texts), vocab_size)."""
        if max_length < 1:
            raise ValueError("max_length must be >= 1")
        if batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if not texts:
            return np.zeros((0, self.vocab_size), dtype=np.float32)

        vectors: List[np.ndarray] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            tokenized = self._tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            tokenized = {k: v.to(self._device) for k, v in tokenized.items()}

            with torch.inference_mode():
                logits = self._model(**tokenized).logits
                activations = torch.log1p(torch.relu(logits))
                pooled = torch.amax(activations, dim=1)
                pooled = pooled.to(dtype=torch.float32, device="cpu")
            vectors.append(pooled.numpy())

        return np.ascontiguousarray(np.vstack(vectors), dtype=np.float32)


@lru_cache(maxsize=2)
def get_splade_encoder(
    model_id: str = DEFAULT_SPLADE_MODEL_ID,
    device: Optional[str] = None,
    hf_token: Optional[str] = None,
) -> SpladeEncoder:
    """Return a cached SPLADE encoder instance."""
    return SpladeEncoder(model_id=model_id, device=device, hf_token=hf_token)


def _default_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


__all__ = ["DEFAULT_SPLADE_MODEL_ID", "SpladeEncoder", "get_splade_encoder"]
