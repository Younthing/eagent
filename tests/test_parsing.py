from eagent.utils.parsing import parse_pdf_structure


def test_parse_pdf_structure_reads_file(tmp_path):
    file_path = tmp_path / "sample.txt"
    file_path.write_text(" Example content ", encoding="utf-8")

    result = parse_pdf_structure(str(file_path))

    assert result["body"] == "Example content"


def test_parse_pdf_structure_accepts_raw_string():
    raw_text = "Inline content without file"

    result = parse_pdf_structure(raw_text)

    assert result["body"] == raw_text
