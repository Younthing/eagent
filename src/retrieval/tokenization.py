"""Tokenization helpers for retrieval and rule-based matching."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable, Literal, Sequence, cast

logger = logging.getLogger(__name__)

TokenizerMode = Literal[
    "auto",
    "english",
    "pkuseg_medicine",
    "pkuseg",
    "jieba",
    "char",
]

_NON_WORD = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class TokenizerConfig:
    mode: TokenizerMode = "auto"
    char_ngram: int = 2


def resolve_tokenizer_config(
    mode: str | None,
    char_ngram: int | None,
) -> TokenizerConfig:
    resolved_mode = (mode or "auto").strip().lower()
    allowed = {
        "auto",
        "english",
        "pkuseg_medicine",
        "pkuseg",
        "jieba",
        "char",
    }
    if resolved_mode not in allowed:
        logger.warning("Unknown tokenizer mode: %s (fallback to auto)", resolved_mode)
        resolved_mode = "auto"
    resolved_ngram = int(char_ngram or 2)
    if resolved_ngram < 1:
        resolved_ngram = 1
    return TokenizerConfig(
        mode=cast(TokenizerMode, resolved_mode),
        char_ngram=resolved_ngram,
    )


def contains_cjk(text: str) -> bool:
    return any(_is_cjk(char) for char in text)


def normalize_for_match(text: str) -> str:
    if not text:
        return ""
    parts: list[str] = []
    for char in text:
        if _is_cjk(char):
            parts.append(char)
        elif char.isascii():
            parts.append(char.lower() if char.isalnum() else " ")
        else:
            parts.append(char if char.isalnum() else " ")
    return " ".join("".join(parts).split())


def tokenize_text(text: str, *, config: TokenizerConfig | None = None) -> list[str]:
    if not text:
        return []
    cfg = config or TokenizerConfig()
    if cfg.mode == "english":
        return _tokenize_english(text)
    if cfg.mode == "char":
        return _merge_tokens(
            _tokenize_cjk_ngrams(text, cfg.char_ngram),
            _tokenize_english(text),
        )
    if cfg.mode == "jieba":
        return _merge_tokens(
            _tokenize_jieba(text) or _tokenize_cjk_ngrams(text, cfg.char_ngram),
            _tokenize_english(text),
        )
    if cfg.mode == "pkuseg":
        return _merge_tokens(
            _tokenize_pkuseg(text, model_name=None)
            or _tokenize_jieba(text)
            or _tokenize_cjk_ngrams(text, cfg.char_ngram),
            _tokenize_english(text),
        )
    if cfg.mode == "pkuseg_medicine":
        return _merge_tokens(
            _tokenize_pkuseg(text, model_name="medicine")
            or _tokenize_pkuseg(text, model_name=None)
            or _tokenize_jieba(text)
            or _tokenize_cjk_ngrams(text, cfg.char_ngram),
            _tokenize_english(text),
        )
    # auto
    if contains_cjk(text):
        return _merge_tokens(
            _tokenize_pkuseg(text, model_name="medicine")
            or _tokenize_pkuseg(text, model_name=None)
            or _tokenize_jieba(text)
            or _tokenize_cjk_ngrams(text, cfg.char_ngram),
            _tokenize_english(text),
        )
    return _tokenize_english(text)


def _tokenize_english(text: str) -> list[str]:
    lowered = text.casefold()
    lowered = lowered.replace("-", " ").replace("–", " ").replace("—", " ")
    lowered = _NON_WORD.sub(" ", lowered)
    return [token for token in lowered.split() if token]


def _tokenize_cjk_ngrams(text: str, ngram: int) -> list[str]:
    chars = [char for char in text if _is_cjk(char)]
    if not chars:
        return []
    if ngram <= 1:
        return chars
    return ["".join(chars[i : i + ngram]) for i in range(len(chars) - ngram + 1)]


def _tokenize_pkuseg(text: str, *, model_name: str | None) -> list[str] | None:
    try:
        segmenter = _get_pkuseg_segmenter(model_name)
        tokens = segmenter.cut(text)
    except Exception:
        logger.debug("pkuseg tokenization failed", exc_info=True)
        return None
    return _clean_tokens(tokens)


def _tokenize_jieba(text: str) -> list[str] | None:
    try:
        import jieba  # type: ignore
    except Exception:
        return None
    try:
        tokens = list(jieba.cut(text))
    except Exception:
        logger.debug("jieba tokenization failed", exc_info=True)
        return None
    return _clean_tokens(tokens)


@lru_cache(maxsize=2)
def _get_pkuseg_segmenter(model_name: str | None):
    import pkuseg

    if model_name:
        return pkuseg.pkuseg(model_name=model_name)
    return pkuseg.pkuseg()


def _clean_tokens(tokens: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for token in tokens:
        normalized = _clean_token(token)
        if normalized:
            cleaned.append(normalized)
    return cleaned


def _clean_token(token: str) -> str:
    if not token:
        return ""
    chars = [char for char in token.strip() if char.isalnum() or _is_cjk(char)]
    if not chars:
        return ""
    cleaned = "".join(chars)
    return cleaned.casefold() if cleaned.isascii() else cleaned


def _merge_tokens(primary: Sequence[str], secondary: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for token in list(primary) + list(secondary):
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _is_cjk(char: str) -> bool:
    code = ord(char)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
        or 0x2F800 <= code <= 0x2FA1F
    )


__all__ = [
    "TokenizerConfig",
    "TokenizerMode",
    "contains_cjk",
    "normalize_for_match",
    "resolve_tokenizer_config",
    "tokenize_text",
]
