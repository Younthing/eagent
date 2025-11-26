def parse_document_structure(text: str) -> dict[str, str]:
    """Simulate document section parsing."""
    return {
        "abstract": text[:500] if len(text) > 500 else text,
        "full": text,
    }


def get_relevant_context(doc: dict[str, str], section_key: str) -> str:
    """Return requested section or full fallback."""
    return doc.get(section_key, doc.get("full", ""))
