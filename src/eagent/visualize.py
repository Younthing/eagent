"""Gradio viewer for Docling paragraph backtrace."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import gradio as gr
import fitz  # PyMuPDF
from PIL import Image, ImageDraw

from pipelines.graphs.nodes.preprocess import parse_docling_pdf


def _span_label(span: Dict[str, Any]) -> str:
    paragraph_id = span.get("paragraph_id") or "unknown"
    title = span.get("title") or "body"
    page = span.get("page")
    page_label = f"p{page}" if isinstance(page, int) else "p?"
    return f"{paragraph_id} | {page_label} | {title}"


def _normalize_bbox(
    bbox: Dict[str, Any], page_height: float
) -> Optional[Tuple[float, float, float, float]]:
    left = bbox.get("left")
    top = bbox.get("top")
    right = bbox.get("right")
    bottom = bbox.get("bottom")
    if left is None or top is None or right is None or bottom is None:
        return None

    origin = (bbox.get("origin") or "").lower()
    if "bottom" in origin:
        top = page_height - top
        bottom = page_height - bottom

    x0, x1 = sorted([left, right])
    y0, y1 = sorted([top, bottom])
    return x0, y0, x1, y1


def _scale_bbox(
    bbox: Dict[str, Any],
    page_rect: fitz.Rect,
    pix_width: int,
    pix_height: int,
) -> Optional[Tuple[int, int, int, int]]:
    normalized = _normalize_bbox(bbox, page_rect.height)
    if normalized is None:
        return None
    x0, y0, x1, y1 = normalized
    if page_rect.width == 0 or page_rect.height == 0:
        return None
    scale_x = pix_width / page_rect.width
    scale_y = pix_height / page_rect.height
    return (
        int(x0 * scale_x),
        int(y0 * scale_y),
        int(x1 * scale_x),
        int(y1 * scale_y),
    )


def _scale_rect(
    rect: fitz.Rect,
    page_rect: fitz.Rect,
    pix_width: int,
    pix_height: int,
) -> Tuple[int, int, int, int]:
    scale_x = pix_width / page_rect.width
    scale_y = pix_height / page_rect.height
    return (
        int(rect.x0 * scale_x),
        int(rect.y0 * scale_y),
        int(rect.x1 * scale_x),
        int(rect.y1 * scale_y),
    )


def _draw_boxes(
    image: Image.Image,
    boxes: List[Tuple[int, int, int, int]],
    color: str,
    width: int,
) -> None:
    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.rectangle(box, outline=color, width=width)


def _build_table(spans: List[Dict[str, Any]]) -> List[List[Any]]:
    table: List[List[Any]] = []
    for span in spans:
        text = span.get("text") or ""
        preview = text.replace("\n", " ").strip()[:160]
        table.append(
            [
                span.get("paragraph_id"),
                span.get("title"),
                span.get("page"),
                preview,
            ]
        )
    return table


def _parse_pdf(file: Optional[Any]) -> Tuple[
    Dict[str, Any],
    gr.update,
    gr.update,
    Dict[str, Any],
    Optional[Image.Image],
    List[List[Any]],
    str,
]:
    if file is None:
        return {}, gr.update(), gr.update(), {}, None, [], ""

    if isinstance(file, (str, Path)):
        path = Path(file)
    else:
        path = Path(file.name)
    doc = parse_docling_pdf(path)
    data = doc.model_dump()
    spans = data.get("sections") or []
    docling_config = data.get("docling_config") or {}

    with fitz.open(path) as pdf:
        page_count = pdf.page_count

    page_value = 1
    dropdown_choices = [_span_label(span) for span in spans]
    dropdown_value = dropdown_choices[0] if dropdown_choices else None

    state = {
        "path": str(path),
        "spans": spans,
        "page_count": page_count,
        "docling_config": docling_config,
    }

    image, table, text = _render_view(state, page_value, dropdown_value, True)
    return (
        state,
        gr.update(minimum=1, maximum=max(page_count, 1), value=page_value, step=1),
        gr.update(choices=dropdown_choices, value=dropdown_value),
        docling_config,
        image,
        table,
        text,
    )


def _find_span_by_label(
    spans: List[Dict[str, Any]], label: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not label:
        return None
    for span in spans:
        if _span_label(span) == label:
            return span
    return None


def _render_view(
    state: Dict[str, Any],
    page_number: int,
    paragraph_label: Optional[str],
    show_all: bool,
) -> Tuple[Optional[Image.Image], List[List[Any]], str]:
    if not state:
        return None, [], ""

    path = state.get("path")
    spans = state.get("spans") or []
    if not path:
        return None, [], ""

    selected_span = _find_span_by_label(spans, paragraph_label)
    selected_text = selected_span.get("text") if selected_span else ""

    with fitz.open(path) as pdf:
        if page_number < 1 or page_number > pdf.page_count:
            return None, [], selected_text
        page = pdf.load_page(page_number - 1)
        zoom = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        page_rect = page.rect
        page_spans = [
            span for span in spans if span.get("page") == page_number
        ]
        table = _build_table(page_spans)

        doc_boxes = []
        fallback_boxes = []
        for span in page_spans:
            span_boxes = _collect_span_boxes_for_page(
                span,
                page_rect,
                pix.width,
                pix.height,
            )
            if span_boxes:
                doc_boxes.extend(span_boxes)
                continue
            fallback_boxes.extend(
                _search_text_boxes(
                    page,
                    span.get("text") or "",
                    page_rect,
                    pix.width,
                    pix.height,
                )
            )

        if show_all:
            if doc_boxes:
                _draw_boxes(image, doc_boxes, color="#00B3FF", width=2)
            if fallback_boxes:
                _draw_boxes(image, fallback_boxes, color="#FF9800", width=2)

        if selected_span and selected_span.get("page") == page_number:
            selected_boxes = _collect_span_boxes_for_page(
                selected_span,
                page_rect,
                pix.width,
                pix.height,
            )
            if selected_boxes:
                _draw_boxes(image, selected_boxes, color="#FF2D2D", width=3)
            else:
                fallback = _search_text_boxes(
                    page,
                    selected_span.get("text") or "",
                    page_rect,
                    pix.width,
                    pix.height,
                )
                if fallback:
                    _draw_boxes(image, fallback, color="#FF9800", width=3)

    return image, table, selected_text


def _collect_span_boxes_for_page(
    span: Dict[str, Any],
    page_rect: fitz.Rect,
    pix_width: int,
    pix_height: int,
) -> List[Tuple[int, int, int, int]]:
    boxes: List[Tuple[int, int, int, int]] = []
    span_boxes = span.get("bboxes") or []
    if span_boxes:
        for raw_box in span_boxes:
            scaled = _scale_bbox(raw_box, page_rect, pix_width, pix_height)
            if scaled is not None:
                boxes.append(scaled)
        return boxes
    bbox = span.get("bbox")
    if bbox:
        scaled = _scale_bbox(bbox, page_rect, pix_width, pix_height)
        if scaled is not None:
            boxes.append(scaled)
    return boxes


def _search_text_boxes(
    page: fitz.Page,
    text: str,
    page_rect: fitz.Rect,
    pix_width: int,
    pix_height: int,
) -> List[Tuple[int, int, int, int]]:
    candidates = _build_search_candidates(text)
    if not candidates:
        return []
    flags = getattr(fitz, "TEXT_DEHYPHENATE", 0)
    for query in candidates:
        rects = page.search_for(query, flags=flags)
        if rects:
            return [
                _scale_rect(rect, page_rect, pix_width, pix_height)
                for rect in rects
            ]
    return []


def _build_search_candidates(text: str) -> List[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) < 20:
        return []
    words = cleaned.split(" ")
    candidates: List[str] = []
    if len(cleaned) >= 120:
        candidates.append(cleaned[:120])
    if len(cleaned) >= 80:
        candidates.append(cleaned[:80])
    for count in (16, 12, 8):
        if len(words) >= count:
            candidates.append(" ".join(words[:count]))
    # de-dup while preserving order
    seen: set[str] = set()
    unique: List[str] = []
    for item in candidates:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _on_page_change(
    state: Dict[str, Any],
    page_number: int,
    paragraph_label: Optional[str],
    show_all: bool,
) -> Tuple[Optional[Image.Image], List[List[Any]], str]:
    return _render_view(state, page_number, paragraph_label, show_all)


def _on_paragraph_change(
    state: Dict[str, Any],
    page_number: int,
    paragraph_label: Optional[str],
    show_all: bool,
) -> Tuple[Optional[Image.Image], List[List[Any]], str, gr.update]:
    spans = state.get("spans") or []
    selected = _find_span_by_label(spans, paragraph_label)
    if selected and isinstance(selected.get("page"), int):
        page_number = selected["page"]
    image, table, text = _render_view(state, page_number, paragraph_label, show_all)
    return image, table, text, gr.update(value=page_number)


def build_app() -> gr.Blocks:
    with gr.Blocks(title="Docling Paragraph Backtrace") as demo:
        gr.Markdown("## Docling Paragraph Backtrace")

        state = gr.State({})
        with gr.Row():
            file_input = gr.File(
                label="PDF File",
                file_types=[".pdf"],
                type="filepath",
            )
            parse_button = gr.Button("Parse PDF", variant="primary")

        config_view = gr.JSON(label="Docling Config")

        with gr.Row():
            page_slider = gr.Slider(
                minimum=1,
                maximum=1,
                value=1,
                step=1,
                label="Page",
            )
            paragraph_dropdown = gr.Dropdown(
                choices=[],
                label="Paragraph",
                value=None,
            )
            show_all = gr.Checkbox(
                value=True,
                label="Show all boxes on page",
            )

        with gr.Row():
            image_output = gr.Image(
                label="Page Preview",
                type="pil",
            )
            table_output = gr.Dataframe(
                headers=["paragraph_id", "title", "page", "text_preview"],
                datatype=["str", "str", "number", "str"],
                label="Page Spans",
                interactive=False,
            )

        text_output = gr.Textbox(
            label="Selected Paragraph",
            lines=8,
            interactive=False,
        )

        parse_button.click(
            _parse_pdf,
            inputs=[file_input],
            outputs=[
                state,
                page_slider,
                paragraph_dropdown,
                config_view,
                image_output,
                table_output,
                text_output,
            ],
        )

        page_slider.change(
            _on_page_change,
            inputs=[state, page_slider, paragraph_dropdown, show_all],
            outputs=[image_output, table_output, text_output],
        )

        show_all.change(
            _on_page_change,
            inputs=[state, page_slider, paragraph_dropdown, show_all],
            outputs=[image_output, table_output, text_output],
        )

        paragraph_dropdown.change(
            _on_paragraph_change,
            inputs=[state, page_slider, paragraph_dropdown, show_all],
            outputs=[image_output, table_output, text_output, page_slider],
        )

    return demo


def main() -> None:
    app = build_app()
    app.launch()


if __name__ == "__main__":
    main()
