# ERE Format Reference Guide

This document describes the three types of Electronic Records Express (ERE) PDF files that ChartVision processes, their structural differences, and handling strategies.

**Last Updated:** 2025-12-10 (Sandefur test file analysis)

## Purpose

Understanding ERE format differences is critical for optimizing:

1. **Extraction** - Route to text vs vision extraction based on format
2. **Parsing** - Handle bookmark variations across formats
3. **Citation Accuracy** - Map page bookmarks correctly for exhibit/page citations

## Overview

Social Security ERE files arrive in three formats depending on their source:

| Type | Source | Searchability | Bookmark Style | Page Bookmarks |
|------|--------|---------------|----------------|----------------|
| **Raw SSA** | Direct SSA ERE export | ~94% searchable | `Section F.`, `1F (Page X of Y)` | ✅ With exhibit prefix |
| **Processed** | Assure, Atlas, Chronicle Legal | 100% searchable | `F. Medical...`, `(page X of Y)` | ✅ No exhibit prefix |
| **Court Transcript** | Federal court filings (PACER) | Images only (~95 chars/page) | `C1F -`, descriptive sections | ❌ None |

## Sandefur Test File Comparison

All three formats tested with same claimant (Sandefur) for direct comparison:

| Metric | Raw SSA | Processed | Court Transcript |
|--------|---------|-----------|------------------|
| **File** | `Sandefur_raw_ere.pdf` | `sandefur_processed.pdf` | `2024 Court Sandefur...pdf` |
| **Total Pages** | 2,941 | 3,494 | 3,148 |
| **Section F Exhibits** | 62 | 62 | 41 |
| **Section F Pages** | 2,049 (pp 893-2941) | 2,110 (pp 1385-3494) | 1,527 (pp 1622-3148) |
| **Total Bookmarks** | 3,136 | ~2,300 | 212 |
| **Page Bookmarks** | 2,049 (100% coverage) | 2,110 (100% coverage) | 0 (none) |
| **Text Searchable** | ~94% | 100% | ~0% (court stamps only) |
| **Largest Exhibit** | 17F (437 pages) | 17F (437 pages) | C57F (667 pages) |

---

## Type 1: Raw SSA ERE

**Source:** Direct download from SSA's Electronic Records Express system

### Characteristics

- **Text Extraction:** ~94% searchable, ~6% scanned images or blank pages
- **Bookmarks:** 1 bookmark per page + section/exhibit headers (3-level hierarchy)
- **Page Bookmark Coverage:** 100% - every page has a Level 3 bookmark

### Bookmark Structure

```
Level 1: Section headers
  "Section A.  Payment Documents/Decisions"
  "Section B.  Jurisdictional Documents/Notices"
  "Section F.  Medical Records"

Level 2: Exhibits (with SSA code, provider, dates, page count)
  "1F: Progress Notes (PROGRESSNOTES) Src.: Mark E Sutherland, MD Tmt. Dt.: 07/01/2009 - 10/09/2009 (4 pages)"
  "17F: Inpatient Hospital Records (INHOSP) Src.: Christus St Michael Tmt. Dt.: 02/01/2013-11/03/2015 (437 pages)"

Level 3: Page bookmarks (WITH exhibit ID prefix)
  "1F (Page 1 of 4)"
  "1F (Page 2 of 4)"
  "17F (Page 235 of 437)"
```

### Detection Markers

- Section headers start with `Section [ABDEF].`
- Page bookmarks include exhibit ID: `1F (Page X of Y)`
- No Table of Contents bookmark
- Has Level 3 page bookmarks with exhibit prefix

### Regex Patterns

```python
# Section header
r"Section\s+([ABDEF])\b"

# Exhibit title
r"^(\d+)([ABDEF])(?:\s*[-:])"

# Page bookmark (with exhibit prefix)
r"^(\d+)([ABDEF])\s*\(Page\s+(\d+)\s+of\s+(\d+)\)"

# Full exhibit title parser (Section F)
r'(\d+F):\s*(.+?)\s*\((\w+)\)\s*Src\.?:\s*(.+?)\s*Tmt\.?\s*Dt\.?:\s*(.+?)\s*\((\d+)\s*pages?\)'
# Groups: exhibit_id, record_type, ssa_code, provider, treatment_date, page_count
```

### Sandefur Raw SSA Statistics

| SSA Code | Count | Description |
|----------|-------|-------------|
| PROGRESSNOTES | 24 | Progress notes from providers |
| CPYEVREQ | 13 | Copy of Evidence Request |
| MEDNOMER | 4 | Medical Source - No MER Available |
| 448 | 4 | Request for Medical Advice |
| INHOSP | 3 | Inpatient Hospital Records |
| HOSPITAL | 2 | Hospital Records |
| OUTHOSP | 2 | Outpatient Hospital Records |
| OFFCREC | 2 | Office Treatment Records |
| 3826 | 2 | Medical Report/General |
| RADIOREP | 1 | Radiology Report |
| RMEDINT | 1 | Response to Medical Interrogatory |
| 4734 | 1 | Physical RFC Assessment |
| 4734SUP | 1 | Mental RFC Assessment |
| CE | 1 | Consultative Examination |
| 2506 | 1 | Psychiatric Review Technique |

---

## Type 2: Processed ERE

**Source:** Third-party processing systems (Assure, Atlas, Chronicle Legal)

### Characteristics

- **Text Extraction:** 100% searchable (OCR applied during processing)
- **Bookmarks:** Table of Contents + 3-level hierarchy with page bookmarks
- **Page Bookmark Coverage:** 100% - every page has a Level 3 bookmark
- **Additional:** Consistent formatting, clean metadata in titles

### Bookmark Structure

```
Level 1: Table of Contents (first bookmark)
  "Table of Contents"

Level 1: Section headers (letter prefix format)
  "A. Payment Documents/Decisions"
  "B. Jurisdictional Documents/Notices"
  "F. Medical Records"

Level 2: Exhibits (with SSA code, provider, dates)
  "10F: Progress Notes - PROGRESSNOTES Abraham Breast Clinic Tmt. Dt.: 03/05/2014-06/06/2014 (235 pages)"
  "17F: Inpatient Hospital Records - INHOSP Christus St Michael Tmt. Dt.: 02/01/2013-11/03/2015 (437 pages)"

Level 3: Page bookmarks (NO exhibit ID prefix - lowercase)
  "(page 1 of 235)"
  "(page 2 of 235)"
  "(page 235 of 235)"
```

### Detection Markers

- First bookmark is `Table of Contents`
- Section headers use letter prefix: `A. Payment...`, `F. Medical...`
- Page bookmarks lack exhibit ID: `(page X of Y)` (lowercase, no prefix)

### Regex Patterns

```python
# Section header (letter prefix)
r"^([ABDEF])\.\s+"

# Exhibit title
r"^(\d+)([ABDEF])(?:\s*[-:])"

# Page bookmark (no exhibit prefix, lowercase)
r"^\(page\s+(\d+)\s+of\s+(\d+)\)"
```

### Key Differences from Raw SSA

| Aspect | Raw SSA | Processed |
|--------|---------|-----------|
| **Table of Contents** | ❌ None | ✅ First bookmark |
| **Section Header Format** | `Section F.` | `F. Medical Records` |
| **Page Bookmark Format** | `1F (Page 1 of 4)` | `(page 1 of 4)` |
| **Page Bookmark Case** | Mixed case | Lowercase |
| **OCR Quality** | ~94% searchable | 100% searchable |
| **Exhibit Context in Page BM** | ✅ Has exhibit ID | ❌ No exhibit ID |

---

## Type 3: Court Transcript ERE

**Source:** Federal court case filings (PACER)

### Characteristics

- **Text Extraction:** Images only (~95 chars per page = court stamp only)
- **Structure:** Court captioning section + scanned exhibits (entire document is images)
- **Page Bookmarks:** ❌ **NONE** - requires page calculation from exhibit start
- **Vision Required:** 100% of medical content requires vision extraction

### Bookmark Structure

```
Level 1: Court-specific headers (first 2 bookmarks)
  "Certification Page" @ page 1
  "Court Transcript Index" @ page 2
  "Documents Related to Administrative Process Including Transcript" @ page 10

Level 1: Section headers (descriptive format - not letter prefix)
  "Payment Documents and Decisions"    → Section A
  "Jurisdictional Documents and Notices" → Section B
  "Non Disability Related Development" → Section D
  "Disability Related Development"     → Section E
  "Medical Records"                    → Section F

Level 2/3: Exhibits (C prefix, dash separator, date and provider in title)
  "C22F - Copy of Evidence Request, dated 11/24/2015, from ANESTHESIA SPECIALIST OF AR"
  "C28F - Progress Notes, dated 10/26/2015 to 01/11/2016, from Collom & Carney Clinic"
  "C57F - Medical Report/General, dated 04/25/2018, from John Anigbogu MD"

Level 4: NONE (no page bookmarks exist)
```

### Court Stamp Format (Only Extractable Text)

All pages contain only the court header stamp (~95 characters):

```
Case 4:23-cv-04097-BAB   Document 11-1    Filed 02/08/24   Page X of 1527 PageID #: YYYY
```

**Pattern:** `Case [CaseNumber]   Document [DocNumber]    Filed [Date]   Page X of [TotalPages] PageID #: [PageID]`

### Detection Markers

- Has `Certification Page` or `Court Transcript Index` in first 5 bookmarks
- Section headers are descriptive (not letter prefix): `"Medical Records"` not `"F. Medical Records"`
- Exhibits prefixed with `C`: `C22F -`, `C57F -`
- No Level 3/4 page-level bookmarks
- Text extraction returns only court stamps (~95 chars per page)

### Regex Patterns

```python
# Section header (descriptive name mapping)
section_name_map = {
    "payment documents and decisions": "A",
    "jurisdictional documents and notices": "B",
    "non disability related development": "D",
    "disability related development": "E",
    "medical records": "F",
}

# Exhibit title (with C prefix and dash)
r"^C(\d+)([ABDEF])\s*-\s*(.+?),\s*dated\s*(.+?),\s*from\s*(.+)$"
# Groups: exhibit_num, section_letter, record_type, date, provider

# Exhibit ID extraction (with optional C prefix)
r"^C?(\d+)([ABDEF])(?:\s*[-:])"
```

### Sandefur Court Transcript Statistics

| Record Type | Count | Examples |
|-------------|-------|----------|
| Progress Notes | 12 | C28F, C29F, C31F, C32F, C33F, C45F-C51F |
| Evidence Request | 10 | C22F, C23F, C24F, C34F, C35F, C38F-C42F |
| Medical Advice Request | 4 | C25F, C26F, C27F, C62F |
| Medical Source (No MER) | 4 | C36F, C37F, C43F, C44F |
| Medical Report | 2 | C52F, C57F (667 pages!) |
| Office Treatment Records | 2 | C53F, C55F |
| RFC Assessment | 2 | C58F, C60F |
| Outpatient Hospital | 1 | C54F |
| Radiology | 1 | C30F |
| Response to Interrogatory | 1 | C56F |
| Consultative Exam | 1 | C59F |
| Psychiatric Review | 1 | C61F |

### Critical Implementation Note

**Court transcripts require special handling in citation enrichment:**

```typescript
// For court transcripts (no page bookmarks)
if (exhibit.pageBookmarks.length === 0) {
  // LLM always outputs exhibit-relative page (e.g., page 5 of exhibit 10F)
  // For court transcripts, we calculate absolute pdfPage using fallback formula
  const pdfPage = Math.min(
    exhibit.startPage + citation.page - 1,
    exhibit.endPage  // Clamp to exhibit range
  );
  return {
    exhibitId: citation.exhibitId,
    page: citation.page,  // Keep exhibit-relative
    pageOfTotal: [citation.page, exhibit.pageCount],
    pdfPage: pdfPage  // Calculated absolute page for merged PDF linking
  };
}
```

---

## Type Detection Algorithm

```python
def detect_ere_type(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()

    if not toc:
        return "UNKNOWN"

    first_bookmark = toc[0][1] if toc else ""
    first_l2 = next((t[1] for t in toc if t[0] == 2), "")

    # Court Transcript detection
    has_court_prefix = first_l2.startswith("C") and len(first_l2) > 2 and first_l2[1].isdigit()
    has_certification = any("certification" in t[1].lower() for t in toc[:5])
    has_court_index = any("court" in t[1].lower() and "index" in t[1].lower() for t in toc[:5])

    if has_court_prefix or has_certification or has_court_index:
        return "COURT_TRANSCRIPT"

    # Processed detection
    has_toc = first_bookmark.lower() == "table of contents"
    page_bookmarks_no_id = any(t[1].startswith("(page") for t in toc if t[0] == 3)

    if has_toc or page_bookmarks_no_id:
        return "PROCESSED"

    # Default to Raw SSA
    return "RAW_SSA"
```

---

## Text Extraction Strategy

| Type | Strategy | Vision % | Notes |
|------|----------|----------|-------|
| **Raw SSA** | Text extraction with vision fallback | ~6% | Most pages searchable; scanned pages need vision |
| **Processed** | Text extraction only | 0% | 100% OCR'd, no vision needed |
| **Court Transcript** | Vision extraction required | 100% | All pages are scanned images |

### Format Detection → Extraction Mode

```python
def get_extraction_mode(ere_type: str, text_length: int) -> str:
    """Determine extraction mode based on format and text content."""
    if ere_type == "COURT_TRANSCRIPT":
        return "vision"  # Always vision for court transcripts

    if ere_type == "PROCESSED":
        return "text"  # Always text for processed files

    # Raw SSA: check if page is scanned
    if text_length < 200:
        return "vision"  # Scanned page in raw file
    return "text"
```

### Scanned Page Detection

```python
def is_scanned_page(text: str) -> bool:
    """Returns True if page likely needs vision extraction."""
    # Court stamps are ~95 chars; meaningful text starts at ~200+ chars
    return len(text.strip()) < 200
```

```typescript
function isLikelyScannedPage(text: string): boolean {
  // Court stamps are ~95 chars; meaningful medical content is 200+ chars
  return text.length < 200;
}
```

### Text Extraction Quality by Format

| Format | Avg Chars/Page | Token Estimate | Quality |
|--------|----------------|----------------|---------|
| Raw SSA | 1,500-2,500 | 375-625 | Good (some OCR artifacts) |
| Processed | 2,000-3,500 | 500-875 | Excellent (clean OCR) |
| Court Transcript | ~95 | ~24 | N/A (court stamps only) |

### Chunking Implications

Based on target chunk size of 8,000 tokens (~32K characters):

| Format | Pages/Chunk | Strategy |
|--------|-------------|----------|
| Raw SSA | 12-20 pages | Text extraction with vision fallback |
| Processed | 10-16 pages | Text extraction only |
| Court Transcript | 20-30 pages | Vision extraction (batch pages into images) |

### Large Exhibit Handling

Exhibits over 100 pages (observed in Sandefur):

| Exhibit | Pages | Format | Recommended Chunks |
|---------|-------|--------|-------------------|
| 10F | 235 | Raw/Processed | 12-16 chunks |
| 17F | 437 | Raw/Processed | 22-29 chunks |
| 49F | 146 | Raw/Processed | 8-10 chunks |
| C57F | 667 | Court | 22-34 vision batches |

---

## ERE Section Structure

All ERE formats contain five standard sections:

| Section | Name | Description | ChartVision Processing |
|---------|------|-------------|------------------------|
| **A** | Payment Documents/Decisions | ALJ decisions, DDEs, court orders | DDE exhibits extracted for RFC data |
| **B** | Jurisdictional Documents/Notices | Hearing transcripts, notices | Excluded |
| **D** | Non-Disability Development | Non-disability related documents | Excluded |
| **E** | Disability Development | Claimant reports, VE resumes | Filtered by category |
| **F** | Medical Records | All medical evidence | **Primary focus** |

### Section A Document Types

| Category | Examples |
|----------|----------|
| ALJ Decisions | ALJDEC - ALJ Hearing Decision |
| Appeals Council | ACDENY, ACORDR - AC Denial/Order |
| Court Decisions | DECCOURT - District Court Decision |
| DDEs | Disability Determination Explanation (RFC assessments) |
| Other | COMPLAINT, EAJAAWARD |

### Section E Document Types

| Category | SSA Form | Description |
|----------|----------|-------------|
| Self-Reports | 3369, 3373 | Work History, Function Report |
| Disability Reports | 3368, 3367, 3441 | Adult, Field Office, Appeals |
| Vocational | 4633, 4632 | Work Background, Medications |
| Representative | REPBRIEF, PROFFER | Attorney correspondence |

### Section F Record Types

Complete SSA record codes mapped to extraction templates (from Sandefur analysis):

| SSA Code | Description | Template | Frequency |
|----------|-------------|----------|-----------|
| **Clinical Records** |
| PROGRESSNOTES | Progress Notes | office_visit | Very Common (38%) |
| OFFCREC | Office Treatment Records | office_visit | Common |
| 3826 | Medical Report/General | office_visit | Occasional |
| **Hospital Records** |
| HOSPITAL | Hospital Records | hospital_admission | Common |
| INHOSP | Inpatient Hospital Records | hospital_admission | Common |
| OUTHOSP | Outpatient Hospital Records | hospital_admission | Common |
| EMERGENCY | Emergency Room | hospital_admission | Occasional |
| **Specialty Records** |
| RADIOREP | Radiology Report | imaging_report | Occasional |
| RADIOLOGY | Imaging/Radiology | imaging_report | Occasional |
| LABWORK | Laboratory Results | lab_result | Occasional |
| MENTALHEALTH | Mental Health Records | mental_health | Occasional |
| **Consultative Exams** |
| CE | Consultative Examination | consultative_exam | Occasional |
| CONSEXAM | Consultative Examination | consultative_exam | Occasional |
| **RFC/DDE Forms** |
| 4734 | Physical RFC Assessment | dde_assessment | Rare (Section F) |
| 4734SUP | Mental RFC Assessment | dde_assessment | Rare (Section F) |
| 2506 | Psychiatric Review Technique | dde_assessment | Rare |
| **Medical Opinions** |
| RMEDINT | Response to Medical Interrogatory | medical_source_statement | Rare |
| **Administrative** |
| CPYEVREQ | Copy of Evidence Request | **skip** | Common (21%) |
| MEDNOMER | Medical Source - No MER Available | **skip** | Occasional |
| 448 | Request for Medical Advice | **skip** | Occasional |

**Note:** CPYEVREQ and MEDNOMER are administrative documents without medical content and should be skipped during extraction.

---

## DDE (Disability Determination Explanation) Structure

DDEs are RFC assessment documents in Section A containing structured medical findings.

### Location in ERE

```
Section A → exhibits with "DDE" or "4734" in title
Example: "4A: Disability Determination Explanation (DDE) Dec. Dt.: MM/DD/YYYY (N pages)"
```

### DDE Page Structure

**Page 1 - Claimant Information:**
```
┌─────────────────────────────────────────────────────────────┐
│ Disability Determination Explanation     exhibit no. CXA    │
│ PAGE: 1 OF N                                                │
├─────────────────────────────────────────────────────────────┤
│ CLAIMANT INFORMATION                                        │
│   Name, SSN, Address, Phone                                 │
│   Gender, Height, Weight                                    │
│   Special Indications                                       │
├─────────────────────────────────────────────────────────────┤
│ RELEVANT DATES                                              │
│   DOB, AOD (Alleged Onset Date), DLI (Date Last Insured)   │
├─────────────────────────────────────────────────────────────┤
│ ALLEGATIONS OF IMPAIRMENTS                                  │
│   List of claimed conditions                                │
└─────────────────────────────────────────────────────────────┘
```

**Page 2 - Technical Issues:**
```
┌─────────────────────────────────────────────────────────────┐
│ TECHNICAL ISSUES                                            │
│   Is individual working? Prior Electronic Filings           │
│   Alleged Onset Date, Work after AOD                        │
├─────────────────────────────────────────────────────────────┤
│ EVIDENCE OF RECORD                                          │
│   List of medical sources with:                             │
│   - Provider name, dates, document type                     │
│   - Notes summarizing key findings                          │
└─────────────────────────────────────────────────────────────┘
```

**Subsequent Pages:**
- Provider-by-provider evidence summaries
- Diagnostic findings, treatment notes
- RFC findings and limitations

### DDE Extraction Strategy

DDEs require **vision extraction** due to:
1. Tabular data (dates, prior claims, evidence lists)
2. Structured forms with boxes/fields
3. Key RFC findings embedded in formatted text

---

## Exhibit Title Patterns

### Raw SSA Format

```
{ExhibitID}:  {Description} ({SSACode}) Dec. Dt.:  {Date} ({N} pages)
```

Example: `1A:  ALJ Hearing Decision (ALJDEC) Dec. Dt.:  01/31/2014 (26 pages)`

### Section F Medical Records Format

```
{ExhibitID}: {RecordType} ({SSACode})  Src.:  {Provider} Tmt. Dt.:  {Date}
```

Example: `17F: Progress Notes (PROGRESSNOTES)  Src.:  Memorial Medical Clinic Tmt. Dt.:  10/04/2013`

### Provider Name Extraction

```python
# Full pattern with provider
r'(\d+F):\s*(.+?)\s*\((\w+)\)\s*Src\.:\s*(.+?)\s*Tmt\.\s*Dt\.:'

# Groups: exhibit_id, record_type, ssa_code, provider_name
```

---

## Citation System

### Page Bookmark → PDF Page Mapping

| Format | Bookmark Style | Has Page Bookmarks | Mapping Strategy |
|--------|----------------|-------------------|------------------|
| Raw SSA | `"1F (Page X of Y)"` | ✅ Yes (100%) | Lookup bookmark by pageOfTotal |
| Processed | `"(page X of Y)"` | ✅ Yes (100%) | Lookup bookmark by pageOfTotal |
| Court Transcript | None | ❌ No | Calculate: `exhibit.startPage + page - 1` |

### Citation Enrichment Flow

```typescript
// assembleService.ts - computeCitations()

1. LLM outputs: { exhibitId: "10F", page: 5 }  // exhibit-relative page
2. Lookup exhibit from DynamoDB (saved by ingest)
3. If pageBookmarks exist (Raw SSA or Processed):
   → Find bookmark where pageOfTotal[0] === page
   → Use bookmark.page as pdfPage (absolute PDF page)
   → Return { exhibitId, page, pageOfTotal: [5, 235], pdfPage: 1109 }
4. Else (Court Transcript - no page bookmarks):
   → Calculate pdfPage: exhibit.startPage + page - 1
   → Return { exhibitId, page, pageOfTotal: [5, pageCount], pdfPage: calculated }
```

### Citation Accuracy Verification (Sandefur Files)

| Format | Page Bookmarks | Mapping Accuracy | Notes |
|--------|----------------|------------------|-------|
| Raw SSA | 2,049 | 100% | Every page has bookmark with absolute PDF page |
| Processed | 2,110 | 100% | Every page has bookmark with absolute PDF page |
| Court Transcript | 0 | Calculated | Must use startPage + offset calculation |

### Example Citation Resolution

**Raw SSA (Exhibit 10F, Page 5):**
```
Input:  { exhibitId: "10F", page: 5 }
Lookup: pageBookmarks.find(pb => pb.pageOfTotal[0] === 5)
Found:  { page: 1109, label: "10F (Page 5 of 235)", pageOfTotal: [5, 235] }
Output: { exhibitId: "10F", page: 5, pageOfTotal: [5, 235], pdfPage: 1109 }
```

**Court Transcript (Exhibit C32F, Page 50):**
```
Input:  { exhibitId: "32F", page: 50 }  // C prefix stripped
Lookup: exhibit.pageBookmarks = []  // Empty for court transcripts
Calc:   pdfPage = exhibit.startPage + page - 1 = 1687 + 50 - 1 = 1736
Output: { exhibitId: "32F", page: 50, pageOfTotal: [50, 103], pdfPage: 1736 }
```

---

## Exhibit ID Normalization

Court Transcript exhibits use `C` prefix which should be stripped for consistency:

```python
# Input: "C17F - Medical Records..."
# Normalized ID: "17F"

exhibit_id = re.match(r"^C?(\d+)([ABDEF])", title)
normalized = f"{exhibit_id.group(1)}{exhibit_id.group(2)}"  # "17F"
```

---

## Date Formats

### Primary Format: MM/DD/YYYY

All SSA ERE formats use US date format consistently:

| Context | Pattern | Example |
|---------|---------|---------|
| Decision dates | `Dec. Dt.: MM/DD/YYYY` | `Dec. Dt.: 01/31/2014` |
| Treatment dates | `Tmt. Dt.: MM/DD/YYYY` | `Tmt. Dt.: 10/18/2010` |
| Document dates | `Doc. Dt.: MM/DD/YYYY` | `Doc. Dt.: 12/07/2015` |

### Date Parsing Regex

```python
# Standard SSA date
r'(\d{1,2}/\d{1,2}/\d{4})'

# With context label
r'(?:Dec\.|Tmt\.|Doc\.)\s*Dt\.:\s*(\d{1,2}/\d{1,2}/\d{4})'
```

### Unknown Dates

Many exhibits have `Tmt. Dt.: Unknown` - fall back to document/decision dates when available.

---

## Deduplication Considerations

Providers may have multiple exhibits across different record types or time periods.

**Deduplication key:** `(provider_name, date, finding_type)` rather than exhibit ID alone.

Common scenarios:
- Same provider, multiple visits on different dates
- Same provider, different record types (progress notes vs lab results)
- Copy of Evidence Request duplicates across exhibits

---

## Implementation Recommendations

### Format-Specific Processing

| Format | Ingest | Segment | Extract | Assemble |
|--------|--------|---------|---------|----------|
| **Raw SSA** | Parse bookmarks, store page bookmarks | Text extraction, chunk by ~20 pages | Text mode (vision fallback for <200 chars) | Use page bookmarks for citation |
| **Processed** | Parse bookmarks, store page bookmarks | Text extraction, chunk by ~15 pages | Text mode only | Use page bookmarks for citation |
| **Court Transcript** | Parse bookmarks, no page bookmarks | Vision chunking, batch pages | Vision mode required | Calculate citation from startPage |

### Pipeline Optimization Opportunities

1. **Format Detection at Ingest**: Detect ERE type early and store in job metadata to avoid re-detection
2. **Skip CPYEVREQ/MEDNOMER**: 21% of exhibits are administrative; skip during segment to reduce processing
3. **Vision Batching**: For court transcripts, batch 20-30 pages per vision request to reduce API calls
4. **Page Bookmark Caching**: Store page bookmarks in DynamoDB for fast citation enrichment

### Test Coverage

The Sandefur test files provide comprehensive coverage:

| Scenario | File | Coverage |
|----------|------|----------|
| Large exhibits (400+ pages) | All 3 formats | 17F (437 pages) |
| Single-page exhibits | Raw/Processed | 19F-24F, 34F-42F |
| Complete page bookmark mapping | Raw SSA | 2,049 bookmarks |
| Court transcript handling | Court | 41 exhibits, 0 page bookmarks |
| Mixed record types | All 3 formats | 15 distinct SSA codes |

---

## Related Files

- `app/pdf/lib/bookmark_parser.py` - Bookmark parsing implementation
- `app/pdf/lib/text_extractor.py` - Text extraction with table detection
- `app/pdf/lib/chunker.py` - Exhibit chunking logic
- `app/api/services/extractService.ts` - Text/vision extraction routing
- `app/api/services/assembleService.ts` - Citation enrichment
- `app/api/services/exhibitMatcher.ts` - SSA code → template matching
- `app/api/config/chronology_filtering.yaml` - Section/exhibit filtering rules
- `app/api/config/templates/exhibit_type_mapping.yaml` - SSA code → template mapping

---

## Test Files

Located in `app/api/tests/`:

| File | Format | Size | Section F |
|------|--------|------|-----------|
| `Sandefur_raw_ere.pdf` | Raw SSA | 2,941 pages | 62 exhibits |
| `sandefur_processed.pdf` | Processed | 3,494 pages | 62 exhibits |
| `2024 Court Sandefur Transcript Complete.pdf` | Court Transcript | 3,148 pages | 41 exhibits |
