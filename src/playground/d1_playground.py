"""Gradio playground for D1 reasoning with evidence highlighting."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import fitz  # PyMuPDF
import gradio as gr
from PIL import Image, ImageDraw

from core.config import get_settings
from pipelines.graphs.nodes.domains.common import (
    build_domain_prompts,
    build_reasoning_config,
    run_domain_reasoning,
)
from pipelines.graphs.nodes.fusion import fusion_node
from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from pipelines.graphs.nodes.locators.retrieval_splade import (
    splade_retrieval_locator_node,
)
from pipelines.graphs.nodes.locators.rule_based import rule_based_locator_node
from pipelines.graphs.nodes.preprocess import parse_docling_pdf
from pipelines.graphs.nodes.validators.completeness import completeness_validator_node
from pipelines.graphs.nodes.validators.existence import existence_validator_node
from pipelines.graphs.nodes.validators.relevance import relevance_validator_node
from retrieval.engines.splade import DEFAULT_SPLADE_MODEL_ID
from rob2.question_bank import load_question_bank
from schemas.internal.rob2 import QuestionSet

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL_SPLADE = PROJECT_ROOT / "models" / "splade_distil_CoCodenser_large"


def _resolve_splade_model_id() -> str:
    settings = get_settings()
    model_id = str(settings.splade_model_id or "").strip()
    if model_id:
        return model_id
    if DEFAULT_LOCAL_SPLADE.exists():
        return str(DEFAULT_LOCAL_SPLADE)
    return DEFAULT_SPLADE_MODEL_ID


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


def _collect_span_boxes_for_page(
    span: Dict[str, Any],
    page_number: int,
    page_rect: fitz.Rect,
    pix_width: int,
    pix_height: int,
) -> List[Tuple[int, int, int, int]]:
    boxes: List[Tuple[int, int, int, int]] = []
    bboxes_by_page = span.get("bboxes_by_page") or {}
    page_key = str(page_number)
    if page_key in bboxes_by_page:
        for raw_box in bboxes_by_page[page_key]:
            scaled = _scale_bbox(raw_box, page_rect, pix_width, pix_height)
            if scaled is not None:
                boxes.append(scaled)
        return boxes

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


def _build_search_candidates(text: str) -> List[str]:
    cleaned = " ".join(text.split()).strip()
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
    seen: set[str] = set()
    unique: List[str] = []
    for item in candidates:
        item = item.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


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
                _scale_rect(rect, page_rect, pix_width, pix_height) for rect in rects
            ]
    return []


def _render_page(
    state: Dict[str, Any],
    page_number: int,
    paragraph_ids: Sequence[str],
) -> Optional[Image.Image]:
    path = state.get("path")
    spans = state.get("spans") or []
    if not path:
        return None

    highlight = {str(pid) for pid in paragraph_ids if pid}

    with fitz.open(path) as pdf:
        if page_number < 1 or page_number > pdf.page_count:
            return None
        page = pdf.load_page(page_number - 1)
        zoom = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        page_rect = page.rect

        boxes: List[Tuple[int, int, int, int]] = []
        for span in spans:
            if str(span.get("paragraph_id")) not in highlight:
                continue
            if str(span.get("page")) != str(page_number):
                continue
            span_boxes = _collect_span_boxes_for_page(
                span, page_number, page_rect, pix.width, pix.height
            )
            if span_boxes:
                boxes.extend(span_boxes)
            else:
                boxes.extend(
                    _search_text_boxes(
                        page, span.get("text") or "", page_rect, pix.width, pix.height
                    )
                )

        if boxes:
            draw = ImageDraw.Draw(image)
            for box in boxes:
                draw.rectangle(box, outline="#FF2D2D", width=3)
        return image


def _extract_question_ids(question_set: QuestionSet) -> List[str]:
    return [
        question.question_id
        for question in sorted(
            (q for q in question_set.questions if q.domain == "D1"),
            key=lambda item: item.order,
        )
    ]


def _simplify_candidates(
    validated_candidates: Mapping[str, Sequence[dict]], question_ids: Sequence[str]
) -> Dict[str, List[dict]]:
    simplified: Dict[str, List[dict]] = {}
    for question_id in question_ids:
        raw_list = validated_candidates.get(question_id) or []
        simplified[question_id] = [
            {
                "paragraph_id": item.get("paragraph_id"),
                "title": item.get("title"),
                "page": item.get("page"),
                "text": item.get("text"),
            }
            for item in raw_list
            if isinstance(item, dict)
        ]
    return simplified


def _expand_candidates(payload: Mapping[str, Sequence[dict]]) -> Dict[str, List[dict]]:
    expanded: Dict[str, List[dict]] = {}
    for question_id, items in payload.items():
        expanded_list: List[dict] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            paragraph_id = str(item.get("paragraph_id") or "").strip()
            if not paragraph_id:
                continue
            expanded_list.append(
                {
                    "question_id": question_id,
                    "paragraph_id": paragraph_id,
                    "title": str(item.get("title") or ""),
                    "page": item.get("page"),
                    "text": str(item.get("text") or ""),
                    "fusion_score": float(item.get("fusion_score") or 0.0),
                    "fusion_rank": int(item.get("fusion_rank") or index),
                    "support_count": int(item.get("support_count") or 1),
                    "supports": item.get("supports")
                    or [{"engine": "manual", "rank": 1, "score": 0.0}],
                    "relevance": item.get("relevance"),
                    "existence": item.get("existence"),
                }
            )
        expanded[question_id] = expanded_list
    return expanded


def _parse_evidence_json(text: str) -> Dict[str, List[dict]]:
    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Evidence JSON must be an object keyed by question_id.")
    normalized: Dict[str, List[dict]] = {}
    for key, items in payload.items():
        if not isinstance(key, str):
            continue
        if not isinstance(items, list):
            raise ValueError(f"Evidence for {key} must be a list.")
        normalized[key] = [item for item in items if isinstance(item, dict)]
    return normalized


def _pipeline_run(
    file_path: str,
    *,
    top_k: int,
    per_query_top_n: int,
    use_structure: bool,
) -> Dict[str, Any]:
    settings = get_settings()
    doc = parse_docling_pdf(file_path)
    question_set = load_question_bank()
    base_state = {
        "doc_structure": doc.model_dump(),
        "question_set": question_set.model_dump(),
        "top_k": top_k,
        "per_query_top_n": per_query_top_n,
        "rrf_k": 60,
        "query_planner": "deterministic",
        "reranker": "none",
        "use_structure": bool(use_structure),
        "splade_model_id": _resolve_splade_model_id(),
        "splade_device": settings.splade_device,
        "splade_hf_token": settings.splade_hf_token,
        "splade_query_max_length": settings.splade_query_max_length,
        "splade_doc_max_length": settings.splade_doc_max_length,
        "splade_batch_size": settings.splade_batch_size,
        "fusion_top_k": top_k,
        "fusion_rrf_k": 60,
        "relevance_mode": "none",
        "relevance_min_confidence": 0.6,
        "relevance_require_quote": False,
        "completeness_enforce": False,
        "completeness_require_relevance": False,
    }

    rule_based = rule_based_locator_node(base_state)
    bm25 = bm25_retrieval_locator_node(base_state)
    splade = splade_retrieval_locator_node(base_state)
    fused_state = {**base_state, **rule_based, **bm25, **splade}
    fusion = fusion_node(fused_state)

    relevance_state = {**fused_state, **fusion}
    relevance = relevance_validator_node(relevance_state)

    existence_state = {**relevance_state, **relevance}
    existence = existence_validator_node(existence_state)

    completeness_state = {**existence_state, **existence}
    completeness = completeness_validator_node(completeness_state)

    return {
        "doc": doc,
        "question_set": question_set,
        "validated_candidates": completeness.get("validated_candidates") or {},
    }


def _load_pdf_and_evidence(
    file_input: Optional[str],
    top_k: int,
    per_query_top_n: int,
    use_structure: bool,
) -> Tuple[
    Dict[str, Any],
    Any,
    Any,
    str,
    str,
    str,
    Optional[Image.Image],
    str,
]:
    if not file_input:
        return {}, gr.update(), gr.update(), "{}", "", "", None, "No PDF selected."

    path = Path(file_input)
    if not path.exists():
        return {}, gr.update(), gr.update(), "{}", "", "", None, "PDF not found."

    result = _pipeline_run(
        str(path),
        top_k=top_k,
        per_query_top_n=per_query_top_n,
        use_structure=use_structure,
    )
    doc = result["doc"]
    question_set = result["question_set"]
    validated_candidates = result["validated_candidates"]

    spans = doc.model_dump().get("sections") or []
    with fitz.open(path) as pdf:
        page_count = pdf.page_count

    question_ids = _extract_question_ids(question_set)
    simplified = _simplify_candidates(validated_candidates, question_ids)
    evidence_text = json.dumps(simplified, ensure_ascii=True, indent=2)
    expanded = _expand_candidates(simplified)
    system_prompt, user_prompt = build_domain_prompts(
        domain="D1",
        question_set=question_set,
        validated_candidates=expanded,
        evidence_top_k=top_k,
    )

    state = {
        "path": str(path),
        "spans": spans,
        "page_count": page_count,
        "question_set": question_set,
        "validated_candidates": expanded,
        "question_ids": question_ids,
    }

    selected_question = question_ids[0] if question_ids else ""
    highlight_ids = [
        str(item.get("paragraph_id"))
        for item in simplified.get(selected_question, [])
        if isinstance(item, dict) and item.get("paragraph_id")
    ]
    image = _render_page(state, 1, highlight_ids)

    return (
        state,
        gr.update(minimum=1, maximum=max(page_count, 1), value=1, step=1),
        gr.update(choices=question_ids, value=selected_question),
        evidence_text,
        system_prompt,
        user_prompt,
        image,
        "Pipeline completed.",
    )


def _update_highlight(
    state: Dict[str, Any],
    evidence_text: str,
    question_id: Optional[str],
    page_number: int,
) -> Tuple[Optional[Image.Image], str]:
    if not state:
        return None, "No document loaded."
    try:
        parsed = _parse_evidence_json(evidence_text)
    except ValueError as exc:
        return None, str(exc)
    items = parsed.get(question_id or "") or []
    paragraph_ids = [
        str(item.get("paragraph_id"))
        for item in items
        if isinstance(item, dict) and item.get("paragraph_id")
    ]
    image = _render_page(state, page_number, paragraph_ids)
    return image, "Evidence updated."


def _refresh_prompts(
    state: Dict[str, Any],
    evidence_text: str,
    top_k: int,
) -> Tuple[str, str, str]:
    if not state:
        return "", "", "No document loaded."
    try:
        parsed = _parse_evidence_json(evidence_text)
    except ValueError as exc:
        return "", "", str(exc)

    expanded = _expand_candidates(parsed)
    question_set = state.get("question_set")
    if question_set is None:
        return "", "", "Question set missing."

    system_prompt, user_prompt = build_domain_prompts(
        domain="D1",
        question_set=question_set,
        validated_candidates=expanded,
        evidence_top_k=top_k,
    )
    state["validated_candidates"] = expanded
    return system_prompt, user_prompt, "Prompts refreshed."


def _run_d1(
    state: Dict[str, Any],
    evidence_text: str,
    top_k: int,
    system_prompt: str,
    mode: str,
) -> Tuple[str, str]:
    if not state:
        return "{}", "No document loaded."
    try:
        parsed = _parse_evidence_json(evidence_text)
    except ValueError as exc:
        return "{}", str(exc)

    expanded = _expand_candidates(parsed)
    question_set = state.get("question_set")
    if question_set is None:
        return "{}", "Question set missing."

    settings = get_settings()
    model_id = str(settings.d1_model or "").strip()
    if not model_id:
        return "{}", "Missing D1 model (set D1_MODEL)."

    config = build_reasoning_config(
        model_id=model_id,
        model_provider=settings.d1_model_provider,
        temperature=float(settings.d1_temperature),
        timeout=float(settings.d1_timeout) if settings.d1_timeout is not None else None,
        max_tokens=int(settings.d1_max_tokens)
        if settings.d1_max_tokens is not None
        else None,
        max_retries=int(settings.d1_max_retries),
    )

    system_prompt_value = system_prompt if mode == "custom" else None
    user_prompt = None
    if mode == "custom" and system_prompt:
        _, user_prompt = build_domain_prompts(
            domain="D1",
            question_set=question_set,
            validated_candidates=expanded,
            evidence_top_k=top_k,
        )

    decision = run_domain_reasoning(
        domain="D1",
        question_set=question_set,
        validated_candidates=expanded,
        llm=None,
        llm_config=config,
        evidence_top_k=top_k,
        system_prompt=system_prompt_value,
        user_prompt=user_prompt,
    )
    return json.dumps(
        decision.model_dump(), ensure_ascii=True, indent=2
    ), "D1 run complete."


def _run_d1_default(
    state: Dict[str, Any],
    evidence_text: str,
    top_k: int,
    system_prompt: str,
) -> Tuple[str, str]:
    return _run_d1(state, evidence_text, top_k, system_prompt, "default")


def _run_d1_custom(
    state: Dict[str, Any],
    evidence_text: str,
    top_k: int,
    system_prompt: str,
) -> Tuple[str, str]:
    return _run_d1(state, evidence_text, top_k, system_prompt, "custom")


def build_app() -> gr.Blocks:
    with gr.Blocks(title="D1 调试台") as demo:
        gr.Markdown("## D1 调试台（PDF → 证据 → 提示词 → 结论）")

        state = gr.State({})

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 定位与证据")
                gr.Markdown("**步骤 1：上传 PDF 并运行定位**")
                with gr.Row():
                    file_input = gr.File(
                        label="PDF 文件",
                        file_types=[".pdf"],
                        type="filepath",
                    )
                    run_pipeline = gr.Button("运行 D1 流水线", variant="primary")
                with gr.Row():
                    top_k = gr.Slider(1, 10, value=5, step=1, label="证据 Top-k")
                    per_query_top_n = gr.Slider(
                        10, 200, value=50, step=10, label="每条查询 Top-N"
                    )
                use_structure = gr.Checkbox(value=True, label="结构化检索")
                gr.Markdown("**步骤 2：编辑证据并应用高亮**")
                with gr.Row():
                    page_slider = gr.Slider(
                        minimum=1, maximum=1, value=1, step=1, label="页码"
                    )
                    question_dropdown = gr.Dropdown(choices=[], label="D1 问题")
                image_output = gr.Image(label="证据高亮", type="pil")
                evidence_text = gr.Textbox(label="D1 证据（可编辑 JSON）", lines=18)
                apply_evidence = gr.Button("应用证据")
                status = gr.Textbox(label="状态", interactive=False)
                with gr.Accordion("定位侧说明（可展开）", open=False):
                    gr.Markdown(
                        "\n".join(
                            [
                                "- `运行 D1 流水线`：解析 PDF 并生成初始证据。",
                                "- `应用证据`：根据当前证据 JSON 刷新高亮。",
                                "- 切换 `页码` 或 `D1 问题` 会更新高亮。",
                            ]
                        )
                    )

            with gr.Column(scale=1):
                gr.Markdown("### 提示词与推理")
                gr.Markdown("**步骤 3：刷新提示词并对比推理**")
                system_prompt = gr.Textbox(label="D1 系统提示词（可编辑）", lines=10)
                user_prompt = gr.Textbox(
                    label="D1 用户提示词（只读）", lines=10, interactive=False
                )
                with gr.Row():
                    refresh_prompts = gr.Button("刷新提示词")
                    run_default = gr.Button("运行 D1（默认提示词）")
                    run_custom = gr.Button("运行 D1（自定义提示词）")
                output_default = gr.Textbox(label="D1 输出（默认提示词）", lines=18)
                output_custom = gr.Textbox(label="D1 输出（自定义提示词）", lines=18)
                with gr.Accordion("提示词侧说明（可展开）", open=False):
                    gr.Markdown(
                        "\n".join(
                            [
                                "- `刷新提示词`：基于当前证据 JSON 重建提示词。",
                                "- `运行 D1（默认提示词）`：使用自动生成提示词。",
                                "- `运行 D1（自定义提示词）`：使用你编辑后的提示词。",
                                "- 对比左右输出以评估提示词调整效果。",
                            ]
                        )
                    )

        run_pipeline.click(
            _load_pdf_and_evidence,
            inputs=[file_input, top_k, per_query_top_n, use_structure],
            outputs=[
                state,
                page_slider,
                question_dropdown,
                evidence_text,
                system_prompt,
                user_prompt,
                image_output,
                status,
            ],
        )

        apply_evidence.click(
            _update_highlight,
            inputs=[state, evidence_text, question_dropdown, page_slider],
            outputs=[image_output, status],
        )

        refresh_prompts.click(
            _refresh_prompts,
            inputs=[state, evidence_text, top_k],
            outputs=[system_prompt, user_prompt, status],
        )

        page_slider.change(
            _update_highlight,
            inputs=[state, evidence_text, question_dropdown, page_slider],
            outputs=[image_output, status],
        )

        question_dropdown.change(
            _update_highlight,
            inputs=[state, evidence_text, question_dropdown, page_slider],
            outputs=[image_output, status],
        )

        run_default.click(
            _run_d1_default,
            inputs=[state, evidence_text, top_k, system_prompt],
            outputs=[output_default, status],
        )

        run_custom.click(
            _run_d1_custom,
            inputs=[state, evidence_text, top_k, system_prompt],
            outputs=[output_custom, status],
        )

    return demo


def main() -> None:
    app = build_app()
    app.launch()


if __name__ == "__main__":
    main()
