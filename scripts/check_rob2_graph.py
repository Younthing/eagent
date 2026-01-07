"""Run the ROB2 workflow end-to-end via the core runner service."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from schemas.requests import Rob2Input, Rob2RunOptions  # noqa: E402
from services.rob2_runner import run_rob2  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the ROB2 LangGraph workflow.")
    parser.add_argument("pdf_path", type=Path, help="Path to a paper PDF.")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--per-query-top-n", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument(
        "--planner",
        choices=("deterministic", "llm"),
        default="deterministic",
    )
    parser.add_argument(
        "--rerank",
        choices=("none", "cross_encoder"),
        default="none",
    )
    parser.add_argument(
        "--structure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable structure-aware corpus filtering (Milestone 5).",
    )
    parser.add_argument("--splade-model-id", default=None)
    parser.add_argument(
        "--relevance",
        choices=("none", "llm"),
        default="none",
        help="Relevance validator mode (Milestone 7).",
    )
    parser.add_argument(
        "--consistency",
        choices=("none", "llm"),
        default="none",
        help="Consistency validator mode (Milestone 7).",
    )
    parser.add_argument("--min-confidence", type=float, default=0.6)
    parser.add_argument(
        "--enforce-completeness",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--fail-on-consistency", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--relax-on-retry", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--d2-effect-type",
        choices=("assignment", "adherence"),
        default="assignment",
        help="Effect type for D2 reasoning (Milestone 8).",
    )
    parser.add_argument("--domain-evidence-top-k", type=int, default=5)
    parser.add_argument(
        "--domain-audit",
        choices=("none", "llm"),
        default="none",
        help="Run full-text audit + evidence patch (Milestone 9).",
    )
    parser.add_argument(
        "--audit-window",
        type=int,
        default=1,
        help="Include ±N neighboring paragraphs when patching evidence.",
    )
    parser.add_argument(
        "--audit-rerun",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Re-run affected domain agents after applying audit patches.",
    )
    parser.add_argument(
        "--audit-final",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run one optional final audit over all domains after D5.",
    )
    parser.add_argument("--json", action="store_true", help="Print final state JSON.")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    if not args.pdf_path.exists():
        print(f"PDF not found: {args.pdf_path}", file=sys.stderr)
        return 2

    debug_level = "full" if args.json else "min"
    options = Rob2RunOptions(
        top_k=args.top_k,
        per_query_top_n=args.per_query_top_n,
        rrf_k=args.rrf_k,
        query_planner=args.planner,
        reranker=args.rerank,
        use_structure=bool(args.structure),
        splade_model_id=args.splade_model_id,
        relevance_mode=args.relevance,
        consistency_mode=args.consistency,
        relevance_min_confidence=args.min_confidence,
        consistency_min_confidence=args.min_confidence,
        completeness_enforce=bool(args.enforce_completeness),
        validation_max_retries=args.max_retries,
        validation_fail_on_consistency=bool(args.fail_on_consistency),
        validation_relax_on_retry=bool(args.relax_on_retry),
        d2_effect_type=args.d2_effect_type,
        domain_evidence_top_k=args.domain_evidence_top_k,
        domain_audit_mode=args.domain_audit,
        domain_audit_patch_window=args.audit_window,
        domain_audit_rerun_domains=bool(args.audit_rerun),
        domain_audit_final=bool(args.audit_final),
        debug_level=debug_level,
    )
    result = run_rob2(Rob2Input(pdf_path=str(args.pdf_path)), options)
    debug_state = {}
    if result.debug and isinstance(result.debug, dict):
        debug_state = result.debug.get("state") or {}

    if args.json:
        print(json.dumps(debug_state or result.model_dump(), ensure_ascii=False, indent=2))
        return 0

    attempt = debug_state.get("validation_attempt")
    passed = bool(debug_state.get("completeness_passed"))
    failed = debug_state.get("completeness_failed_questions") or []
    consistency_failed = debug_state.get("consistency_failed_questions") or []
    print(
        "Validation result:",
        f"attempt={attempt}",
        f"completeness_passed={passed}",
        f"failed_questions={len(failed)}",
        f"consistency_failed_questions={len(consistency_failed)}",
    )

    retry_log = debug_state.get("validation_retry_log") or []
    if isinstance(retry_log, list) and retry_log:
        print("\nRetry log:")
        for item in retry_log:
            if not isinstance(item, dict):
                continue
            updates = item.get("updates") or {}
            print(
                f"  - attempt={item.get('attempt')} "
                f"failed={len(item.get('completeness_failed_questions') or [])} "
                f"consistency_failed={len(item.get('consistency_failed_questions') or [])} "
                f"updates={updates}"
            )

    print("\nROB2:", f"overall={result.result.overall.risk}")
    if result.table_markdown.strip():
        print("\nROB2 table:\n" + result.table_markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
