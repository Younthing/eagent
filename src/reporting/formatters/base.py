"""Base formatter interface."""

from abc import ABC, abstractmethod
from pathlib import Path

from reporting.schemas import ReportData


class BaseFormatter(ABC):
    """Abstract base class for report formatters."""

    def __init__(self, template_dir: Path | None = None):
        """
        Initialize formatter.

        Args:
            template_dir: Directory containing templates for this formatter
        """
        self.template_dir = template_dir or self._get_default_template_dir()

    @abstractmethod
    def format(self, data: ReportData) -> str | bytes:
        """
        Format report data into the target format.

        Args:
            data: Structured report data

        Returns:
            Formatted content (string for text formats, bytes for binary)
        """
        pass

    def _get_default_template_dir(self) -> Path:
        """Get default template directory for this formatter."""
        # Default to templates/default in the reporting module
        from pathlib import Path

        module_dir = Path(__file__).parent.parent
        return module_dir / "templates" / "default"
