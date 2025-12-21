"""Load locator configuration rules from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from schemas.internal.locator import LocatorRules

DEFAULT_LOCATOR_RULES = Path(__file__).resolve().parent / "locator_rules.yaml"


def load_locator_rules(path: Path | str | None = None) -> LocatorRules:
    """Load and validate locator rules from YAML."""
    resolved = Path(path) if path else DEFAULT_LOCATOR_RULES
    if not resolved.exists():
        raise FileNotFoundError(f"Locator rules not found: {resolved}")

    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Locator rules must be a YAML mapping")

    return LocatorRules.model_validate(raw)


@lru_cache(maxsize=2)
def get_locator_rules(path: str | None = None) -> LocatorRules:
    """Return cached locator rules for reuse in locator nodes."""
    resolved: Path | None = Path(path) if path else None
    return load_locator_rules(resolved)


__all__ = ["DEFAULT_LOCATOR_RULES", "get_locator_rules", "load_locator_rules"]

