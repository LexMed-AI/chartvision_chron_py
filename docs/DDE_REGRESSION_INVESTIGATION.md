# DDE Extraction Regression Investigation Report

**Date:** 2024-12-14
**Status:** ROOT CAUSE IDENTIFIED
**Severity:** High - A-Section data (claimant name, MDIs, impairments) not being populated

## Summary

After the ERE API modularization refactor, A-Section (DDE) extraction no longer returns MDIs, impairments, or claimant name. AOD and DLI are correctly extracted. The user reported "This worked yesterday."

## Symptoms

| Field | Expected | Actual |
|-------|----------|--------|
| Claimant Name | Extracted | Missing/Unknown |
| MDIs | Extracted | 0 items |
| Impairments | Extracted | 0 items |
| AOD (Alleged Onset Date) | Extracted | ✅ Working |
| DLI (Date Last Insured) | Extracted | ✅ Working |

## Root Cause Analysis

### Data Flow Trace

**Step 1: DDE Parser Returns**
```python
# dde_parser.py returns:
{
    "fields": {
        "case_metadata": {"claimant_name": "...", "date_of_birth": "..."},
        "medical_impairments": [...],
        ...
    },
    "medicallyDeterminableImpairments": {"established": [...]},  # Top-level
    "determinationHistory": {"initial": {...}, "reconsideration": {...}},  # Top-level
    "extraction_mode": "vision",
    "confidence": 0.85
}
```

**Step 2: job_processors.py Extracts Fields (Line 217)**
```python
dde_result = result.get("fields", {})  # Only gets nested fields, DISCARDS top-level MDI/determination
```

**Step 3: Normalization (Line 222)**
```python
dde_result = normalize_dde_result(dde_result, dde_extraction_mode, dde_confidence)
```

`normalize_dde_result` converts the nested structure to a flat one:
```python
{
    "claimant_name": "...",
    "primary_diagnoses": [...],  # MDIs put here
    "raw_fields": {...}          # Original preserved but NOT used
}
```

**Step 4: Builder Call (Lines 269-274)**
```python
builder.from_dde_result(
    {"fields": dde_result},  # Normalized result wrapped
    case_reference=job_id,
    total_pages=len(segments),
)
```

**Step 5: ChartVisionBuilder.from_dde_result() (chartvision_builder.py:290-292)**
```python
fields = dde_result.get("fields", {})  # Gets flattened result
determination = dde_result.get("determinationHistory", {})  # ❌ EMPTY - discarded at Step 2!
mdi = dde_result.get("medicallyDeterminableImpairments", {})  # ❌ EMPTY - discarded at Step 2!
```

### The Bug

1. **job_processors.py line 217** extracts only `result.get("fields", {})`, discarding the top-level `medicallyDeterminableImpairments` and `determinationHistory` keys
2. **normalize_dde_result** flattens MDIs into `primary_diagnoses` but `from_dde_result` doesn't look for that key
3. **from_dde_result** expects `medicallyDeterminableImpairments` at the top level of `dde_result`, not inside `fields`

## Impact

- **Claimant name**: Extracted to `fields.claimant_name` but lost in normalization path
- **MDIs/Impairments**: Extracted to top-level `medicallyDeterminableImpairments` but discarded at step 2
- **AOD/DLI**: Work because they're in both places (`fields` and normalized result)

## Fix Options

### Option A: Preserve Top-Level Keys (Recommended)
Modify `process_ere_job` to preserve the full parser result before normalization:

```python
# Line 217-222 change from:
dde_result = result.get("fields", {})
dde_result = normalize_dde_result(dde_result, ...)

# To:
raw_dde_result = result  # Keep entire parser output
dde_result = normalize_dde_result(result.get("fields", {}), ...)

# Line 269-274 change from:
builder.from_dde_result({"fields": dde_result}, ...)

# To:
builder.from_dde_result(raw_dde_result, ...)
```

### Option B: Update from_dde_result
Modify `from_dde_result` to also look for MDIs in `fields.primary_diagnoses`.

### Option C: Don't Normalize Before Builder
Pass raw parser result directly to `from_dde_result`, keep normalization only for API response.

## Verification Steps

After fix:
1. Run E2E test with Tull PDF
2. Verify A-Section shows:
   - Claimant name populated
   - MDIs > 0
   - Impairments > 0
3. Verify F-Section still shows 117+ entries

## Files Affected

| File | Issue |
|------|-------|
| `app/api/job_processors.py:217` | Discards top-level MDI/determination |
| `app/api/job_processors.py:269-274` | Passes normalized result instead of raw |
| `app/core/builders/chartvision_builder.py:290-292` | Expects keys that were discarded |

## Timeline

- **Introduced**: During ERE API modularization refactor (2024-12-14)
- **Detected**: Same day during E2E testing
- **Commit**: `894b7e8` introduced `extraction_limits.py` but root cause is in job_processors normalization flow
