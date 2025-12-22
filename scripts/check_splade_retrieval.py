"""Check SPLADE retrieval output with multi-query + RRF (Milestone 4/5)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipelines.graphs.nodes.preprocess import parse_docling_pdf  # noqa: E402
from retrieval.engines.faiss_ip import build_ip_index, search_ip  # noqa: E402
from retrieval.engines.fusion import rrf_fuse  # noqa: E402
from retrieval.engines.splade import (  # noqa: E402
    DEFAULT_SPLADE_MODEL_ID,
    get_splade_encoder,
)
from retrieval.query_planning.llm import (  # noqa: E402
    LLMQueryPlannerConfig,
    generate_query_plan_llm,
)
from retrieval.query_planning.planner import generate_queries_for_question  # noqa: E402
from retrieval.rerankers.cross_encoder import (  # noqa: E402
    DEFAULT_CROSS_ENCODER_MODEL_ID,
    get_cross_encoder_reranker,
)
from retrieval.structure.filters import filter_spans_by_section_priors  # noqa: E402
from rob2.locator_rules import DEFAULT_LOCATOR_RULES, load_locator_rules  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402
from schemas.internal.rob2 import Rob2Question  # noqa: E402
from core.config import get_settings  # noqa: E402

DEFAULT_LOCAL_SPLADE = PROJECT_ROOT / "models" / "splade_distil_CoCodenser_large"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run SPLADE (naver/splade-v3) retrieval + RRF and print top-k candidates.",
    )
    parser.add_argument("pdf_path", type=Path, help="Path to a paper PDF.")
    parser.add_argument(
        "--question-id",
        default=None,
        help="Only print results for a single question_id (e.g. q1_1).",
    )
    parser.add_argument(
        "--model-id",
        default=str(DEFAULT_LOCAL_SPLADE)
        if DEFAULT_LOCAL_SPLADE.exists()
        else DEFAULT_SPLADE_MODEL_ID,
        help="HuggingFace model id or local path for SPLADE.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Torch device override (e.g. cpu, cuda, mps).",
    )
    parser.add_argument(
        "--hf-token",
        default=None,
        help="HuggingFace token for gated models (or set HF_TOKEN / HUGGINGFACE_HUB_TOKEN).",
    )
    parser.add_argument(
        "--doc-max-length",
        type=int,
        default=256,
        help="Tokenizer max length for document spans.",
    )
    parser.add_argument(
        "--query-max-length",
        type=int,
        default=64,
        help="Tokenizer max length for queries.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for SPLADE encoding.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k fused candidates to print per question.",
    )
    parser.add_argument(
        "--per-query-top-n",
        type=int,
        default=50,
        help="Top-N hits kept per query before fusion.",
    )
    parser.add_argument(
        "--rrf-k",
        type=int,
        default=60,
        help="RRF k constant.",
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
        help="Optional post-RRF reranker.",
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
        "--full",
        action="store_true",
        help="Print all fused candidates instead of only top-k.",
    )
    parser.add_argument(
        "--rules-path",
        type=Path,
        default=DEFAULT_LOCATOR_RULES,
        help="Path to locator_rules.yaml (default: src/rob2/locator_rules.yaml).",
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
    spans = doc.sections
    if not spans:
        print("No spans found in document.", file=sys.stderr)
        return 2

    question_set = load_question_bank()
    rules = load_locator_rules(args.rules_path)

    settings = get_settings()
    query_plan = None
    if args.planner == "llm":
        model_id = (args.planner_model or settings.query_planner_model or "").strip()
        if not model_id:
            print(
                "Missing planner model. Set --planner-model or QUERY_PLANNER_MODEL.",
                file=sys.stderr,
            )
            return 2
        model_provider = args.planner_provider or settings.query_planner_model_provider
        temperature = (
            args.planner_temperature
            if args.planner_temperature is not None
            else settings.query_planner_temperature
        )
        config = LLMQueryPlannerConfig(
            model=model_id,
            model_provider=str(model_provider) if model_provider else None,
            temperature=float(temperature),
            timeout=settings.query_planner_timeout,
            max_tokens=settings.query_planner_max_tokens,
            max_retries=settings.query_planner_max_retries,
        )
        try:
            query_plan = generate_query_plan_llm(
                question_set,
                rules,
                config=config,
                max_queries_per_question=5,
                max_keywords_per_question=args.planner_max_keywords,
            )
        except Exception as exc:
            print(f"LLM planner failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    reranker = None
    reranker_top_n = None
    reranker_max_length = None
    reranker_batch_size = None
    if args.rerank == "cross_encoder":
        rerank_model_id = (
            args.rerank_model_id
            or settings.reranker_model_id
            or DEFAULT_CROSS_ENCODER_MODEL_ID
        )
        reranker_top_n = (
            args.rerank_top_n if args.rerank_top_n is not None else settings.reranker_top_n
        )
        reranker_max_length = (
            args.rerank_max_length
            if args.rerank_max_length is not None
            else settings.reranker_max_length
        )
        reranker_batch_size = (
            args.rerank_batch_size
            if args.rerank_batch_size is not None
            else settings.reranker_batch_size
        )
        device = args.rerank_device or settings.reranker_device
        try:
            reranker = get_cross_encoder_reranker(model_id=rerank_model_id, device=device)
            print(f"Reranker: {rerank_model_id} on {reranker.device} (top_n={reranker_top_n})")
        except Exception as exc:
            print(f"Failed to load reranker: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2

    questions: list[Rob2Question]
    if args.question_id:
        selected = [
            q for q in question_set.questions if q.question_id == args.question_id
        ]
        if not selected:
            print(f"Unknown question_id: {args.question_id}", file=sys.stderr)
            return 2
        questions = selected
    else:
        questions = question_set.questions

    encoder = get_splade_encoder(
        model_id=args.model_id, device=args.device, hf_token=args.hf_token
    )
    print(f"Encoder: {args.model_id} on {encoder.device}")

    doc_vectors = encoder.encode(
        [span.text for span in spans],
        max_length=args.doc_max_length,
        batch_size=args.batch_size,
    )
    full_index = build_ip_index(doc_vectors)
    full_mapping = list(range(len(spans)))

    for question in questions:
        print(f"\n== {question.question_id} ({question.domain}) ==")
        if query_plan is not None:
            queries = query_plan.get(question.question_id) or []
        else:
            queries = generate_queries_for_question(question, rules)
        print(f"Queries ({len(queries)}):")
        for q in queries:
            print(f"  - {q}")

        index = full_index
        mapping = full_mapping
        section_scores = {}
        matched_priors = {}
        fallback_used = False

        if args.structure:
            priors = list(rules.domains[question.domain].section_priors)
            override = rules.question_overrides.get(question.question_id)
            if override and override.section_priors:
                priors.extend(override.section_priors)

            filtered = filter_spans_by_section_priors(spans, priors)
            if filtered.indices:
                mapping = filtered.indices
                index = build_ip_index(doc_vectors[mapping])
                section_scores = filtered.section_scores
                matched_priors = filtered.matched_priors
            else:
                fallback_used = True

            print(
                f"Structure-aware: filtered_spans={len(mapping) if not fallback_used else 0} "
                f"total_spans={len(spans)} fallback={fallback_used}"
            )

        per_query = {}
        for query in queries:
            query_vec = encoder.encode([query], max_length=args.query_max_length)
            scores, local_indices = search_ip(index, query_vec, top_n=args.per_query_top_n)
            ranked = []
            if scores.size and local_indices.size:
                for local_idx, raw_score in zip(
                    local_indices[0].tolist(),
                    scores[0].tolist(),
                    strict=False,
                ):
                    if local_idx < 0:
                        continue
                    original_index = mapping[int(local_idx)]
                    section_score = section_scores.get(original_index, 0)
                    composite = float(raw_score) + section_score * args.section_bonus_weight
                    ranked.append((original_index, float(raw_score), composite))
            ranked.sort(key=lambda item: (-item[2], -item[1], item[0]))
            per_query[query] = [
                (original_index, raw_score) for original_index, raw_score, _ in ranked
            ]

        fused = rrf_fuse(per_query, k=args.rrf_k)
        if not fused:
            print("No candidates found.")
            continue

        rerank_scores = {}
        fused_for_print = fused
        if reranker is not None:
            top_n = min(int(reranker_top_n or 50), len(fused))
            head = fused[:top_n]
            passages = []
            for hit in head:
                span = spans[hit.doc_index]
                title = span.title.strip() if span.title else ""
                body = span.text.strip() if span.text else ""
                passages.append(f"{title}\n\n{body}".strip() if title else body)

            result = reranker.rerank(
                question.text,
                passages,
                max_length=int(reranker_max_length or 512),
                batch_size=int(reranker_batch_size or 8),
            )
            rerank_scores = {
                head[i].doc_index: float(result.scores[i]) for i in range(len(head))
            }
            fused_for_print = [head[i] for i in result.order] + fused[top_n:]

        items = fused_for_print if args.full else fused_for_print[: args.top_k]
        print(f"Candidates: {len(fused_for_print)} (printing {len(items)})")
        for idx, hit in enumerate(items, start=1):
            span = spans[hit.doc_index]
            section_score = section_scores.get(hit.doc_index, 0)
            matched = matched_priors.get(hit.doc_index) or []
            rerank_score = rerank_scores.get(hit.doc_index)
            rerank_label = f" rerank={rerank_score:.4f}" if rerank_score is not None else ""
            print(
                f"{idx:>2}. rrf={hit.rrf_score:.4f} best_rank={hit.best_rank} "
                f"splade={hit.best_engine_score:.4f} section={section_score} "
                f"pid={span.paragraph_id} page={span.page} title={span.title}{rerank_label}"
            )
            print(f"    best_query: {hit.best_query}")
            print(f"    query_ranks: {hit.query_ranks}")
            if matched:
                print(f"    matched_section_priors: {matched}")
            print(f"    text: {_preview(span.text)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
