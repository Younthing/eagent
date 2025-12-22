"""Check BM25 retrieval output with multi-query + RRF (Milestone 4/5)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipelines.graphs.nodes.preprocess import parse_docling_pdf  # noqa: E402
from retrieval.engines.bm25 import build_bm25_index  # noqa: E402
from retrieval.engines.fusion import rrf_fuse  # noqa: E402
from retrieval.query_planning.llm import (  # noqa: E402
    LLMQueryPlannerConfig,
    generate_query_plan_llm,
)
from retrieval.query_planning.planner import generate_queries_for_question  # noqa: E402
from retrieval.structure.filters import filter_spans_by_section_priors  # noqa: E402
from rob2.locator_rules import DEFAULT_LOCATOR_RULES, load_locator_rules  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402
from schemas.internal.rob2 import Rob2Question  # noqa: E402
from core.config import get_settings  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run BM25 retrieval + RRF and print top-k candidates.",
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
        help="Top-k candidates to print per question.",
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

    doc = parse_docling_pdf(args.pdf_path)
    question_set = load_question_bank()
    rules = load_locator_rules(args.rules_path)
    spans = doc.sections
    full_index = build_bm25_index(spans)
    full_mapping = list(range(len(spans)))

    query_plan = None
    if args.planner == "llm":
        settings = get_settings()
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

        if args.section_bonus_weight < 0:
            print("section_bonus_weight must be >= 0", file=sys.stderr)
            return 2

        if args.structure:
            priors = list(rules.domains[question.domain].section_priors)
            override = rules.question_overrides.get(question.question_id)
            if override and override.section_priors:
                priors.extend(override.section_priors)

            filtered = filter_spans_by_section_priors(spans, priors)
            if filtered.indices:
                mapping = filtered.indices
                index = build_bm25_index([spans[i] for i in mapping])
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
            hits = index.search(query, top_n=args.per_query_top_n)
            scored = []
            for hit in hits:
                original_index = mapping[hit.doc_index]
                section_score = section_scores.get(original_index, 0)
                composite = hit.score + section_score * args.section_bonus_weight
                scored.append((original_index, hit.score, composite))

            scored.sort(key=lambda item: (-item[2], -item[1], item[0]))
            per_query[query] = [
                (original_index, bm25_score)
                for original_index, bm25_score, _ in scored
            ]

        fused = rrf_fuse(per_query, k=args.rrf_k)
        if not fused:
            print("No candidates found.")
            continue

        items = fused if args.full else fused[: args.top_k]
        print(f"Candidates: {len(fused)} (printing {len(items)})")
        for idx, hit in enumerate(items, start=1):
            span = spans[hit.doc_index]
            section_score = section_scores.get(hit.doc_index, 0)
            matched = matched_priors.get(hit.doc_index) or []
            print(
                f"{idx:>2}. rrf={hit.rrf_score:.4f} best_rank={hit.best_rank} "
                f"bm25={hit.best_engine_score:.2f} section={section_score} "
                f"pid={span.paragraph_id} page={span.page} title={span.title}"
            )
            print(f"    best_query: {hit.best_query}")
            print(f"    query_ranks: {hit.query_ranks}")
            if matched:
                print(f"    matched_section_priors: {matched}")
            print(f"    text: {_preview(span.text)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
