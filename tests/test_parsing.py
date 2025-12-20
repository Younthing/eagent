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
                SimpleNamespace(
                    page_content="Chunk A",
                    metadata={
                        "dl_meta": {
                            "headings": ["3.2 AI 模型"],
                            "doc_items": [
                                {
                                    "prov": [
                                        {
                                            "page_no": 3,
                                            "bbox": {
                                                "l": 108.0,
                                                "t": 405.14,
                                                "r": 504.0,
                                                "b": 330.78,
                                                "coord_origin": "BOTTOMLEFT",
                                            },
                                        }
                                    ]
                                }
                            ],
                        }
                    },
                ),
                SimpleNamespace(
                    page_content="Chunk B",
                    metadata={
                        "dl_meta": {
                            "headings": ["Intro", "Sub"],
                            "doc_items": [
                                {
                                    "prov": [
                                        {
                                            "page_no": 5,
                                            "bbox": {
                                                "l": 1,
                                                "t": 2,
                                                "r": 3,
                                                "b": 4,
                                                "coord_origin": "TOPLEFT",
                                            },
                                        }
                                    ]
                                }
                            ],
                        }
                    },
                ),
            ]

    monkeypatch.setattr(parsing, "DoclingLoader", FakeLoader)

    result = parsing.parse_pdf_structure(str(file_path))

    assert result["body"] == "Chunk A\n\nChunk B"
    assert result["sections"][0]["title"] == "3.2 AI 模型"
    assert result["sections"][0]["page"] == 3
    assert result["sections"][0]["bbox"] == {
        "left": 108.0,
        "top": 405.14,
        "right": 504.0,
        "bottom": 330.78,
        "origin": "BOTTOMLEFT",
    }
    assert result["3.2 AI 模型"] == "Chunk A"
    assert result["Intro > Sub"] == "Chunk B"


def test_parse_pdf_structure_fallbacks_to_plain_text(monkeypatch, tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text(" Example content ", encoding="utf-8")
    monkeypatch.setattr(parsing, "DoclingLoader", None)

    result = parsing.parse_pdf_structure(str(file_path))

    assert result["body"] == "Example content"
    assert result["sections"] == []
