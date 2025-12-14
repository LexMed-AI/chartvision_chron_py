"""
Chronology post-processing for ChartVision reports.

Handles deduplication and lab panel grouping of chronology entries.
"""
from collections import defaultdict
from typing import List

from app.core.models.chartvision import ChronologyEntry
from app.core.builders.source_formatter import combine_sources


def deduplicate_chronology(entries: List[ChronologyEntry]) -> List[ChronologyEntry]:
    """Remove duplicate chronology entries.

    Duplicates are identified by (date, provider, occurrence_treatment[:100], source).
    Including occurrence_treatment prefix prevents merging distinct visits
    (e.g., office_visit and imaging_report) on the same day with same provider.

    Keeps the first occurrence when duplicates are found.

    Args:
        entries: List of chronology entries (may contain duplicates)

    Returns:
        Deduplicated list of chronology entries
    """
    seen = set()
    deduplicated = []

    for entry in entries:
        # Create key from date, provider, occurrence prefix, and source
        occ_prefix = (entry.occurrence_treatment or "")[:100]
        key = (entry.date, entry.provider_specialty, occ_prefix, entry.source)

        if key not in seen:
            seen.add(key)
            deduplicated.append(entry)

    return deduplicated


def group_lab_panels(entries: List[ChronologyEntry]) -> List[ChronologyEntry]:
    """Group lab results from the same panel into a single row.

    Lab results with same (date, provider, facility) and occurrence_treatment
    containing "**Test:**" are combined into one entry with all test results.

    Args:
        entries: List of chronology entries

    Returns:
        List with lab panels grouped into single entries
    """
    # Separate lab results from other entries
    labs = []
    others = []

    for entry in entries:
        occ = entry.occurrence_treatment.lower() if entry.occurrence_treatment else ""
        if "**test:**" in occ:
            labs.append(entry)
        else:
            others.append(entry)

    if not labs:
        return entries

    # Group labs by (date, provider, facility)
    lab_groups = defaultdict(list)
    for lab in labs:
        key = (lab.date, lab.provider_specialty, lab.facility)
        lab_groups[key].append(lab)

    # Merge each group into a single entry
    merged_labs = []
    for (date_val, provider, facility), group in lab_groups.items():
        if len(group) == 1:
            merged_labs.append(group[0])
        else:
            merged_entry = _merge_lab_group(date_val, provider, facility, group)
            merged_labs.append(merged_entry)

    return others + merged_labs


def _merge_lab_group(
    date_val,
    provider: str,
    facility: str,
    group: List[ChronologyEntry],
) -> ChronologyEntry:
    """Merge a group of lab results into a single entry.

    Args:
        date_val: Date of the lab results
        provider: Provider name
        facility: Facility name
        group: List of lab result entries to merge

    Returns:
        Single merged ChronologyEntry
    """
    combined_tests = []
    sources = set()

    for entry in group:
        combined_tests.append(entry.occurrence_treatment)
        sources.add(entry.source)

    # Create combined occurrence text
    combined_occ = "<br><br>".join(combined_tests)

    # Create combined source citation
    combined_source = combine_sources(list(sources))

    return ChronologyEntry(
        date=date_val,
        provider_specialty=provider,
        facility=facility,
        occurrence_treatment=combined_occ,
        source=combined_source,
    )


def process_chronology(entries: List[ChronologyEntry]) -> List[ChronologyEntry]:
    """Full chronology post-processing pipeline.

    Applies lab panel grouping, deduplication, and sorting.

    Args:
        entries: Raw chronology entries

    Returns:
        Processed, sorted chronology entries
    """
    # Step 1: Group lab panels
    grouped = group_lab_panels(entries)

    # Step 2: Deduplicate
    deduplicated = deduplicate_chronology(grouped)

    # Step 3: Sort by date (oldest first for chronological order)
    deduplicated.sort(key=lambda x: x.date)

    return deduplicated
