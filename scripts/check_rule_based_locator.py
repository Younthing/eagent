"""Check rule-based locator output (Milestone 3)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pipelines.graphs.nodes.preprocess import parse_docling_pdf  # noqa: E402
from pipelines.graphs.nodes.locators.rule_based import rule_based_locate  # noqa: E402
from rob2.locator_rules import DEFAULT_LOCATOR_RULES, load_locator_rules  # noqa: E402
from rob2.question_bank import load_question_bank  # noqa: E402
from schemas.internal.evidence import EvidenceCandidate  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the rule-based locator and print top-k evidence candidates.",
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
        "--full",
        action="store_true",
        help="Print all scored candidates instead of only top-k.",
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

    candidates_by_q, bundles = rule_based_locate(
        doc,
        question_set,
        rules,
        top_k=args.top_k,
    )

    if args.question_id:
        if args.question_id not in candidates_by_q:
            print(f"Unknown question_id: {args.question_id}", file=sys.stderr)
            return 2
        _print_question(args.question_id, candidates_by_q[args.question_id], args)
        return 0

    for bundle in bundles:
        print(f"\n== {bundle.question_id} ==")
        _print_question(bundle.question_id, candidates_by_q[bundle.question_id], args)
    return 0


def _print_question(
    question_id: str,
    candidates: list[EvidenceCandidate],
    args: argparse.Namespace,
) -> None:
    items = candidates if args.full else candidates[: args.top_k]
    print(f"Candidates: {len(candidates)} (printing {len(items)})")
    for idx, candidate in enumerate(items, start=1):
        matched_keywords = candidate.matched_keywords or []
        keywords_label = ", ".join(matched_keywords) if matched_keywords else "-"
        print(
            f"{idx:>2}. score={candidate.score:.1f} "
            f"(section={candidate.section_score:.0f}, keyword={candidate.keyword_score:.0f}) "
            f"pid={candidate.paragraph_id} page={candidate.page} title={candidate.title}"
        )
        print(f"    keywords: {keywords_label}")
        print(f"    text: {_preview(candidate.text)}")


if __name__ == "__main__":
    raise SystemExit(main())
