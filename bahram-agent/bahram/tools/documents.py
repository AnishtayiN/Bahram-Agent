"""Document extraction tool for Bahram Agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DocumentTool:
    """Extract content from documents."""

    def __init__(self) -> None:
        self._max_size: int = 10 * 1024 * 1024  # 10MB

    async def extract(
        self,
        file_path: str,
        format: str = "text",
    ) -> dict[str, Any]:
        """Extract content from a document."""
        path = Path(file_path)

        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        if path.stat().st_size > self._max_size:
            return {"error": "File too large"}

        suffix = path.suffix.lower()

        try:
            if suffix == ".pdf":
                return await self._extract_pdf(path)
            elif suffix in (".doc", ".docx"):
                return await self._extract_docx(path)
            elif suffix == ".txt":
                return {"content": path.read_text(), "format": "text"}
            elif suffix == ".md":
                return {"content": path.read_text(), "format": "markdown"}
            elif suffix == ".json":
                import json
                return {"content": json.loads(path.read_text()), "format": "json"}
            elif suffix in (".yaml", ".yml"):
                try:
                    import yaml
                    return {"content": yaml.safe_load(path.read_text()), "format": "yaml"}
                except ImportError:
                    return {"content": path.read_text(), "format": "text"}
            else:
                return {"content": path.read_text(errors="replace"), "format": "text"}

        except Exception as e:
            return {"error": str(e)}

    async def _extract_pdf(self, path: Path) -> dict[str, Any]:
        """Extract from PDF."""
        try:
            import PyPDF2

            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"

                return {
                    "content": text,
                    "format": "text",
                    "pages": len(reader.pages),
                }
        except ImportError:
            return {"error": "PyPDF2 not installed. Run: pip install PyPDF2"}

    async def _extract_docx(self, path: Path) -> dict[str, Any]:
        """Extract from DOCX."""
        try:
            from docx import Document

            doc = Document(str(path))
            text = "\n".join([para.text for para in doc.paragraphs])

            return {
                "content": text,
                "format": "text",
                "paragraphs": len(doc.paragraphs),
            }
        except ImportError:
            return {"error": "python-docx not installed. Run: pip install python-docx"}

    def set_max_size(self, max_size: int) -> None:
        """Set max file size."""
        self._max_size = max_size
