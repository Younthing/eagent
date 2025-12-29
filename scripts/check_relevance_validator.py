"""Check relevance validation output on fused candidates (Milestone 7)."""

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
from pipelines.graphs.nodes.validators.relevance import (  # noqa: E402
    relevance_validator_node,
)
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402

DEFAULT_LOCAL_SPLADE = PROJECT_ROOT / "models" / "splade_distil_CoCodenser_large"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run locators + fusion, then validate relevance via LLM.",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a paper PDF.")
    parser.add_argument(
        "--question-id",
        default=None,
        help="Only print results for a single question_id (e.g. q1_1).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k fused candidates per question (also used by relevance output).",
    )
    parser.add_argument(
        "--per-query-top-n",
        type=int,
        default=50,
        help="Top-N hits kept per query before fusion (BM25/SPLADE).",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF k constant (BM25/SPLADE) and fusion RRF k.",
    )
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
        "--validator",
        choices=("none", "llm"),
        default="none",
        help="Relevance validator mode (Milestone 7).",
    )
    parser.add_argument(
        "--relevance-model",
        default=None,
        help="Model id for init_chat_model (e.g. openai:gpt-4o-mini). Defaults to RELEVANCE_MODEL.",
    )
    parser.add_argument(
        "--relevance-provider",
        default=None,
        help="Optional model_provider override for init_chat_model (defaults to RELEVANCE_MODEL_PROVIDER).",
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.6,
        help="Minimum confidence to treat label=relevant as pass.",
    )
    parser.add_argument(
        "--require-quote",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require supporting_quote to be an exact substring of paragraph text.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=None,
        help="Validate only the top-N fused candidates per question (default: top_k).",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print all annotated candidates instead of only top-k.",
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
    if args.top_n is not None and args.top_n < 1:
        print("top_n must be >= 1", file=sys.stderr)
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

    validation_state = {
        **fused_state,
        **fusion,
        "relevance_mode": args.validator,
        "relevance_model": args.relevance_model,
        "relevance_model_provider": args.relevance_provider,
        "relevance_min_confidence": args.min_confidence,
        "relevance_require_quote": bool(args.require_quote),
        "relevance_top_n": args.top_n,
        "relevance_top_k": args.top_k,
    }
    relevance = relevance_validator_node(validation_state)

    candidates_by_q = relevance.get("relevance_candidates") or {}
    debug_by_q = relevance.get("relevance_debug") or {}

    if args.question_id:
        items = candidates_by_q.get(args.question_id)
        if not isinstance(items, list):
            print(f"Unknown question_id: {args.question_id}", file=sys.stderr)
            return 2
        _print_question(args.question_id, items, debug_by_q.get(args.question_id), args)
        return 0

    bundles = relevance.get("relevance_evidence") or []
    if not isinstance(bundles, list):
        print("Invalid relevance output.", file=sys.stderr)
        return 2

    for bundle in bundles:
        question_id = bundle.get("question_id")
        if not isinstance(question_id, str):
            continue
        items = candidates_by_q.get(question_id) or []
        if not isinstance(items, list):
            continue
        print(f"\n== {question_id} ==")
        _print_question(question_id, items, debug_by_q.get(question_id), args)

    return 0


def _print_question(
    question_id: str,
    items: list[dict],
    debug: object,
    args: argparse.Namespace,
) -> None:
    annotated = items if args.full else items[: args.top_k]
    debug_payload: dict[str, object] = (
        {str(key): value for key, value in debug.items()} if isinstance(debug, dict) else {}
    )
    fallback = debug_payload.get("fallback_used")
    fallback_label = "fallback=True" if fallback else "fallback=False"

    print(f"Candidates: {len(items)} (printing {len(annotated)}) {fallback_label}")
    for idx, item in enumerate(annotated, start=1):
        pid = item.get("paragraph_id")
        title = item.get("title")
        page = item.get("page")
        relevance = item.get("relevance") or {}
        label = relevance.get("label") if isinstance(relevance, dict) else None
        conf = relevance.get("confidence") if isinstance(relevance, dict) else None
        conf_value = float(conf) if isinstance(conf, (int, float)) else None
        quote = relevance.get("supporting_quote") if isinstance(relevance, dict) else None
        quote_preview = _preview(quote, 120) if isinstance(quote, str) else "-"
        conf_label = f"{conf_value:.2f}" if conf_value is not None else "-"
        label_str = str(label) if isinstance(label, str) else "unknown"

        print(
            f"{idx:>2}. relevance={label_str} conf={conf_label} pid={pid} page={page} title={title}"
        )
        if quote_preview != "-":
            print(f"    quote: {quote_preview}")
        text = item.get("text") or ""
        if isinstance(text, str):
            print(f"    text: {_preview(text)}")


if __name__ == "__main__":
    raise SystemExit(main())
