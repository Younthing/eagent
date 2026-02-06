"""Cache management commands."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

import typer

from .shared import emit_json

if TYPE_CHECKING:
    from persistence.cache import CacheManager


app = typer.Typer(
    help="缓存查看与清理",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


def _cached_funcs() -> dict[str, Callable[..., Any]]:
    from core.config import get_settings
    from pipelines.graphs.nodes.domain_audit import _load_audit_system_prompt
    from pipelines.graphs.nodes.domains.common import _load_system_prompt_template
    from retrieval.engines.splade import get_splade_encoder
    from retrieval.rerankers.cross_encoder import get_cross_encoder_reranker
    from rob2.locator_rules import get_locator_rules
    from rob2.question_bank import get_question_bank

    return {
        "settings": get_settings,
        "locator_rules": get_locator_rules,
        "question_bank": get_question_bank,
        "splade_encoder": get_splade_encoder,
        "cross_encoder": get_cross_encoder_reranker,
        "domain_prompt": _load_system_prompt_template,
        "audit_prompt": _load_audit_system_prompt,
    }


@app.command("stats", help="查看缓存状态")
def cache_stats() -> None:
    payload: dict[str, dict] = {}
    for name, func in _cached_funcs().items():
        info = getattr(func, "cache_info", None)
        payload[name] = info()._asdict() if callable(info) else {"cached": False}
    persistent = _persistent_cache_stats()
    if persistent is not None:
        payload["persistent_cache"] = {"stages": persistent}
    emit_json(payload)


@app.command("clear", help="清理缓存")
def cache_clear() -> None:
    cleared: list[str] = []
    for name, func in _cached_funcs().items():
        clear = getattr(func, "cache_clear", None)
        if callable(clear):
            clear()
            cleared.append(name)
    emit_json({"cleared": cleared})


@app.command("prune", help="清理持久化缓存")
def cache_prune(
    days: int = typer.Option(
        30,
        "--days",
        min=1,
        help="删除超过指定天数的缓存条目",
    ),
) -> None:
    manager = _build_cache_manager()
    if manager is None:
        emit_json({"removed": 0, "reason": "cache_disabled"})
        return
    removed = manager.prune_older_than(days=days)
    emit_json({"removed": removed})


def _build_cache_manager() -> "CacheManager | None":
    from core.config import get_settings
    from persistence.cache import CacheManager
    from persistence.sqlite_store import SqliteStore

    settings = get_settings()
    scope = str(getattr(settings, "cache_scope", "none") or "none").strip().lower()
    if scope == "none":
        return None
    base_dir = getattr(settings, "cache_dir", None) or getattr(
        settings, "persistence_dir", "data/rob2"
    )
    store = SqliteStore(Path(base_dir) / "metadata.sqlite")
    return CacheManager(base_dir, store, scope=scope)


def _persistent_cache_stats() -> list[dict] | None:
    manager = _build_cache_manager()
    if manager is None:
        return None
    return manager.stats()


__all__ = ["app"]
