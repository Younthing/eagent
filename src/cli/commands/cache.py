"""Cache management commands."""

from __future__ import annotations

import typer

from core.config import get_settings
from pipelines.graphs.nodes.domain_audit import _load_audit_system_prompt
from pipelines.graphs.nodes.domains.common import _load_system_prompt_template
from retrieval.engines.splade import get_splade_encoder
from retrieval.rerankers.cross_encoder import get_cross_encoder_reranker
from rob2.locator_rules import get_locator_rules
from rob2.question_bank import get_question_bank
from .shared import emit_json


app = typer.Typer(
    help="缓存查看与清理",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


_CACHED_FUNCS = {
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
    for name, func in _CACHED_FUNCS.items():
        info = getattr(func, "cache_info", None)
        payload[name] = info()._asdict() if callable(info) else {"cached": False}
    emit_json(payload)


@app.command("clear", help="清理缓存")
def cache_clear() -> None:
    cleared: list[str] = []
    for name, func in _CACHED_FUNCS.items():
        clear = getattr(func, "cache_clear", None)
        if callable(clear):
            clear()
            cleared.append(name)
    emit_json({"cleared": cleared})


__all__ = ["app"]
