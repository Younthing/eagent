"""Check and print a summary of the ROB2 question bank (Milestone 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from rob2.question_bank import DEFAULT_QUESTION_BANK, load_question_bank  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load and validate the ROB2 question bank and print a summary.",
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_QUESTION_BANK,
        help="Path to rob2_questions.yaml (default: src/rob2/rob2_questions.yaml).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full QuestionSet as JSON.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        question_set = load_question_bank(args.path)
    except Exception as exc:
        print(f"Failed to load question bank: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(question_set.model_dump(), ensure_ascii=True, indent=2))
        return 0

    assignment = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "assignment"
    ]
    adherence = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "adherence"
    ]

    print(f"Question bank: {args.path}")
    print(f"Version: {question_set.version}")
    print(f"Variant: {question_set.variant}")
    print(f"Total questions: {len(question_set.questions)}")
    print(f"D2 assignment questions: {len(assignment)}")
    print(f"D2 adherence questions: {len(adherence)}")
    print("First/last question_id:")
    print(f"  first: {question_set.questions[0].question_id}")
    print(f"  last:  {question_set.questions[-1].question_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

