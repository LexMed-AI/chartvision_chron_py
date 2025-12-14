"""
PDF Exhibit Extraction.

Extracts F-section medical exhibits from ERE PDF files using bookmarks.
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Memory limits for image extraction
from app.config.extraction_limits import MAX_IMAGES_PER_EXHIBIT


def extract_f_exhibits_from_pdf(
    pdf_path: str,
    max_exhibits: Optional[int] = None,
    max_pages_per_exhibit: int = 50
) -> List[Dict[str, Any]]:
    """
    Extract F-section exhibits from ERE PDF using bookmarks with vision fallback.

    Parses PDF bookmarks to find individual F-section exhibits (1F, 2F, etc.)
    and extracts text from each exhibit. For scanned pages, includes image data
    for vision-based extraction.

    Args:
        pdf_path: Path to ERE PDF file
        max_exhibits: Maximum number of exhibits to extract (None for all)
        max_pages_per_exhibit: Maximum pages to extract per exhibit

    Returns:
        List of exhibit dicts with structure:
        {
            "exhibit_id": str,
            "text": str,  # Combined text from text-extractable pages
            "images": List[bytes],  # PNG images for scanned pages
            "page_range": (start, end),
            "has_scanned_pages": bool,
            "scanned_page_nums": List[int]  # 1-indexed page numbers
        }
    """
    import fitz  # PyMuPDF
    from app.adapters.pdf.preprocessing import (
        is_scanned_page,
        render_page_to_image,
        strip_court_headers,
    )

    try:
        doc = fitz.open(pdf_path)
        toc = doc.get_toc()

        # Extract F-section exhibits from bookmarks (pattern: ##F: ... or ##F - ...)
        f_exhibits = []
        for level, title, page in toc:
            match = re.match(r'^(\d+F)\s*[-:]', title)
            if match:
                f_exhibits.append({
                    "exhibit_id": match.group(1),
                    "title": title,
                    "start_page": page,
                })

        # Calculate end pages based on next exhibit
        for i, ex in enumerate(f_exhibits):
            if i < len(f_exhibits) - 1:
                ex["end_page"] = f_exhibits[i + 1]["start_page"] - 1
            else:
                ex["end_page"] = len(doc)

        logger.info(f"Found {len(f_exhibits)} F-section exhibits in PDF")

        # Apply max_exhibits limit
        if max_exhibits:
            f_exhibits = f_exhibits[:max_exhibits]

        # Extract content from each exhibit (text + images for scanned pages)
        exhibits_with_content = []
        total_scanned = 0

        for ex in f_exhibits:
            start = ex["start_page"] - 1  # 0-indexed for fitz
            end = min(ex["end_page"], ex["start_page"] + max_pages_per_exhibit - 1)

            text_parts = []
            images = []
            scanned_page_nums = []

            for page_num in range(start, min(end, len(doc))):
                page = doc[page_num]

                if is_scanned_page(page):
                    # Check memory limit
                    if len(images) >= MAX_IMAGES_PER_EXHIBIT:
                        logger.warning(
                            f"Exhibit {ex['exhibit_id']} truncated at "
                            f"{MAX_IMAGES_PER_EXHIBIT} scanned pages"
                        )
                        break
                    # Scanned page - render to image for vision extraction
                    images.append(render_page_to_image(page))
                    scanned_page_nums.append(page_num + 1)  # 1-indexed
                    total_scanned += 1
                else:
                    # Text page - extract text and strip court headers
                    page_text = page.get_text()
                    # Strip court headers to send clean text to LLM
                    clean_text = strip_court_headers(page_text)
                    if clean_text.strip():
                        text_parts.append(clean_text)

            text = "\n".join(text_parts)
            has_content = text.strip() or images

            if has_content:
                exhibit_data = {
                    "exhibit_id": ex["exhibit_id"],
                    "text": text,
                    "images": images,
                    "page_range": (ex["start_page"], end),
                    "has_scanned_pages": len(images) > 0,
                    "scanned_page_nums": scanned_page_nums,
                }
                exhibits_with_content.append(exhibit_data)

                if images:
                    logger.info(
                        f"Exhibit {ex['exhibit_id']}: {len(text):,} chars text, "
                        f"{len(images)} scanned pages (pp. {scanned_page_nums})"
                    )
                else:
                    logger.debug(f"Exhibit {ex['exhibit_id']}: {len(text):,} chars text")

        doc.close()

        if total_scanned > 0:
            logger.info(
                f"Extracted {len(exhibits_with_content)} F-exhibits "
                f"({total_scanned} scanned pages requiring vision)"
            )
        else:
            logger.info(f"Extracted {len(exhibits_with_content)} F-exhibits (all text)")

        return exhibits_with_content

    except Exception as e:
        logger.error(f"Failed to extract F-exhibits from {pdf_path}: {e}")
        return []


def load_bookmark_metadata(metadata_path: str) -> Dict[str, Any]:
    """
    Load bookmark metadata from JSON file.

    Args:
        metadata_path: Path to metadata JSON file

    Returns:
        Bookmark metadata dict or empty dict on error
    """
    import json
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        logger.info(
            f"Loaded bookmark metadata: {metadata.get('total_bookmarks', 0)} bookmarks, "
            f"{metadata.get('exhibit_count', 0)} exhibits"
        )
        return metadata
    except Exception as e:
        logger.error(f"Failed to load bookmark metadata from {metadata_path}: {e}")
        return {}
