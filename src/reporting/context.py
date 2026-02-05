"""Shared context and labels for ROB2 reports."""

from __future__ import annotations

import datetime
from typing import Any

from schemas.responses import Rob2RunResult


RISK_LABELS = {
    "low": "低风险",
    "some_concerns": "有些疑虑",
    "high": "高风险",
    "not_applicable": "不适用",
}

DOMAIN_NAMES = {
    "D1": "D1: 随机化过程产生的偏差",
    "D2": "D2: 偏离既定干预措施产生的偏差",
    "D3": "D3: 缺失结果数据产生的偏差",
    "D4": "D4: 结果测量产生的偏差",
    "D5": "D5: 结果报告选择产生的偏差",
}


def build_report_context(
    result: Rob2RunResult,
    *,
    pdf_name: str,
    generated_at: datetime.datetime | None = None,
) -> dict[str, Any]:
    timestamp = generated_at or datetime.datetime.now()
    return {
        "data": result.result,
        "pdf_name": pdf_name,
        "generated_at": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "risk_labels": RISK_LABELS,
        "domain_names": DOMAIN_NAMES,
    }


__all__ = ["DOMAIN_NAMES", "RISK_LABELS", "build_report_context"]
