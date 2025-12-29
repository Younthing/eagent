"""Check the full validation layer on fused evidence candidates (Milestone 7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipelines.graphs.nodes.fusion import fusion_node  # noqa: E402
from pipelines.graphs.nodes.locators.retrieval_bm25 import (  # noqa: E402
    bm25_retrieval_locator_node,
)
from pipelines.graphs.nodes.locators.retrieval_splade import (  # noqa: E402
    splade_retrieval_locator_node,
)
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node  # noqa: E402
from pipelines.graphs.nodes.preprocess import parse_docling_pdf  # noqa: E402
from pipelines.graphs.nodes.validators.consistency import (  # noqa: E402
    consistency_validator_node,
)
from pipelines.graphs.nodes.validators.existence import existence_validator_node  # noqa: E402
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node  # noqa: E402
from pipelines.graphs.nodes.validators.completeness import (  # noqa: E402
    completeness_validator_node,
)
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402

DEFAULT_LOCAL_SPLADE = PROJECT_ROOT / "models" / "splade_distil_CoCodenser_large"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run locators + fusion + validation (relevance/existence/consistency/completeness).",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a paper PDF.")
    parser.add_argument(
        "--question-id",
        default=None,
        help="Only print results for a single question_id (e.g. q1_1).",
    )
    parser.add_argument("--top-k", type=int, default=5, help="Top-k to print.")
    parser.add_argument(
        "--per-query-top-n",
        type=int,
        default=50,
        help="Top-N hits kept per query before fusion (BM25/SPLADE).",
    )
    parser.add_argument("--rrf-k", type=int, default=60, help="RRF k constant.")
    parser.add_argument(
        "--planner",
        choices=("deterministic", "llm"),
        default="deterministic",
        help="Query planner mode (Milestone 4).",
    )
    parser.add_argument(
        "--rerank",
        choices=("none", "cross_encoder"),
        default="none",
        help="Optional post-RRF reranker for BM25/SPLADE candidates.",
    )
    parser.add_argument(
        "--structure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable structure-aware corpus filtering (Milestone 5).",
    )
    parser.add_argument(
        "--splade-model-id",
        default=str(DEFAULT_LOCAL_SPLADE)
        if DEFAULT_LOCAL_SPLADE.exists()
        else DEFAULT_SPLADE_MODEL_ID,
        help="HuggingFace model id or local path for SPLADE.",
    )

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
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence for relevance/consistency decisions.",
    )
    parser.add_argument(
        "--require-quote",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require supporting_quote to be an exact substring of paragraph text.",
    )
    parser.add_argument(
        "--existence-require-text-match",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require candidate text to match the source paragraph text.",
    )
    parser.add_argument(
        "--existence-require-quote-in-source",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require supporting_quote (when present) to exist in source paragraph.",
    )
    parser.add_argument(
        "--enforce-completeness",
        action="store_true",
        help="Fail completeness when required questions have no validated evidence.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print full validated candidates list instead of only top-k.",
    )
    return parser


def _preview(text: str, limit: int = 220) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3] + "..."


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"PDF not found: {args.pdf_path}", file=sys.stderr)
        return 2
    if args.top_k < 1:
        print("top_k must be >= 1", file=sys.stderr)
        return 2
    if args.per_query_top_n < 1:
        print("per_query_top_n must be >= 1", file=sys.stderr)
        return 2
    if args.rrf_k < 1:
        print("rrf_k must be >= 1", file=sys.stderr)
        return 2
    if args.min_confidence < 0 or args.min_confidence > 1:
        print("min_confidence must be between 0 and 1", file=sys.stderr)
        return 2

    doc = parse_docling_pdf(args.pdf_path)
    question_set = load_question_bank()

    base_state: dict = {
        "doc_structure": doc.model_dump(),
        "question_set": question_set.model_dump(),
        "top_k": args.top_k,
        "per_query_top_n": args.per_query_top_n,
        "rrf_k": args.rrf_k,
        "query_planner": args.planner,
        "reranker": args.rerank,
        "use_structure": bool(args.structure),
        "splade_model_id": args.splade_model_id,
        "fusion_top_k": args.top_k,
        "fusion_rrf_k": args.rrf_k,
    }

    rule_based = rule_based_locator_node(base_state)
    bm25 = bm25_retrieval_locator_node(base_state)
    splade = splade_retrieval_locator_node(base_state)

    fused_state = {**base_state, **rule_based, **bm25, **splade}
    fusion = fusion_node(fused_state)

    relevance_state = {
        **fused_state,
        **fusion,
        "relevance_mode": args.relevance,
        "relevance_min_confidence": args.min_confidence,
        "relevance_require_quote": bool(args.require_quote),
        "relevance_top_k": args.top_k,
    }
    relevance = relevance_validator_node(relevance_state)

    existence_state = {
        **relevance_state,
        **relevance,
        "existence_top_k": args.top_k,
        "existence_require_text_match": bool(args.existence_require_text_match),
        "existence_require_quote_in_source": bool(args.existence_require_quote_in_source),
    }
    existence = existence_validator_node(existence_state)

    consistency_state = {
        **existence_state,
        **existence,
        "consistency_mode": args.consistency,
        "consistency_min_confidence": args.min_confidence,
    }
    consistency = consistency_validator_node(consistency_state)

    completeness_state = {
        **consistency_state,
        **consistency,
        "validated_top_k": args.top_k,
        "completeness_enforce": bool(args.enforce_completeness),
    }
    completeness = completeness_validator_node(completeness_state)

    validated_by_q = completeness.get("validated_candidates") or {}
    if not isinstance(validated_by_q, dict):
        print("Invalid validated output.", file=sys.stderr)
        return 2

    if args.question_id:
        items = validated_by_q.get(args.question_id)
        if not isinstance(items, list):
            print(f"Unknown question_id: {args.question_id}", file=sys.stderr)
            return 2
        _print_question(args.question_id, items, args)
        return 0

    report = completeness.get("completeness_report") or []
    failed = completeness.get("completeness_failed_questions") or []
    passed = bool(completeness.get("completeness_passed"))
    print(f"\nCompleteness: passed={passed} failed_questions={len(failed)}")
    if failed:
        print("  failed:", ", ".join(str(q) for q in failed))
    if isinstance(report, list) and report:
        satisfied = sum(1 for item in report if isinstance(item, dict) and item.get("status") == "satisfied")
        print(f"  satisfied_questions={satisfied} total_questions={len(report)}")

    for question_id in sorted(validated_by_q.keys()):
        items = validated_by_q.get(question_id)
        if not isinstance(items, list):
            continue
        print(f"\n== {question_id} ==")
        _print_question(question_id, items, args)

    return 0


def _print_question(question_id: str, items: list[dict], args: argparse.Namespace) -> None:
    selected = items if args.full else items[: args.top_k]
    print(f"Validated: {len(items)} (printing {len(selected)})")
    for idx, item in enumerate(selected, start=1):
        pid = item.get("paragraph_id")
        title = item.get("title")
        page = item.get("page")
        relevance = item.get("relevance") or {}
        label = relevance.get("label") if isinstance(relevance, dict) else None
        conf = relevance.get("confidence") if isinstance(relevance, dict) else None
        conf_value = float(conf) if isinstance(conf, (int, float)) else None
        conf_label = f"{conf_value:.2f}" if conf_value is not None else "-"
        label_str = str(label) if isinstance(label, str) else "unknown"
        print(
            f"{idx:>2}. relevance={label_str} conf={conf_label} pid={pid} page={page} title={title}"
        )
        text = item.get("text") or ""
        if isinstance(text, str):
            print(f"    text: {_preview(text)}")


if __name__ == "__main__":
    raise SystemExit(main())
