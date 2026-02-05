from __future__ import annotations

from langextract import data as lx_data

from preprocessing import document_metadata as dm
from schemas.internal.documents import SectionSpan


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
