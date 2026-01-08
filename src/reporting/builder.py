"""Builder to convert Rob2FinalOutput to ReportData structure."""

from datetime import datetime
from typing import Any

from schemas.internal.results import Rob2FinalOutput
from schemas.internal.locator import DomainId

from reporting.schemas import (
    CitationEntry,
    CitationsSection,
    CitationUse,
    DomainSection,
    EvidenceRef,
    OverallSection,
    QuestionAnswer,
    ReportData,
    ReportDataMetadata,
)
from reporting.utils import (
    get_answer_label,
    get_domain_name,
    get_overall_interpretation,
    get_risk_label,
)


class ReportDataBuilder:
    """Builds structured ReportData from Rob2FinalOutput."""

    def __init__(
        self,
        result: Rob2FinalOutput,
        *,
        report_title: str = "ROB2 Risk of Bias Assessment Report",
        source_pdf_name: str | None = None,
        table_markdown: str | None = None,
        validation_reports: dict[str, Any] | None = None,
        audit_reports: list[dict[str, Any]] | None = None,
        include_confidence: bool = True,
    ):
        self.result = result
        self.report_title = report_title
        self.source_pdf_name = source_pdf_name
        self.table_markdown = table_markdown
        self.validation_reports = validation_reports
        self.audit_reports = audit_reports
        self.include_confidence = include_confidence

    def build(self) -> ReportData:
        """Build the complete ReportData structure."""
        return ReportData(
            metadata=self._build_metadata(),
            overall=self._build_overall(),
            domains=self._build_domains(),
            citations=self._build_citations(),
            summary_table=self.table_markdown,
            validation_reports=self.validation_reports,
            audit_reports=self.audit_reports,
        )

    def _build_metadata(self) -> ReportDataMetadata:
        """Build metadata section."""
        return ReportDataMetadata(
            title=self.report_title,
            variant=self.result.variant,
            question_set_version=self.result.question_set_version,
            generated_at=datetime.now(),
            system_version=self._get_system_version(),
            source_pdf_name=self.source_pdf_name,
        )

    def _build_overall(self) -> OverallSection:
        """Build overall risk section."""
        overall = self.result.overall
        risk_value = overall.risk
        return OverallSection(
            risk=risk_value,
            risk_label=get_risk_label(risk_value),
            rationale=overall.rationale,
            interpretation=get_overall_interpretation(risk_value),
        )

    def _build_domains(self) -> list[DomainSection]:
        """Build domain sections."""
        domains = []
        for domain_result in self.result.domains:
            domain_id = domain_result.domain
            answers = [
                self._build_question_answer(ans, domain_id)
                for ans in domain_result.answers
            ]

            domain_section = DomainSection(
                domain_id=domain_id,
                domain_name=get_domain_name(domain_id),
                effect_type=domain_result.effect_type,
                risk=domain_result.risk,
                risk_label=get_risk_label(domain_result.risk),
                risk_rationale=domain_result.risk_rationale,
                answers=answers,
                missing_questions=domain_result.missing_questions,
                total_questions=len(answers) + len(domain_result.missing_questions),
                answered_questions=len(answers),
            )
            domains.append(domain_section)

        return domains

    def _build_question_answer(
        self, answer_result: Any, domain_id: DomainId
    ) -> QuestionAnswer:
        """Build a question answer entry."""
        evidence_refs = [
            EvidenceRef(
                paragraph_id=ref.paragraph_id,
                page=ref.page,
                title=ref.title,
                quote=ref.quote,
            )
            for ref in answer_result.evidence_refs
        ]

        return QuestionAnswer(
            question_id=answer_result.question_id,
            rob2_id=answer_result.rob2_id or "",
            question_text=answer_result.text or "",
            answer=answer_result.answer,
            answer_label=get_answer_label(answer_result.answer),
            rationale=answer_result.rationale,
            evidence_refs=evidence_refs,
            confidence=answer_result.confidence if self.include_confidence else None,
        )

    def _build_citations(self) -> CitationsSection:
        """Build citations section."""
        citation_entries = []
        citations_by_domain: dict[str, int] = {}

        for citation in self.result.citations:
            uses = [
                CitationUse(
                    domain_id=use.domain,
                    question_id=use.question_id,
                    rob2_id="",  # Not available in CitationUse
                )
                for use in citation.uses
            ]

            # Count citations by domain
            for use in citation.uses:
                domain_id = use.domain
                citations_by_domain[domain_id] = (
                    citations_by_domain.get(domain_id, 0) + 1
                )

            citation_entry = CitationEntry(
                paragraph_id=citation.paragraph_id,
                page=citation.page,
                title=citation.title,
                text=citation.text or "",
                uses=uses,
            )
            citation_entries.append(citation_entry)

        return CitationsSection(
            citations=citation_entries,
            total_citations=len(citation_entries),
            citations_by_domain=citations_by_domain,
        )

    def _get_system_version(self) -> str:
        """Get system version from package metadata."""
        try:
            from importlib.metadata import version

            return version("eagent")
        except Exception:
            return "unknown"
