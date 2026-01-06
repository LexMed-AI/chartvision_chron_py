"""
CitationMatcher - Match extracted entries to source pages.

Uses search terms from extracted entries (dates, providers, facilities)
to find the most likely source page(s) in the exhibit text.

Usage:
    from app.core.extraction.citation_matcher import CitationMatcher
    from app.core.extraction.pdf_exhibit_extractor import PageText

    pages = [PageText(absolute_page=100, relative_page=1, exhibit_id="1F", text="...")]
    matcher = CitationMatcher(pages, exhibit_context)

    result = matcher.match(entry)
    # result.citation contains the matched Citation
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.core.models.citation import Citation
from app.core.extraction.pdf_exhibit_extractor import PageText


@dataclass
class SearchTerm:
    """A term to search for when matching entries to pages."""

    value: str
    weight: float = 1.0
    fuzzy: bool = False


@dataclass
class MatchResult:
    """Result of matching an entry to source page(s)."""

    citation: Citation
    match_score: float
    matched_terms: List[str] = field(default_factory=list)
    match_method: str = "search"  # "search" or "fallback"


class CitationMatcher:
    """
    Match extracted chronology entries to their source pages.

    Uses weighted search terms from entry fields to score pages
    and select the best match.
    """

    # Terms to skip when extracting search values
    SKIP_TERMS = {"not specified", "unknown", "n/a", "none", "unspecified", ""}

    def __init__(
        self,
        pages: List[PageText],
        exhibit_context: Dict[str, Any],
        match_threshold: float = 3.0,
    ):
        """
        Initialize matcher with page content.

        Args:
            pages: List of PageText objects with page content
            exhibit_context: Exhibit metadata (exhibit_id, page_range, etc.)
            match_threshold: Minimum score to consider a match valid
        """
        self.pages = pages
        self.context = exhibit_context
        self.match_threshold = match_threshold
        # Pre-compute lowercase text for efficient matching
        self._page_text_lower = {p.absolute_page: p.text.lower() for p in pages}

    def match(self, entry: Dict) -> MatchResult:
        """
        Match an entry to its source page(s).

        Args:
            entry: Extracted entry dict with date, provider, facility, etc.

        Returns:
            MatchResult with citation and match metadata
        """
        terms = self._extract_search_terms(entry)

        if not terms:
            return self._fallback_result(entry)

        scores = self._score_pages(terms)

        if not scores:
            return self._fallback_result(entry)

        best_pages = self._select_best_pages(scores)

        if not best_pages:
            return self._fallback_result(entry)

        return self._build_result(best_pages, terms, scores)

    def _extract_search_terms(self, entry: Dict) -> List[SearchTerm]:
        """
        Extract weighted search terms from entry fields.

        Priority and weights:
        - date: weight=3.0, exact match
        - provider: weight=2.0, fuzzy match
        - facility: weight=2.0, fuzzy match
        - diagnoses[:2]: weight=1.0, fuzzy match
        - procedures[:2]: weight=1.0, fuzzy match
        """
        terms = []

        # Date - highest weight, exact match
        date = entry.get("date", "")
        if date and date.lower() not in self.SKIP_TERMS:
            normalized = self._normalize_date(date)
            if normalized:
                terms.append(SearchTerm(value=normalized, weight=3.0, fuzzy=False))

        # Provider - high weight, fuzzy match
        provider = entry.get("provider", "")
        if provider and provider.lower() not in self.SKIP_TERMS:
            terms.append(SearchTerm(value=provider, weight=2.0, fuzzy=True))

        # Facility - high weight, fuzzy match
        facility = entry.get("facility", "")
        if facility and facility.lower() not in self.SKIP_TERMS:
            terms.append(SearchTerm(value=facility, weight=2.0, fuzzy=True))

        # Diagnoses - lower weight, fuzzy match, first 2 only
        diagnoses = entry.get("diagnoses", [])
        for diag in diagnoses[:2]:
            if isinstance(diag, str) and len(diag) > 3 and diag.lower() not in self.SKIP_TERMS:
                terms.append(SearchTerm(value=diag, weight=1.0, fuzzy=True))

        # Procedures - lower weight, fuzzy match, first 2 only
        procedures = entry.get("procedures", [])
        for proc in procedures[:2]:
            if isinstance(proc, str) and len(proc) > 3 and proc.lower() not in self.SKIP_TERMS:
                terms.append(SearchTerm(value=proc, weight=1.0, fuzzy=True))

        return terms

    def _normalize_date(self, date: str) -> Optional[str]:
        """
        Normalize date for matching.

        Currently returns as-is. Future enhancement could handle
        different date formats (MM/DD/YYYY, YYYY-MM-DD, etc.)

        Args:
            date: Date string from entry

        Returns:
            Normalized date string or None if invalid
        """
        if not date or not date.strip():
            return None
        return date.strip()

    def _score_pages(self, terms: List[SearchTerm]) -> Dict[int, float]:
        """
        Score each page against search terms.

        Args:
            terms: List of SearchTerm objects

        Returns:
            Dict mapping absolute_page to score
        """
        scores = {}

        for page in self.pages:
            page_text = self._page_text_lower.get(page.absolute_page, "")
            score = 0.0

            for term in terms:
                if self._term_matches(term, page_text):
                    score += term.weight

            if score > 0:
                scores[page.absolute_page] = score

        return scores

    def _term_matches(self, term: SearchTerm, page_text: str) -> bool:
        """
        Check if a term matches in the page text.

        Args:
            term: SearchTerm to look for
            page_text: Lowercase page text

        Returns:
            True if term is found
        """
        if term.fuzzy:
            return self._fuzzy_match(term.value, page_text)
        else:
            # Exact match (case-insensitive)
            return term.value.lower() in page_text

    def _fuzzy_match(self, term: str, text: str, threshold: float = 0.85) -> bool:
        """
        Fuzzy match a term against text.

        Handles common variations like:
        - Different punctuation
        - Extra/missing spaces
        - Word-boundary matching for short terms

        Args:
            term: Term to match
            text: Text to search in (should be lowercase)
            threshold: Similarity threshold (unused for now)

        Returns:
            True if fuzzy match found
        """
        normalized_term = self._normalize_for_match(term)
        normalized_text = self._normalize_for_match(text)

        # Substring match
        if normalized_term in normalized_text:
            return True

        # Word-boundary match for short terms (avoid false positives)
        if len(normalized_term) <= 10:
            # Check if term appears as complete word(s)
            pattern = r'\b' + re.escape(normalized_term) + r'\b'
            if re.search(pattern, normalized_text, re.IGNORECASE):
                return True

        return False

    def _normalize_for_match(self, text: str) -> str:
        """
        Normalize text for matching.

        - Lowercase
        - Remove punctuation
        - Normalize whitespace

        Args:
            text: Text to normalize

        Returns:
            Normalized string
        """
        # Lowercase
        result = text.lower()
        # Remove punctuation (keep alphanumeric and spaces)
        result = re.sub(r'[^\w\s]', ' ', result)
        # Normalize whitespace
        result = ' '.join(result.split())
        return result

    def _select_best_pages(self, scores: Dict[int, float]) -> List[int]:
        """
        Select the best matching page(s).

        Finds the highest-scoring page, then includes consecutive
        pages with decent scores (for multi-page entries).

        Args:
            scores: Dict mapping absolute_page to score

        Returns:
            List of selected absolute page numbers (sorted)
        """
        if not scores:
            return []

        # Filter to pages meeting threshold
        qualified = {p: s for p, s in scores.items() if s >= self.match_threshold}

        if not qualified:
            return []

        # Find best page
        best_page = max(qualified, key=qualified.get)
        best_score = qualified[best_page]

        # Include consecutive pages with decent scores
        consecutive_threshold = self.match_threshold * 0.7
        selected = [best_page]

        # Check page before
        prev_page = best_page - 1
        if prev_page in scores and scores[prev_page] >= consecutive_threshold:
            selected.insert(0, prev_page)

        # Check page after
        next_page = best_page + 1
        if next_page in scores and scores[next_page] >= consecutive_threshold:
            selected.append(next_page)

        return sorted(selected)

    def _build_result(
        self,
        pages: List[int],
        terms: List[SearchTerm],
        scores: Dict[int, float],
    ) -> MatchResult:
        """
        Build MatchResult from matched pages.

        Args:
            pages: Selected page numbers
            terms: Search terms used
            scores: Page scores

        Returns:
            MatchResult with citation
        """
        start_page = min(pages)
        end_page = max(pages) if len(pages) > 1 else None

        # Find the PageText for start page to get relative page info
        page_info = next((p for p in self.pages if p.absolute_page == start_page), None)

        if page_info:
            citation = Citation(
                absolute_page=start_page,
                exhibit_id=page_info.exhibit_id,
                relative_page=page_info.relative_page,
                total_pages=self.context.get("total_pages"),
                source_type="ere",
                is_estimated=False,
                confidence=min(1.0, scores.get(start_page, 0) / 10.0),
            )

            # Add range info if multi-page
            if end_page and end_page != start_page:
                end_info = next((p for p in self.pages if p.absolute_page == end_page), None)
                if end_info:
                    citation.end_absolute_page = end_page
                    citation.end_relative_page = end_info.relative_page
        else:
            # Fallback citation
            citation = Citation(
                absolute_page=start_page,
                source_type="generic",
                is_estimated=True,
            )

        # Collect matched terms
        matched = [t.value for t in terms if any(
            self._term_matches(t, self._page_text_lower.get(p, ""))
            for p in pages
        )]

        return MatchResult(
            citation=citation,
            match_score=max(scores.get(p, 0) for p in pages),
            matched_terms=matched,
            match_method="search",
        )

    def _fallback_result(self, entry: Dict) -> MatchResult:
        """
        Create fallback result when no match found.

        Uses first page of exhibit as default.

        Args:
            entry: Original entry dict

        Returns:
            MatchResult with fallback citation
        """
        if self.pages:
            first_page = self.pages[0]
            citation = Citation(
                absolute_page=first_page.absolute_page,
                exhibit_id=first_page.exhibit_id,
                relative_page=first_page.relative_page,
                total_pages=self.context.get("total_pages"),
                source_type="ere",
                is_estimated=True,
                confidence=0.3,
            )
        else:
            # No pages available - use context
            start_page = self.context.get("start_page", 1)
            citation = Citation(
                absolute_page=start_page,
                exhibit_id=self.context.get("exhibit_id", ""),
                relative_page=1,
                source_type="generic",
                is_estimated=True,
                confidence=0.1,
            )

        return MatchResult(
            citation=citation,
            match_score=0.0,
            matched_terms=[],
            match_method="fallback",
        )
