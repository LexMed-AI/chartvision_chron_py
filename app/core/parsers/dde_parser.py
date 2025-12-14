"""
DDE Parser - Haiku-powered Section A extraction with vision fallback.

Parses DDE (Disability Determination Explanation) documents using LLM.
Uses port injection for LLM and PDF operations.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.core.ports.llm import LLMPort
from app.core.ports.pdf import PDFPort

logger = logging.getLogger(__name__)


class DDEParser:
    """
    Parse DDE (Disability Determination Explanation) documents using LLM.

    Uses dependency injection for LLM and PDF operations.
    """

    def __init__(self, llm: LLMPort, pdf: PDFPort):
        """
        Initialize parser with injected dependencies.

        Args:
            llm: LLM port implementation (e.g., BedrockAdapter)
            pdf: PDF port implementation (e.g., PyMuPDFAdapter)
        """
        self.version = "4.0.0"
        self._llm = llm
        self._pdf = pdf
        self.template = self._load_template()

    def _load_template(self) -> Dict[str, Any]:
        """Load extraction template from YAML."""
        # Try multiple paths for template
        paths = [
            Path(__file__).parent.parent.parent.parent / "templates" / "dde_assessment.yaml",
            Path(__file__).parent.parent.parent / "config" / "prompts" / "parsing" / "dde_parsing.yaml",
        ]

        for path in paths:
            if path.exists():
                with open(path) as f:
                    return yaml.safe_load(f)

        logger.warning("DDE template not found, using default")
        return {"user_prompt": "Extract DDE fields from:\n{medical_content}"}

    async def parse(
        self,
        pdf_path: str,
        page_start: int = 1,
        page_end: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Parse DDE document with vision fallback for scanned pages.

        Args:
            pdf_path: Path to PDF file
            page_start: Starting page (1-indexed)
            page_end: Ending page (None = all)

        Returns:
            Dict with fields, confidence, extraction_mode, errors
        """
        try:
            # Get page count if end not specified
            if page_end is None:
                page_end = self._pdf.get_page_count(pdf_path)

            # Get content with scanned page detection
            pages_content = self._pdf.get_pages_content(pdf_path, page_start, page_end)

            if pages_content.get("has_scanned"):
                return await self._parse_with_vision(pdf_path, page_start, page_end, pages_content)

            return await self._parse_text(pages_content)

        except Exception as e:
            logger.error(f"DDE parsing failed: {e}")
            return {
                "fields": {},
                "confidence": 0.0,
                "extraction_mode": "error",
                "errors": [str(e)],
            }

    async def _parse_text(self, pages_content: Dict[str, Any]) -> Dict[str, Any]:
        """Parse using text extraction."""
        text_pages = pages_content.get("text_pages", [])
        # PageContent is a dataclass, access attributes directly
        text = "\n".join(p.content for p in text_pages if p.content)

        if not text.strip():
            return {
                "fields": {},
                "confidence": 0.0,
                "extraction_mode": "text",
                "errors": ["No text extracted"],
            }

        try:
            fields = await self._extract_with_llm(text)
            confidence = self._calculate_confidence(fields)

            return {
                "fields": fields,
                "confidence": confidence,
                "extraction_mode": "text",
                "pages_processed": len(text_pages),
                "errors": [],
            }
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {
                "fields": {},
                "confidence": 0.0,
                "extraction_mode": "text",
                "errors": [str(e)],
            }

    async def _parse_with_vision(
        self,
        pdf_path: str,
        page_start: int,
        page_end: int,
        pages_content: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse using vision extraction for scanned pages."""
        image_pages = pages_content.get("image_pages", [])

        if not image_pages:
            # Fall back to text if no images
            return await self._parse_text(pages_content)

        # Render pages as images (PageContent is a dataclass)
        images = []
        for page_info in image_pages[:10]:  # Limit to 10 pages
            page_num = page_info.page_num if hasattr(page_info, 'page_num') else page_start
            try:
                img_bytes = self._pdf.render_page_image(pdf_path, page_num, dpi=150)
                images.append(img_bytes)
            except Exception as e:
                logger.warning(f"Failed to render page {page_num}: {e}")

        if not images:
            return await self._parse_text(pages_content)

        try:
            logger.info(f"Using vision extraction for {len(images)} scanned pages")
            fields = await self._extract_with_vision(images)
            confidence = self._calculate_confidence(fields)

            return {
                "fields": fields,
                "confidence": confidence,
                "extraction_mode": "vision",
                "pages_processed": len(images),
                "errors": [],
            }
        except Exception as e:
            logger.error(f"Vision extraction failed: {e}")
            return {
                "fields": {},
                "confidence": 0.0,
                "extraction_mode": "vision",
                "pages_processed": 0,
                "errors": [str(e)],
            }

    async def _extract_with_llm(self, text: str) -> Dict[str, Any]:
        """Extract DDE fields from text using LLM."""
        system = self.template.get(
            "system_prompt_text",
            "Extract DDE data from text. Return valid JSON."
        )

        prompt = self.template.get("user_prompt", "Extract DDE fields from:\n{medical_content}")
        prompt = prompt.replace("{medical_content}", text[:15000])

        response = await self._llm.generate(
            prompt=prompt,
            model="haiku",
            max_tokens=4000,
            temperature=0.05,
            system=system,
        )

        return self._parse_json(response)

    async def _extract_with_vision(self, images: List[bytes]) -> Dict[str, Any]:
        """Extract DDE fields from images using LLM vision."""
        system = self.template.get(
            "system_prompt_vision",
            "Extract DDE data from document images. Return valid JSON."
        )

        prompt = self.template.get(
            "user_prompt",
            "Extract all DDE data from these document images. Return valid JSON only:"
        )

        response = await self._llm.generate_with_vision(
            prompt=prompt,
            images=images,
            model="haiku",
            max_tokens=4000,
            temperature=0.05,
            system=system,
        )

        return self._parse_json(response)

    def _parse_json(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response with robust extraction."""
        if not response:
            logger.warning("Empty LLM response")
            return {}

        original = response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end == -1:
                    response = response[start:].strip()
                else:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end == -1:
                    response = response[start:].strip()
                else:
                    response = response[start:end].strip()

            # Try direct parse
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass

            # Try to find JSON object
            first_brace = response.find("{")
            last_brace = response.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                json_str = response[first_brace:last_brace + 1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass

            # Try to recover truncated JSON
            if first_brace != -1:
                truncated_json = response[first_brace:]
                open_braces = truncated_json.count("{") - truncated_json.count("}")
                open_brackets = truncated_json.count("[") - truncated_json.count("]")

                for _ in range(max(open_braces, open_brackets) + 2):
                    fixed = truncated_json.rstrip().rstrip(",").rstrip(":")
                    fixed += "]" * open_brackets + "}" * open_braces
                    try:
                        result = json.loads(fixed)
                        logger.info("Recovered DDE data from truncated JSON")
                        return result
                    except json.JSONDecodeError:
                        last_comma = truncated_json.rfind(",")
                        if last_comma > 0:
                            truncated_json = truncated_json[:last_comma]
                            open_braces = truncated_json.count("{") - truncated_json.count("}")
                            open_brackets = truncated_json.count("[") - truncated_json.count("]")
                        else:
                            break

            logger.warning(f"Failed to parse JSON. First 500 chars: {original[:500]}")
            return {}

        except Exception as e:
            logger.error(f"JSON parse error: {e}")
            return {}

    def _calculate_confidence(self, fields: Dict[str, Any]) -> float:
        """Calculate confidence based on key fields found."""
        key_fields = [
            "claimant_name", "date_of_birth", "claim_type",
            "alleged_onset_date", "protective_filing_date"
        ]

        case_metadata = fields.get("case_metadata", {})

        found = 0
        for f in key_fields:
            if fields.get(f) or case_metadata.get(f):
                found += 1

        return found / len(key_fields) if key_fields else 0.0


def create_dde_parser() -> DDEParser:
    """
    Factory function to create DDEParser with default adapters.

    Returns:
        Configured DDEParser instance
    """
    from app.adapters.llm import BedrockAdapter
    from app.adapters.pdf import PyMuPDFAdapter

    return DDEParser(llm=BedrockAdapter(), pdf=PyMuPDFAdapter())
