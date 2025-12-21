"""Check BM25 retrieval output with multi-query + RRF (Milestone 4)."""

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
from retrieval.query_planning.planner import generate_queries_for_question  # noqa: E402
from rob2.locator_rules import DEFAULT_LOCATOR_RULES, load_locator_rules  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402
from schemas.internal.rob2 import Rob2Question  # noqa: E402


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
    index = build_bm25_index(doc.sections)

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
        queries = generate_queries_for_question(question, rules)
        print(f"Queries ({len(queries)}):")
        for q in queries:
            print(f"  - {q}")

        per_query = {}
        for query in queries:
            hits = index.search(query, top_n=args.per_query_top_n)
            per_query[query] = [(hit.doc_index, hit.score) for hit in hits]

        fused = rrf_fuse(per_query, k=args.rrf_k)
        if not fused:
            print("No candidates found.")
            continue

        items = fused if args.full else fused[: args.top_k]
        print(f"Candidates: {len(fused)} (printing {len(items)})")
        for idx, hit in enumerate(items, start=1):
            span = doc.sections[hit.doc_index]
            print(
                f"{idx:>2}. rrf={hit.rrf_score:.4f} best_rank={hit.best_rank} "
                f"bm25={hit.best_engine_score:.2f} pid={span.paragraph_id} page={span.page} title={span.title}"
            )
            print(f"    best_query: {hit.best_query}")
            print(f"    query_ranks: {hit.query_ranks}")
            print(f"    text: {_preview(span.text)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

