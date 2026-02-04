from __future__ import annotations

from preprocessing.doc_scope import apply_doc_scope
from schemas.internal.documents import DocStructure, SectionSpan


def _span(pid: str, text: str, page: int | None, title: str = "body") -> SectionSpan:
    return SectionSpan(
        paragraph_id=pid,
        title=title,
        page=page,
        text=text,
    )


def _doc(spans: list[SectionSpan]) -> DocStructure:
    body = "\n\n".join(span.text for span in spans)
    return DocStructure(body=body, sections=spans)


def test_doc_scope_auto_english_cuts_second_article() -> None:
    spans = [
        _span("p1", "Abstract Keywords: randomization. DOI: 10.1234/main", 1, "Abstract"),
        _span("p2", "Methods: allocation concealment.", 2, "Methods"),
        _span("p3", "Results: primary outcome.", 3, "Results"),
        _span("p4", "Abstract Keywords: another trial. DOI: 10.5678/other", 4, "Abstract"),
        _span("p5", "Methods for another trial.", 5, "Methods"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="auto",
        include_paragraph_ids=None,
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "scoped"
    assert report["selected_pages"] == [1, 2, 3]
    assert len(doc.sections) == 3


def test_doc_scope_auto_chinese_cuts_second_article() -> None:
    spans = [
        _span("c1", "摘要 关键词 随机分配。DOI: 10.2222/main", 1, "摘要"),
        _span("c2", "方法：随机化与盲法。", 2, "方法"),
        _span("c3", "结果：主要结局。", 3, "结果"),
        _span("c4", "摘要 关键词 另一研究。DOI: 10.3333/other", 4, "摘要"),
        _span("c5", "方法：另一研究的方法。", 5, "方法"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="auto",
        include_paragraph_ids=None,
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "scoped"
    assert report["selected_pages"] == [1, 2, 3]
    assert len(doc.sections) == 3


def test_doc_scope_auto_same_page_two_articles() -> None:
    spans = [
        _span("s1", "Abstract Keywords: main study. DOI: 10.1000/main", 1, "Abstract"),
        _span("s2", "Methods: main trial.", 1, "Methods"),
        _span("s3", "Abstract Keywords: other study. DOI: 10.2000/other", 1, "Abstract"),
        _span("s4", "Methods: other trial.", 1, "Methods"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="auto",
        include_paragraph_ids=None,
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "scoped"
    assert doc.sections[0].paragraph_id == "s1"
    assert doc.sections[-1].paragraph_id == "s2"


def test_doc_scope_auto_bilingual_abstract_no_cut() -> None:
    spans = [
        _span("b1", "Abstract Keywords: main trial.", 1, "Abstract"),
        _span("b2", "摘要 关键词 主要研究。", 1, "摘要"),
        _span("b3", "Methods: main trial.", 2, "Methods"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="auto",
        include_paragraph_ids=None,
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "insufficient_signals"
    assert len(doc.sections) == 3


def test_doc_scope_manual_paragraph_ids() -> None:
    spans = [
        _span("m1", "Abstract Keywords: main trial.", 1, "Abstract"),
        _span("m2", "Methods: main trial.", 2, "Methods"),
        _span("m3", "Results: main trial.", 3, "Results"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="manual",
        include_paragraph_ids={"m2", "m3"},
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "manual_paragraph_ids"
    assert {span.paragraph_id for span in doc.sections} == {"m2", "m3"}


def test_doc_scope_manual_page_range() -> None:
    spans = [
        _span("p1", "Abstract", 1),
        _span("p2", "Methods", 2),
        _span("p3", "Results", 3),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="manual",
        include_paragraph_ids=None,
        page_range="2-3",
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "manual_page_range"
    assert report["selected_pages"] == [2, 3]
    assert {span.paragraph_id for span in doc.sections} == {"p2", "p3"}


def test_doc_scope_missing_page_info_skips() -> None:
    spans = [
        _span("u1", "Abstract Keywords: main trial.", None, "Abstract"),
        _span("u2", "Methods: main trial.", None, "Methods"),
        _span("u3", "Results: main trial.", None, "Results"),
    ]
    doc, report = apply_doc_scope(
        _doc(spans),
        mode="auto",
        include_paragraph_ids=None,
        page_range=None,
        min_pages=1,
        min_confidence=0.6,
        abstract_gap_pages=3,
    )

    assert report["reason"] == "missing_page_info"
    assert len(doc.sections) == 3
