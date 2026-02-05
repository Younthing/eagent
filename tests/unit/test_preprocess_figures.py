from __future__ import annotations

from pipelines.graphs.nodes import preprocess as pp
from schemas.internal.documents import FigureSpan, SectionSpan


def test_parse_docling_pdf_attaches_figures_and_config(monkeypatch) -> None:
    spans = [SectionSpan(paragraph_id="p1", title="Methods", page=1, text="Text")]
    figures = [FigureSpan(figure_id="fig-1", page=1, caption="Figure 1")]

    monkeypatch.setattr(pp, "_resolve_docling_source", lambda source: "dummy.pdf")

    def _fake_load(source: str, *, overrides: dict | None = None):
        assert source == "dummy.pdf"
        return spans, "Text", {"pipeline": "standard_pdf"}, object()

    def _fake_extract(
        source: str,
        *,
        converter: object,
        overrides: dict | None = None,
    ):
        assert source == "dummy.pdf"
        assert converter is not None
        return figures, {"figure_count": 1}

    monkeypatch.setattr(pp, "_load_with_docling", _fake_load)
    monkeypatch.setattr(pp, "_extract_figures_with_docling", _fake_extract)

    doc = pp.parse_docling_pdf("dummy.pdf")

    assert len(doc.sections) == 1
    assert len(doc.figures) == 1
    assert doc.figures[0].figure_id == "fig-1"
    assert doc.docling_config == {"pipeline": "standard_pdf", "figure_count": 1}


def test_parse_docling_pdf_keeps_empty_figures(monkeypatch) -> None:
    spans = [SectionSpan(paragraph_id="p1", title="Methods", page=1, text="Text")]

    monkeypatch.setattr(pp, "_resolve_docling_source", lambda source: "dummy.pdf")

    def _fake_load(source: str, *, overrides: dict | None = None):
        return spans, "Text", {"pipeline": "standard_pdf"}, object()

    def _fake_extract(
        source: str,
        *,
        converter: object,
        overrides: dict | None = None,
    ):
        return [], {}

    monkeypatch.setattr(pp, "_load_with_docling", _fake_load)
    monkeypatch.setattr(pp, "_extract_figures_with_docling", _fake_extract)

    doc = pp.parse_docling_pdf("dummy.pdf")

    assert doc.figures == []
