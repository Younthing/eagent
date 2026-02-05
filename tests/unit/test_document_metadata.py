from __future__ import annotations

from langextract import data as lx_data
from langextract.resolver import ResolverParsingError

from preprocessing import document_metadata as dm
from schemas.internal.documents import DocStructure, SectionSpan


def test_metadata_mapping_and_sources() -> None:
    spans = [
        SectionSpan(
            paragraph_id="p1",
            title="body",
            page=1,
            text=(
                "TITLE\nAuthor A\nInstitution X\nFoundation Y\n"
                "(Received 9 January 1997)"
            ),
        )
    ]
    extractions = [
        lx_data.Extraction(extraction_class="title", extraction_text="TITLE"),
        lx_data.Extraction(extraction_class="author", extraction_text="Author A"),
        lx_data.Extraction(
            extraction_class="affiliation", extraction_text="Institution X"
        ),
        lx_data.Extraction(extraction_class="funding", extraction_text="Foundation Y"),
        lx_data.Extraction(
            extraction_class="date", extraction_text="Received 9 January 1997"
        ),
    ]
    metadata = dm._build_metadata_from_extractions(extractions, spans)

    assert metadata.title == "TITLE"
    assert metadata.authors == ["Author A"]
    assert metadata.affiliations == ["Institution X"]
    assert metadata.funders == ["Foundation Y"]
    assert metadata.year == 1997
    quotes = {source.quote for source in metadata.sources}
    assert "Author A" in quotes
    assert "Received 9 January 1997" in quotes


def test_extract_metadata_retries_when_parser_fails(monkeypatch) -> None:
    doc_structure = DocStructure(
        body=(
            "TITLE\nAuthor A\nInstitution X\nFoundation Y\n"
            "(Received 9 January 1997)"
        ),
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="body",
                page=1,
                text=(
                    "TITLE\nAuthor A\nInstitution X\nFoundation Y\n"
                    "(Received 9 January 1997)"
                ),
            )
        ],
    )

    calls: list[dict[str, object]] = []

    def _fake_extract(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise ResolverParsingError("mock parser failure")
        return lx_data.AnnotatedDocument(
            text=doc_structure.body,
            extractions=[
                lx_data.Extraction(extraction_class="title", extraction_text="TITLE"),
                lx_data.Extraction(
                    extraction_class="author", extraction_text="Author A"
                ),
                lx_data.Extraction(
                    extraction_class="affiliation", extraction_text="Institution X"
                ),
                lx_data.Extraction(
                    extraction_class="funding", extraction_text="Foundation Y"
                ),
                lx_data.Extraction(
                    extraction_class="date",
                    extraction_text="Received 9 January 1997",
                ),
            ],
        )

    monkeypatch.setattr(dm.lx, "extract", _fake_extract)
    monkeypatch.setattr(dm, "_ensure_anthropic_schema", lambda: None)
    monkeypatch.setattr(dm, "_ensure_anthropic_base_url", lambda: None)

    metadata = dm.extract_document_metadata(
        doc_structure,
        mode="llm",
        model_id="anthropic-claude-3-5-sonnet-latest",
        max_chars=4000,
        extraction_passes=1,
        max_output_tokens=512,
    )

    assert metadata is not None
    assert metadata.title == "TITLE"
    assert metadata.year == 1997
    assert metadata.extraction is not None
    assert metadata.extraction.error is None
    assert len(calls) == 2
    assert calls[0]["use_schema_constraints"] is True
    assert calls[1]["use_schema_constraints"] is False
    assert calls[1]["fence_output"] is True
