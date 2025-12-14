"""
ResponseParser - Parse JSON from LLM responses with truncation recovery.

Extracted from UnifiedChronologyEngine._parse_llm_response and _recover_truncated_json.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResponseParser:
    """Parse JSON responses from LLM with robust error recovery."""

    def parse(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse LLM response into list of entry dicts.

        Args:
            response: Raw LLM response text

        Returns:
            List of parsed entry dicts (empty on failure)
        """
        if not response or not response.strip():
            return []

        json_text = self._extract_json(response)

        try:
            parsed = json.loads(json_text)
            return self._normalize(parsed)
        except json.JSONDecodeError:
            recovered = self._recover_truncated(json_text)
            return self._normalize(recovered) if recovered else []

    def _extract_json(self, response: str) -> str:
        """Extract JSON from markdown code blocks."""
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            return response[start:end if end != -1 else None].strip()
        if "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            return response[start:end if end != -1 else None].strip()
        return response.strip()

    def _normalize(self, parsed: Any) -> List[Dict]:
        """Normalize to list of dicts."""
        if isinstance(parsed, list):
            return [e for e in parsed if isinstance(e, dict)]
        if isinstance(parsed, dict):
            for key in ("entries", "chronological_medical_entries"):
                if key in parsed:
                    return self._normalize(parsed[key])
            return [parsed]
        return []

    def _recover_truncated(self, json_text: str) -> Optional[List[Dict]]:
        """
        Recover valid entries from truncated/malformed JSON.

        Uses 3 strategies from UnifiedChronologyEngine:
        1. Find complete objects via regex
        2. Fix common truncation issues (bracket balancing)
        3. Line-by-line object extraction
        """
        object_pattern = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)

        # Strategy 1: Find complete objects
        objects = object_pattern.findall(json_text)
        if objects:
            valid = []
            for obj_str in objects:
                try:
                    entry = json.loads(obj_str)
                    if isinstance(entry, dict) and entry.get("date"):
                        valid.append(entry)
                except json.JSONDecodeError:
                    continue
            if valid:
                logger.info(f"Recovered {len(valid)} entries from truncated JSON")
                return valid

        # Strategy 2: Fix common truncation issues
        fixed = json_text.rstrip()
        fixed = re.sub(r',\s*$', '', fixed)  # Remove trailing comma

        # Count unbalanced brackets and close them
        open_brackets = fixed.count('[') - fixed.count(']')
        open_braces = fixed.count('{') - fixed.count('}')
        open_quotes = fixed.count('"') % 2

        if open_quotes:
            fixed += '"'

        for _ in range(open_braces):
            if not fixed.rstrip().endswith(('"', '}', ']', 'null', 'true', 'false') + tuple('0123456789')):
                fixed += '""'
            fixed += '}'

        for _ in range(open_brackets):
            fixed += ']'

        try:
            result = json.loads(fixed)
            if isinstance(result, list):
                logger.info(f"Fixed truncated JSON, recovered {len(result)} entries")
                return result
            elif isinstance(result, dict) and result.get("date"):
                return [result]
        except json.JSONDecodeError:
            pass

        # Strategy 3: Line-by-line object extraction
        lines = json_text.split('\n')
        buffer = ""
        valid = []

        for line in lines:
            buffer += line
            if '{' in buffer and '}' in buffer:
                for match in object_pattern.finditer(buffer):
                    try:
                        entry = json.loads(match.group())
                        if isinstance(entry, dict) and entry.get("date"):
                            valid.append(entry)
                    except json.JSONDecodeError:
                        continue
                buffer = ""

        if valid:
            logger.info(f"Line-by-line recovery found {len(valid)} entries")
            return valid

        logger.warning("Could not recover any valid entries from malformed JSON")
        return None
