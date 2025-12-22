"""Check evidence fusion output across rule-based + BM25 + SPLADE (Milestone 6)."""

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
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402

DEFAULT_LOCAL_SPLADE = PROJECT_ROOT / "models" / "splade_distil_CoCodenser_large"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run rule-based + BM25 + SPLADE locators, then fuse candidates and print top-k.",
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
        help="Top-k fused evidence candidates to print per question.",
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
        "--planner-model",
        default=None,
        help="Model id for init_chat_model (e.g. openai:gpt-4o-mini). Defaults to QUERY_PLANNER_MODEL.",
    )
    parser.add_argument(
        "--planner-provider",
        default=None,
        help="Optional model_provider override for init_chat_model (defaults to QUERY_PLANNER_MODEL_PROVIDER).",
    )
    parser.add_argument(
        "--planner-temperature",
        type=float,
        default=None,
        help="Planner temperature (defaults to QUERY_PLANNER_TEMPERATURE, or 0).",
    )
    parser.add_argument(
        "--planner-max-keywords",
        type=int,
        default=10,
        help="Max keyword hints passed per question to the LLM planner.",
    )
    parser.add_argument(
        "--rerank",
        choices=("none", "cross_encoder"),
        default="none",
        help="Optional post-RRF reranker for BM25/SPLADE candidates.",
    )
    parser.add_argument(
        "--rerank-model-id",
        default=None,
        help="Cross-encoder model id or local path (defaults to RERANKER_MODEL_ID).",
    )
    parser.add_argument(
        "--rerank-device",
        default=None,
        help="Cross-encoder device override (cpu|cuda|mps). Defaults to RERANKER_DEVICE.",
    )
    parser.add_argument(
        "--rerank-max-length",
        type=int,
        default=None,
        help="Tokenizer max length for reranker (defaults to RERANKER_MAX_LENGTH, 512).",
    )
    parser.add_argument(
        "--rerank-batch-size",
        type=int,
        default=None,
        help="Batch size for reranker (defaults to RERANKER_BATCH_SIZE, 8).",
    )
    parser.add_argument(
        "--rerank-top-n",
        type=int,
        default=None,
        help="Rerank only the top-N fused candidates (defaults to RERANKER_TOP_N, 50).",
    )
    parser.add_argument(
        "--structure",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable structure-aware corpus filtering (Milestone 5).",
    )
    parser.add_argument(
        "--section-bonus-weight",
        type=float,
        default=0.25,
        help="Section score bonus weight for per-query ranking.",
    )
    parser.add_argument(
        "--splade-model-id",
        default=str(DEFAULT_LOCAL_SPLADE)
        if DEFAULT_LOCAL_SPLADE.exists()
        else DEFAULT_SPLADE_MODEL_ID,
        help="HuggingFace model id or local path for SPLADE.",
    )
    parser.add_argument(
        "--splade-device",
        default=None,
        help="Torch device override for SPLADE (cpu|cuda|mps).",
    )
    parser.add_argument(
        "--splade-hf-token",
        default=None,
        help="HuggingFace token for gated models (or set HF_TOKEN / HUGGINGFACE_HUB_TOKEN).",
    )
    parser.add_argument(
        "--splade-doc-max-length",
        type=int,
        default=256,
        help="Tokenizer max length for document spans in SPLADE.",
    )
    parser.add_argument(
        "--splade-query-max-length",
        type=int,
        default=64,
        help="Tokenizer max length for queries in SPLADE.",
    )
    parser.add_argument(
        "--splade-batch-size",
        type=int,
        default=8,
        help="Batch size for SPLADE encoding.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Print all fused candidates instead of only top-k.",
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

    if args.section_bonus_weight < 0:
        print("section_bonus_weight must be >= 0", file=sys.stderr)
        return 2

    doc = parse_docling_pdf(args.pdf_path)
    question_set = load_question_bank()

    base_state: dict = {
        "doc_structure": doc.model_dump(),
        "question_set": question_set.model_dump(),
        "top_k": args.top_k,
        "per_query_top_n": args.per_query_top_n,
        "rrf_k": args.rrf_k,
        "use_structure": bool(args.structure),
        "section_bonus_weight": args.section_bonus_weight,
        "query_planner": args.planner,
        "query_planner_model": args.planner_model,
        "query_planner_model_provider": args.planner_provider,
        "query_planner_temperature": args.planner_temperature,
        "query_planner_max_keywords": args.planner_max_keywords,
        "reranker": args.rerank,
        "reranker_model_id": args.rerank_model_id,
        "reranker_device": args.rerank_device,
        "reranker_max_length": args.rerank_max_length,
        "reranker_batch_size": args.rerank_batch_size,
        "rerank_top_n": args.rerank_top_n,
        "splade_model_id": args.splade_model_id,
        "splade_device": args.splade_device,
        "splade_hf_token": args.splade_hf_token,
        "splade_doc_max_length": args.splade_doc_max_length,
        "splade_query_max_length": args.splade_query_max_length,
        "splade_batch_size": args.splade_batch_size,
        "fusion_top_k": args.top_k,
        "fusion_rrf_k": args.rrf_k,
    }

    rule_based = rule_based_locator_node(base_state)
    bm25 = bm25_retrieval_locator_node(base_state)
    splade = splade_retrieval_locator_node(base_state)

    fused_state = {**base_state, **rule_based, **bm25, **splade}
    fusion = fusion_node(fused_state)
    candidates_by_q = fusion.get("fusion_candidates") or {}

    if args.question_id:
        items = candidates_by_q.get(args.question_id)
        if not isinstance(items, list):
            print(f"Unknown question_id: {args.question_id}", file=sys.stderr)
            return 2
        _print_question(args.question_id, items, args)
        return 0

    evidence = fusion.get("fusion_evidence") or []
    if not isinstance(evidence, list):
        print("Invalid fusion output.", file=sys.stderr)
        return 2

    for bundle in evidence:
        question_id = bundle.get("question_id")
        if not isinstance(question_id, str):
            continue
        items = candidates_by_q.get(question_id) or []
        if not isinstance(items, list):
            continue
        print(f"\n== {question_id} ==")
        _print_question(question_id, items, args)

    return 0


def _print_question(question_id: str, items: list[dict], args: argparse.Namespace) -> None:
    fused = items if args.full else items[: args.top_k]
    print(f"Candidates: {len(items)} (printing {len(fused)})")
    for idx, item in enumerate(fused, start=1):
        pid = item.get("paragraph_id")
        title = item.get("title")
        page = item.get("page")
        fusion_score_value = 0.0
        fusion_score_raw = item.get("fusion_score")
        if isinstance(fusion_score_raw, (int, float)):
            fusion_score_value = float(fusion_score_raw)
        elif isinstance(fusion_score_raw, str):
            try:
                fusion_score_value = float(fusion_score_raw)
            except ValueError:
                fusion_score_value = 0.0
        supports = item.get("supports") or []
        engines = []
        if isinstance(supports, list):
            for support in supports:
                if isinstance(support, dict):
                    engine = support.get("engine")
                    rank = support.get("rank")
                    if isinstance(engine, str) and isinstance(rank, int):
                        engines.append(f"{engine}#{rank}")
        engines_label = ", ".join(engines) if engines else "-"
        print(
            f"{idx:>2}. fusion={fusion_score_value:.4f} supports={engines_label} "
            f"pid={pid} page={page} title={title}"
        )
        text = item.get("text") or ""
        if isinstance(text, str):
            print(f"    text: {_preview(text)}")


if __name__ == "__main__":
    raise SystemExit(main())
