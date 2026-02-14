"""Batch traffic-light plot renderer for ROB2 summaries."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

SUMMARY_FILE_NAME = "batch_summary.json"
DEFAULT_BATCH_PLOT_FILE = "batch_traffic_light.png"

_COLUMN_KEYS = ("overall", "D1", "D2", "D3", "D4", "D5")
_COLUMN_LABELS = {
    "overall": "Overall",
    "D1": "D1",
    "D2": "D2",
    "D3": "D3",
    "D4": "D4",
    "D5": "D5",
}
_RESULT_STATUSES = {"success", "skipped"}
_COLORS = {
    "low": "#2e7d32",
    "some_concerns": "#f9a825",
    "high": "#c62828",
    "not_applicable": "#9e9e9e",
}
_PLOT_FONT_SIZE = 14
_FONT_ENV_VAR = "ROB2_BATCH_PLOT_FONT_PATH"
_FONT_CANDIDATES = (
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
)


@dataclass(frozen=True)
class TrafficLightRow:
    label: str
    status: str
    risks: dict[str, str]


def load_batch_summary(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"summary 读取失败: {path} ({exc})") from exc

    if not isinstance(payload, dict):
        raise ValueError(f"summary 格式错误: {path}")
    if not isinstance(payload.get("items"), list):
        raise ValueError(f"summary items 缺失: {path}")
    return payload


def normalize_risk(value: Any) -> str:
    if not isinstance(value, str):
        return "not_applicable"
    token = value.strip().lower().replace("-", "_").replace(" ", "_")
    if token in {"low", "some_concerns", "high", "not_applicable"}:
        return token
    return "not_applicable"


def build_traffic_light_rows(
    summary: Mapping[str, Any],
    *,
    include_non_success: bool = False,
) -> list[TrafficLightRow]:
    items = summary.get("items")
    if not isinstance(items, list):
        raise ValueError("summary items 缺失")

    rows: list[TrafficLightRow] = []
    for index, raw_item in enumerate(items):
        if not isinstance(raw_item, Mapping):
            continue

        relative_path = str(raw_item.get("relative_path") or f"item_{index + 1}")
        label = Path(relative_path).with_suffix("").as_posix()
        status = str(raw_item.get("status") or "unknown").strip().lower()
        overall_raw = raw_item.get("overall_risk")

        if status in _RESULT_STATUSES and _has_risk_value(overall_raw):
            domain_risks = raw_item.get("domain_risks")
            if not isinstance(domain_risks, Mapping):
                domain_risks = {}

            risks = {
                "overall": normalize_risk(overall_raw),
                "D1": normalize_risk(domain_risks.get("D1")),
                "D2": normalize_risk(domain_risks.get("D2")),
                "D3": normalize_risk(domain_risks.get("D3")),
                "D4": normalize_risk(domain_risks.get("D4")),
                "D5": normalize_risk(domain_risks.get("D5")),
            }
            rows.append(TrafficLightRow(label=label, status=status, risks=risks))
            continue

        if include_non_success:
            rows.append(
                TrafficLightRow(
                    label=label,
                    status=status,
                    risks={key: "not_applicable" for key in _COLUMN_KEYS},
                )
            )

    return rows


def generate_batch_traffic_light_png(
    summary: Mapping[str, Any],
    output_path: Path,
    *,
    include_non_success: bool = False,
) -> int:
    rows = build_traffic_light_rows(summary, include_non_success=include_non_success)
    if not rows:
        raise ValueError("summary 中没有可绘制的条目")

    image = _draw_matrix(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return len(rows)


def _draw_matrix(rows: list[TrafficLightRow]) -> Image.Image:
    font: Any = _load_plot_font(_PLOT_FONT_SIZE)
    probe = Image.new("RGB", (1, 1), "white")
    probe_draw = ImageDraw.Draw(probe)

    label_width = max(_text_size(probe_draw, row.label, font)[0] for row in rows)
    label_col_width = min(max(label_width + 24, 220), 620)

    margin = 24
    title_height = 34
    header_height = 34
    row_height = 32
    cell_width = 84
    legend_height = 48
    dot_radius = 8

    width = margin * 2 + label_col_width + cell_width * len(_COLUMN_KEYS)
    height = margin * 2 + title_height + header_height + row_height * len(rows) + legend_height
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)

    title = "ROB2 Batch Traffic Light Plot"
    _draw_text(draw, (margin, margin), title, fill="#111111", font=font)

    grid_top = margin + title_height
    matrix_left = margin + label_col_width

    draw.rectangle((margin, grid_top, width - margin, height - margin), outline="#d8d8d8", width=1)

    for idx, key in enumerate(_COLUMN_KEYS):
        label = _COLUMN_LABELS[key]
        x = matrix_left + idx * cell_width + cell_width // 2
        y = grid_top + header_height // 2
        tw, th = _text_size(draw, label, font)
        _draw_text(draw, (x - tw // 2, y - th // 2), label, fill="#2c2c2c", font=font)

    draw.line((margin, grid_top + header_height, width - margin, grid_top + header_height), fill="#dddddd")

    for row_index, row in enumerate(rows):
        row_top = grid_top + header_height + row_index * row_height
        row_center = row_top + row_height // 2
        draw.line((margin, row_top + row_height, width - margin, row_top + row_height), fill="#eeeeee")

        clipped_label = _clip_text(draw, row.label, font, label_col_width - 12)
        tw, th = _text_size(draw, clipped_label, font)
        _draw_text(
            draw,
            (margin + 6, row_center - th // 2),
            clipped_label,
            fill="#1f1f1f",
            font=font,
        )

        for col_index, key in enumerate(_COLUMN_KEYS):
            cx = matrix_left + col_index * cell_width + cell_width // 2
            risk = row.risks.get(key, "not_applicable")
            color = _COLORS.get(risk, _COLORS["not_applicable"])
            draw.ellipse(
                (
                    cx - dot_radius,
                    row_center - dot_radius,
                    cx + dot_radius,
                    row_center + dot_radius,
                ),
                fill=color,
                outline="#5f5f5f",
                width=1,
            )

    legend_top = height - margin - legend_height + 14
    legend_items = [
        ("low", "Low"),
        ("some_concerns", "Some concerns"),
        ("high", "High"),
    ]
    cursor = margin + 4
    for key, text in legend_items:
        color = _COLORS[key]
        draw.ellipse((cursor, legend_top, cursor + 12, legend_top + 12), fill=color, outline="#5f5f5f", width=1)
        _draw_text(draw, (cursor + 18, legend_top - 1), text, fill="#2c2c2c", font=font)
        cursor += 120

    return image


def _has_risk_value(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: Any) -> tuple[int, int]:
    try:
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    except UnicodeEncodeError:
        fallback_font = ImageFont.load_default()
        fallback_text = _ascii_fallback_text(text)
        left, top, right, bottom = draw.textbbox((0, 0), fallback_text, font=fallback_font)
    return int(right - left), int(bottom - top)


def _clip_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_width: int,
) -> str:
    if _text_size(draw, text, font)[0] <= max_width:
        return text

    clipped = text
    while clipped and _text_size(draw, f"{clipped}...", font)[0] > max_width:
        clipped = clipped[:-1]
    return f"{clipped}..." if clipped else "..."


def _draw_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    *,
    fill: str,
    font: Any,
) -> None:
    try:
        draw.text(position, text, fill=fill, font=font)
    except UnicodeEncodeError:
        fallback_font = ImageFont.load_default()
        draw.text(position, _ascii_fallback_text(text), fill=fill, font=fallback_font)


def _load_plot_font(size: int) -> Any:
    env_path = os.getenv(_FONT_ENV_VAR, "").strip()
    if env_path:
        env_font = _load_truetype_font(Path(env_path), size)
        if env_font is not None:
            return env_font

    for candidate in _FONT_CANDIDATES:
        candidate_font = _load_truetype_font(Path(candidate), size)
        if candidate_font is not None:
            return candidate_font
    return ImageFont.load_default()


def _load_truetype_font(path: Path, size: int) -> Any | None:
    if not path.exists():
        return None
    try:
        return ImageFont.truetype(str(path), size=size)
    except Exception:
        return None


def _ascii_fallback_text(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


__all__ = [
    "DEFAULT_BATCH_PLOT_FILE",
    "SUMMARY_FILE_NAME",
    "TrafficLightRow",
    "build_traffic_light_rows",
    "generate_batch_traffic_light_png",
    "load_batch_summary",
    "normalize_risk",
]
