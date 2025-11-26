from types import SimpleNamespace

from eagent.utils import parsing


def test_parse_pdf_structure_uses_docling(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.pdf"
    file_path.write_text("ignored", encoding="utf-8")

    class FakeLoader:
        def __init__(self, file_path: str):
            self.file_path = file_path

        def load(self):
            return [
                SimpleNamespace(page_content="Chunk A"),
                SimpleNamespace(page_content="Chunk B"),
            ]

    monkeypatch.setattr(parsing, "DoclingLoader", FakeLoader)

    result = parsing.parse_pdf_structure(str(file_path))

    assert result["body"] == "Chunk A\n\nChunk B"


def test_parse_pdf_structure_fallbacks_to_plain_text(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text(" Example content ", encoding="utf-8")
    monkeypatch.setattr(parsing, "DoclingLoader", None)

    result = parsing.parse_pdf_structure(str(file_path))

    assert result["body"] == "Example content"
