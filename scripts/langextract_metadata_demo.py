#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import textwrap
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv

import langextract as lx
from langextract.resolver import ResolverParsingError


def _find_latest_doc_structure(root: Path) -> Path | None:
    candidates = list(root.rglob("doc_structure.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _load_doc_text(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    body = payload.get("body")
    if isinstance(body, str) and body.strip():
        return body.strip()
    sections = payload.get("sections") or []
    parts: list[str] = []
    for item in sections:
        text = item.get("text") if isinstance(item, dict) else None
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _build_prompt() -> str:
    return textwrap.dedent(
        """\
        Extract publication metadata in order of appearance.
        Use exact text spans for each extraction. Do not paraphrase.
        Do not overlap entities. If an item is missing, skip it.
        Use these classes: title, author, affiliation, date, funding.
        Add attributes when helpful (e.g., date type: received/accepted/published).
        """
    )


def _build_examples() -> list[lx.data.ExampleData]:
    example_text = (
        "EFFICACY OF XYZ IN TREATMENT\n"
        "Jane Doe, John Smith\n"
        "Department of Psychiatry, University of Example, London, UK\n"
        "Funding: Supported by ABC Foundation grant 1234\n"
        "(Received 12 March 2021; accepted 20 June 2021)"
    )
    return [
        lx.data.ExampleData(
            text=example_text,
            extractions=[
                lx.data.Extraction(
                    extraction_class="title",
                    extraction_text="EFFICACY OF XYZ IN TREATMENT",
                    attributes={"type": "article_title"},
                ),
                lx.data.Extraction(
                    extraction_class="author",
                    extraction_text="Jane Doe",
                    attributes={"role": "author"},
                ),
                lx.data.Extraction(
                    extraction_class="author",
                    extraction_text="John Smith",
                    attributes={"role": "author"},
                ),
                lx.data.Extraction(
                    extraction_class="affiliation",
                    extraction_text="Department of Psychiatry, University of Example, London, UK",
                    attributes={"kind": "institution"},
                ),
                lx.data.Extraction(
                    extraction_class="funding",
                    extraction_text="Supported by ABC Foundation grant 1234",
                    attributes={"funder": "ABC Foundation"},
                ),
                lx.data.Extraction(
                    extraction_class="date",
                    extraction_text="Received 12 March 2021",
                    attributes={"type": "received"},
                ),
                lx.data.Extraction(
                    extraction_class="date",
                    extraction_text="accepted 20 June 2021",
                    attributes={"type": "accepted"},
                ),
            ],
        )
    ]


def _ensure_anthropic_schema() -> None:
    try:
        from langextract_anthropic.schema import AnthropicSchema
    except Exception:
        return

    abstract_methods = getattr(AnthropicSchema, "__abstractmethods__", frozenset())
    if "requires_raw_output" not in abstract_methods:
        return

    def _requires_raw_output(self) -> bool:
        return True

    AnthropicSchema.requires_raw_output = property(_requires_raw_output)
    AnthropicSchema.__abstractmethods__ = frozenset(
        name for name in abstract_methods if name != "requires_raw_output"
    )


def _ensure_anthropic_base_url() -> None:
    try:
        from langextract_anthropic import provider as anth_provider
    except Exception:
        return

    if getattr(anth_provider.AnthropicLanguageModel, "_patched_base_url", False):
        return

    original_init = anth_provider.AnthropicLanguageModel.__init__

    def _patched_init(self, *args, **kwargs) -> None:
        base_url = kwargs.pop("base_url", None) or kwargs.pop("model_url", None)
        original_init(self, *args, **kwargs)
        if base_url:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.api_key, base_url=base_url)
            self._base_url = base_url

    setattr(cast(Any, anth_provider.AnthropicLanguageModel), "__init__", _patched_init)
    anth_provider.AnthropicLanguageModel._patched_base_url = True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LangExtract metadata demo.")
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to doc_structure.json. Defaults to latest in data/rob2/runs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/langextract"),
        help="Directory to write JSONL/HTML outputs.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model id for LangExtract (overrides LANGEXTRACT_MODEL_ID).",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["auto", "anthropic", "openai"],
        default="auto",
        help="Model provider hint (auto selects by model id).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key override (otherwise uses provider env vars).",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL override (otherwise uses provider env vars).",
    )
    parser.add_argument(
        "--fence-output",
        action="store_true",
        help="Force fenced JSON output parsing.",
    )
    parser.add_argument(
        "--no-schema",
        action="store_true",
        help="Disable schema constraints (more tolerant, less strict).",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=1024,
        help="Max output tokens for the model.",
    )
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--extraction-passes", type=int, default=2)
    parser.add_argument("--max-char-buffer", type=int, default=1200)
    return parser.parse_args()


def main() -> None:
    load_dotenv()

    args = _parse_args()
    input_path = args.input
    if input_path is None:
        input_path = _find_latest_doc_structure(Path("data/rob2/runs"))
        if input_path is None:
            raise FileNotFoundError("No doc_structure.json found under data/rob2/runs.")

    doc_text = _load_doc_text(input_path)
    if not doc_text:
        raise ValueError(f"No text found in {input_path}.")

    provider = args.provider
    model_id = args.model or os.getenv("LANGEXTRACT_MODEL_ID")
    if not model_id:
        if provider == "openai":
            model_id = "gpt-4o-mini"
        else:
            model_id = "anthropic-claude-3-5-sonnet-latest"

    provider_effective = provider
    if provider_effective == "auto":
        lowered = model_id.lower()
        if lowered.startswith(("gpt-4", "gpt4", "gpt-5", "gpt5")):
            provider_effective = "openai"

    api_key = args.api_key
    base_url = args.base_url
    if provider_effective == "openai":
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if base_url is None:
            base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL")
    elif provider_effective == "anthropic":
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if base_url is None:
            base_url = os.getenv("ANTHROPIC_BASE_URL")

    _ensure_anthropic_schema()
    _ensure_anthropic_base_url()

    fence_output = args.fence_output
    if provider_effective == "anthropic" and not fence_output:
        fence_output = True
    use_schema_constraints = not args.no_schema

    def _run_extract(*, use_schema: bool, fences: bool) -> lx.data.AnnotatedDocument:
        return lx.extract(
            text_or_documents=doc_text,
            prompt_description=_build_prompt(),
            examples=_build_examples(),
            model_id=model_id,
            api_key=api_key,
            model_url=base_url,
            fence_output=fences,
            use_schema_constraints=use_schema,
            language_model_params={"max_tokens": args.max_output_tokens},
            max_workers=args.max_workers,
            extraction_passes=args.extraction_passes,
            max_char_buffer=args.max_char_buffer,
        )

    try:
        result = _run_extract(use_schema=use_schema_constraints, fences=fence_output)
    except ResolverParsingError:
        result = _run_extract(use_schema=False, fences=True)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_jsonl = output_dir / "langextract_metadata.jsonl"
    lx.io.save_annotated_documents(
        [result], output_name=output_jsonl.name, output_dir=str(output_dir)
    )

    html = lx.visualize(str(output_jsonl))
    output_html = output_dir / "langextract_metadata.html"
    html_content = html.data if hasattr(html, "data") else str(html)
    output_html.write_text(html_content, encoding="utf-8")

    print(f"Wrote {output_jsonl}")
    print(f"Wrote {output_html}")


if __name__ == "__main__":
    main()
