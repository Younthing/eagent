"""CLI entrypoint for quick Docling parsing checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pipelines.graphs.nodes.preprocess import parse_docling_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse a PDF with Docling and print a summary.",
    )
    parser.add_argument("pdf_path", help="Path to the PDF file.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full DocStructure as JSON.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    doc = parse_docling_pdf(pdf_path)

    if args.json:
        print(json.dumps(doc.model_dump(), ensure_ascii=True, indent=2))
        return 0

    titles = [span.title for span in doc.sections if span.title]
    unique_titles = sorted({title for title in titles if title})

    print(f"Parsed: {pdf_path}")
    print(f"Body length: {len(doc.body)}")
    print(f"Section spans: {len(doc.sections)}")
    if unique_titles:
        print("Section titles:")
        for title in unique_titles:
            print(f"  - {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
