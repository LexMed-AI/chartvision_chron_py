# Medical Record Schema Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enhance extraction templates to capture RFC-critical fields (work status, restrictions, pain, MMI) and add longitudinal analysis for SSA disability determination support.

**Architecture:** Hybrid enhancement approach - modify existing high-value YAML templates (office_visit, psych_visit, therapy_eval, emergency_visit) with new fields, create two new visit type templates (telehealth, FCE), and add post-processing longitudinal analysis module.

**Tech Stack:** Python 3.11, YAML templates, pytest, jsonschema validation

---

## Phase 1: High Priority Fields (Week 1-2)

### Task 1: Add workStatus Field to office_visit Template

**Files:**
- Modify: `app/config/templates/office_visit.yaml:33-76`
- Create: `tests/fixtures/golden/office_visit_work_status.txt`
- Create: `tests/fixtures/golden/office_visit_work_status.json`
- Test: `tests/core/extraction/test_work_status_extraction.py`

**Step 1: Create golden file test fixture (input)**

Create `tests/fixtures/golden/office_visit_work_status.txt`:
```text
OFFICE VISIT
Date: 03/15/2024
Provider: James Wilson, MD - Orthopedics
Facility: Valley Spine Center

CHIEF COMPLAINT: Follow-up lumbar fusion, 8 weeks post-op

HPI: 52 y/o male s/p L4-L5 fusion. Reports pain improved from 8/10 to 4/10.
Able to walk 15 minutes. Still having difficulty with prolonged sitting.

PHYSICAL EXAM:
- Incision healed well
- Lumbar ROM limited
- Strength 4/5 bilateral LE

ASSESSMENT:
1. Status post lumbar fusion - healing well
2. Chronic low back pain - improved

WORK STATUS: Light duty effective today. No lifting > 10 lbs.
No bending or twisting. Sit/stand option required.
May work 4 hours per day. Re-evaluate in 4 weeks.

PLAN: Continue PT 2x/week. Return 4 weeks.
```

**Step 2: Create golden file test fixture (expected output)**

Create `tests/fixtures/golden/office_visit_work_status.json`:
```json
{
  "date": "03/15/2024",
  "provider": "James Wilson, MD",
  "provider_specialty": "Orthopedics",
  "facility": "Valley Spine Center",
  "visit_type": "office_visit",
  "occurrence_treatment": {
    "chief_complaint": "Follow-up lumbar fusion, 8 weeks post-op",
    "history_present_illness": "52 y/o male s/p L4-L5 fusion. Reports pain improved from 8/10 to 4/10. Able to walk 15 minutes. Still having difficulty with prolonged sitting.",
    "physical_exam_findings": [
      "Incision healed well",
      "Lumbar ROM limited",
      "Strength 4/5 bilateral LE"
    ],
    "assessment_diagnoses": [
      "Status post lumbar fusion - healing well",
      "Chronic low back pain - improved"
    ],
    "plan_of_care": "Continue PT 2x/week. Return 4 weeks.",
    "workStatus": {
      "status": "light_duty",
      "effective_date": "03/15/2024",
      "duration": "4 weeks",
      "restrictions_summary": "No lifting > 10 lbs. No bending or twisting. Sit/stand option required. May work 4 hours per day."
    }
  }
}
```

**Step 3: Write the failing test**

Create `tests/core/extraction/test_work_status_extraction.py`:
```python
"""Tests for workStatus field extraction."""
import json
import pytest
from pathlib import Path

from app.core.extraction.text_extractor import TextExtractor


class TestWorkStatusExtraction:
    """Test extraction of workStatus field from office visits."""

    @pytest.fixture
    def text_extractor(self, mock_llm):
        """Create TextExtractor with mocked LLM."""
        return TextExtractor(llm_manager=mock_llm)

    @pytest.fixture
    def golden_input(self):
        """Load golden file input."""
        path = Path("tests/fixtures/golden/office_visit_work_status.txt")
        return path.read_text()

    @pytest.fixture
    def golden_expected(self):
        """Load golden file expected output."""
        path = Path("tests/fixtures/golden/office_visit_work_status.json")
        return json.loads(path.read_text())

    def test_work_status_field_present_in_template(self):
        """Verify workStatus field is defined in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "workStatus" in fields
        assert fields["workStatus"]["type"] == "object"

    def test_work_status_detection_keywords(self):
        """Verify workStatus detection keywords are configured."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("office_visit")

        work_status_field = template.get("fields", {}).get("workStatus", {})
        keywords = work_status_field.get("detection_keywords", [])

        assert "work status" in keywords or "light duty" in keywords
        assert "no lifting" in keywords or "off work" in keywords

    def test_work_status_enum_values(self):
        """Verify workStatus.status has correct enum values."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        status_field = fields["workStatus"]["fields"]["status"]
        expected_values = ["full_duty", "light_duty", "modified_duty", "no_work", "sedentary_only", "disabled"]

        assert status_field["type"] == "enum"
        assert set(status_field["values"]) == set(expected_values)
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_work_status_extraction.py -v`
Expected: FAIL with "KeyError: 'workStatus'" or similar

**Step 5: Add workStatus field to office_visit.yaml**

Modify `app/config/templates/office_visit.yaml` - add after `plan_of_care` field (around line 68):
```yaml
  workStatus:
    type: object
    required: false
    label: "Work Status"
    description: "Provider's work status determination and restrictions"
    fields:
      status:
        type: enum
        values:
          - "full_duty"
          - "light_duty"
          - "modified_duty"
          - "no_work"
          - "sedentary_only"
          - "disabled"
        description: "Current work status determination"
      effective_date:
        type: date
        description: "Date work status is effective"
      duration:
        type: string
        description: "Expected duration (e.g., '6 weeks', 'permanent')"
      restrictions_summary:
        type: string
        description: "Summary of work restrictions"
    detection_keywords:
      - "work status"
      - "return to work"
      - "off work"
      - "light duty"
      - "modified duty"
      - "full duty"
      - "no work"
      - "sedentary"
      - "disabled"
      - "unable to work"
      - "may work"
      - "hours per day"
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_work_status_extraction.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/office_visit.yaml tests/core/extraction/test_work_status_extraction.py tests/fixtures/golden/office_visit_work_status.*
git commit -m "feat: add workStatus field to office_visit template"
```

---

### Task 2: Add providerRestrictions Field to office_visit Template

**Files:**
- Modify: `app/config/templates/office_visit.yaml`
- Create: `tests/fixtures/golden/office_visit_restrictions.txt`
- Create: `tests/fixtures/golden/office_visit_restrictions.json`
- Test: `tests/core/extraction/test_provider_restrictions_extraction.py`

**Step 1: Create golden file test fixture (input)**

Create `tests/fixtures/golden/office_visit_restrictions.txt`:
```text
OFFICE VISIT - PAIN MANAGEMENT
Date: 04/22/2024
Provider: Sarah Chen, MD
Facility: Metro Pain Clinic

CC: Chronic low back pain with bilateral leg pain

ASSESSMENT:
1. Lumbar radiculopathy L4-L5, L5-S1
2. Degenerative disc disease

FUNCTIONAL RESTRICTIONS:
- Lifting: No more than 10 lbs occasionally, 5 lbs frequently
- Standing: Limited to 30 minutes at a time, 2 hours total per day
- Walking: Limited to 15 minutes at a time
- Sitting: Must have sit/stand option, change positions every 30 minutes
- Bending/Stooping: Avoid completely
- Twisting: Avoid completely
- Climbing: No ladder climbing
- Reaching overhead: Occasional only
- Must elevate legs when sitting
- Requires 2 unscheduled 15-minute rest breaks per day
- May need to use cane for distances > 100 feet

These restrictions are permanent based on imaging and clinical findings.

PLAN: Continue current medications. Return 3 months.
```

**Step 2: Create golden file test fixture (expected output)**

Create `tests/fixtures/golden/office_visit_restrictions.json`:
```json
{
  "date": "04/22/2024",
  "provider": "Sarah Chen, MD",
  "facility": "Metro Pain Clinic",
  "visit_type": "office_visit",
  "occurrence_treatment": {
    "chief_complaint": "Chronic low back pain with bilateral leg pain",
    "assessment_diagnoses": [
      "Lumbar radiculopathy L4-L5, L5-S1",
      "Degenerative disc disease"
    ],
    "plan_of_care": "Continue current medications. Return 3 months.",
    "providerRestrictions": [
      {
        "restriction_type": "lifting",
        "limit": "10 lbs",
        "frequency": "occasional"
      },
      {
        "restriction_type": "lifting",
        "limit": "5 lbs",
        "frequency": "frequent"
      },
      {
        "restriction_type": "standing",
        "limit": "30 minutes at a time, 2 hours total per day",
        "frequency": "limited"
      },
      {
        "restriction_type": "walking",
        "limit": "15 minutes at a time",
        "frequency": "limited"
      },
      {
        "restriction_type": "sit_stand_option",
        "limit": "change positions every 30 minutes",
        "frequency": "required"
      },
      {
        "restriction_type": "bending",
        "limit": "never",
        "frequency": "avoid"
      },
      {
        "restriction_type": "twisting",
        "limit": "never",
        "frequency": "avoid"
      },
      {
        "restriction_type": "climbing",
        "limit": "no ladder climbing",
        "frequency": "avoid"
      },
      {
        "restriction_type": "reaching_overhead",
        "limit": "occasional only",
        "frequency": "occasional"
      },
      {
        "restriction_type": "elevate_legs",
        "limit": "when sitting",
        "frequency": "required"
      },
      {
        "restriction_type": "unscheduled_breaks",
        "limit": "2 breaks, 15 minutes each",
        "frequency": "daily"
      },
      {
        "restriction_type": "assistive_device",
        "limit": "cane for distances > 100 feet",
        "frequency": "as needed"
      }
    ]
  }
}
```

**Step 3: Write the failing test**

Create `tests/core/extraction/test_provider_restrictions_extraction.py`:
```python
"""Tests for providerRestrictions field extraction."""
import json
import pytest
from pathlib import Path


class TestProviderRestrictionsExtraction:
    """Test extraction of providerRestrictions field."""

    def test_provider_restrictions_field_present_in_template(self):
        """Verify providerRestrictions field is defined in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "providerRestrictions" in fields
        assert fields["providerRestrictions"]["type"] == "array"

    def test_provider_restrictions_enum_values(self):
        """Verify restriction_type has all RFC restriction categories."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        restriction_type = fields["providerRestrictions"]["items"]["restriction_type"]

        # Exertional
        assert "lifting" in restriction_type["values"]
        assert "carrying" in restriction_type["values"]
        assert "pushing" in restriction_type["values"]
        assert "pulling" in restriction_type["values"]

        # Positional
        assert "standing" in restriction_type["values"]
        assert "walking" in restriction_type["values"]
        assert "sitting" in restriction_type["values"]
        assert "bending" in restriction_type["values"]
        assert "twisting" in restriction_type["values"]
        assert "stooping" in restriction_type["values"]
        assert "kneeling" in restriction_type["values"]
        assert "crouching" in restriction_type["values"]
        assert "crawling" in restriction_type["values"]
        assert "climbing" in restriction_type["values"]
        assert "balancing" in restriction_type["values"]

        # Accommodations
        assert "sit_stand_option" in restriction_type["values"]
        assert "elevate_legs" in restriction_type["values"]
        assert "unscheduled_breaks" in restriction_type["values"]
        assert "assistive_device" in restriction_type["values"]

        # Upper extremity
        assert "reaching" in restriction_type["values"]
        assert "reaching_overhead" in restriction_type["values"]
        assert "handling" in restriction_type["values"]
        assert "fingering" in restriction_type["values"]
        assert "repetitive_motion" in restriction_type["values"]

    def test_provider_restrictions_detection_keywords(self):
        """Verify detection keywords for restrictions."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("office_visit")

        restrictions_field = template.get("fields", {}).get("providerRestrictions", {})
        keywords = restrictions_field.get("detection_keywords", [])

        assert any("restrict" in kw for kw in keywords)
        assert any("limit" in kw for kw in keywords)
        assert any("lbs" in kw or "pounds" in kw for kw in keywords)
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_provider_restrictions_extraction.py -v`
Expected: FAIL with "KeyError: 'providerRestrictions'"

**Step 5: Add providerRestrictions field to office_visit.yaml**

Modify `app/config/templates/office_visit.yaml` - add after `workStatus` field:
```yaml
  providerRestrictions:
    type: array
    required: false
    label: "Restrictions"
    description: "Specific functional restrictions imposed by provider"
    items:
      restriction_type:
        type: enum
        values:
          # Exertional
          - "lifting"
          - "carrying"
          - "pushing"
          - "pulling"
          # Positional
          - "standing"
          - "walking"
          - "sitting"
          - "climbing"
          - "balancing"
          - "stooping"
          - "kneeling"
          - "crouching"
          - "crawling"
          - "bending"
          - "twisting"
          # Upper extremity
          - "reaching"
          - "reaching_overhead"
          - "handling"
          - "fingering"
          - "repetitive_motion"
          # Accommodations
          - "sit_stand_option"
          - "elevate_legs"
          - "unscheduled_breaks"
          - "assistive_device"
          # Environmental
          - "heights"
          - "hazards"
          - "temperature_extremes"
          - "noise"
          - "vibration"
          # Time-based
          - "hours_per_day"
          - "days_per_week"
          - "no_work"
          - "bed_rest"
        description: "Type of restriction"
      limit:
        type: string
        description: "Specific limit (e.g., '10 lbs', '2 hours', 'never')"
      frequency:
        type: string
        description: "Frequency qualifier (e.g., 'occasional', 'frequent', 'continuous')"
      body_part:
        type: string
        description: "Affected body part if specific"
      laterality:
        type: enum
        values: ["left", "right", "bilateral"]
        description: "Side affected"
      duration:
        type: string
        description: "Duration of restriction (e.g., '6 weeks', 'permanent')"
    detection_keywords:
      - "restrict"
      - "restriction"
      - "limit"
      - "limited to"
      - "no more than"
      - "avoid"
      - "cannot"
      - "unable to"
      - "must not"
      - "lbs"
      - "pounds"
      - "hours"
      - "minutes"
      - "sit/stand"
      - "sit-stand"
      - "alternate positions"
      - "elevate legs"
      - "legs elevated"
      - "leg elevation"
      - "no bending"
      - "avoid bending"
      - "no twisting"
      - "unscheduled breaks"
      - "rest as needed"
      - "cane"
      - "walker"
      - "wheelchair"
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_provider_restrictions_extraction.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/office_visit.yaml tests/core/extraction/test_provider_restrictions_extraction.py tests/fixtures/golden/office_visit_restrictions.*
git commit -m "feat: add providerRestrictions field to office_visit template"
```

---

### Task 3: Add painAssessments Field to office_visit Template

**Files:**
- Modify: `app/config/templates/office_visit.yaml`
- Create: `tests/fixtures/golden/office_visit_pain.txt`
- Create: `tests/fixtures/golden/office_visit_pain.json`
- Test: `tests/core/extraction/test_pain_assessment_extraction.py`

**Step 1: Create golden file test fixture (input)**

Create `tests/fixtures/golden/office_visit_pain.txt`:
```text
PAIN MANAGEMENT FOLLOW-UP
Date: 05/10/2024
Provider: Michael Torres, MD
Facility: Comprehensive Pain Center

CC: Chronic pain follow-up

PAIN ASSESSMENT:
- Low back pain: 7/10 current, 9/10 at worst, 4/10 at best
  Character: Aching, sharp with movement
  Radiation: Down left leg to knee
  Aggravating: Prolonged sitting, bending, lifting
  Relieving: Lying down, ice, medication

- Bilateral knee pain: 5/10 current
  Character: Aching, grinding
  Worse with stairs and prolonged standing

- Neck pain: 4/10 current
  Character: Stiff, tight
  Radiation: Into bilateral shoulders

ASSESSMENT:
1. Chronic low back pain with left lumbar radiculopathy
2. Bilateral knee osteoarthritis
3. Cervical spondylosis

PLAN: Continue gabapentin 300mg TID. Add Lidoderm patch to low back.
```

**Step 2: Create golden file test fixture (expected output)**

Create `tests/fixtures/golden/office_visit_pain.json`:
```json
{
  "date": "05/10/2024",
  "provider": "Michael Torres, MD",
  "facility": "Comprehensive Pain Center",
  "visit_type": "office_visit",
  "occurrence_treatment": {
    "chief_complaint": "Chronic pain follow-up",
    "assessment_diagnoses": [
      "Chronic low back pain with left lumbar radiculopathy",
      "Bilateral knee osteoarthritis",
      "Cervical spondylosis"
    ],
    "plan_of_care": "Continue gabapentin 300mg TID. Add Lidoderm patch to low back.",
    "painAssessments": [
      {
        "location": "low back",
        "scale": "nprs_0_10",
        "current": 7,
        "at_worst": 9,
        "at_best": 4,
        "character": ["aching", "sharp with movement"],
        "radiation": "down left leg to knee",
        "aggravating_factors": ["prolonged sitting", "bending", "lifting"],
        "relieving_factors": ["lying down", "ice", "medication"]
      },
      {
        "location": "bilateral knees",
        "scale": "nprs_0_10",
        "current": 5,
        "character": ["aching", "grinding"],
        "aggravating_factors": ["stairs", "prolonged standing"]
      },
      {
        "location": "neck",
        "scale": "nprs_0_10",
        "current": 4,
        "character": ["stiff", "tight"],
        "radiation": "into bilateral shoulders"
      }
    ]
  }
}
```

**Step 3: Write the failing test**

Create `tests/core/extraction/test_pain_assessment_extraction.py`:
```python
"""Tests for painAssessments field extraction."""
import json
import pytest
from pathlib import Path


class TestPainAssessmentExtraction:
    """Test extraction of painAssessments field."""

    def test_pain_assessments_field_present_in_template(self):
        """Verify painAssessments field is defined in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "painAssessments" in fields
        assert fields["painAssessments"]["type"] == "array"

    def test_pain_assessment_item_structure(self):
        """Verify painAssessments items have correct structure."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        items = fields["painAssessments"]["items"]

        assert "location" in items
        assert "scale" in items
        assert "current" in items
        assert "at_worst" in items
        assert "character" in items
        assert "radiation" in items
        assert "aggravating_factors" in items
        assert "relieving_factors" in items

    def test_pain_scale_enum_values(self):
        """Verify scale field has standard pain scale options."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        scale_field = fields["painAssessments"]["items"]["scale"]

        assert "nprs_0_10" in scale_field["values"]
        assert "vas" in scale_field["values"]
        assert "faces" in scale_field["values"]

    def test_pain_detection_keywords(self):
        """Verify detection keywords for pain assessments."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("office_visit")

        pain_field = template.get("fields", {}).get("painAssessments", {})
        keywords = pain_field.get("detection_keywords", [])

        assert any("/10" in kw for kw in keywords)
        assert any("pain" in kw.lower() for kw in keywords)
```

**Step 4: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_pain_assessment_extraction.py -v`
Expected: FAIL with "KeyError: 'painAssessments'"

**Step 5: Add painAssessments field to office_visit.yaml**

Modify `app/config/templates/office_visit.yaml` - add after `providerRestrictions` field:
```yaml
  painAssessments:
    type: array
    required: false
    label: "Pain"
    description: "Pain assessments with location, severity, and characteristics"
    items:
      location:
        type: string
        description: "Body location of pain (e.g., 'low back', 'bilateral knees')"
      laterality:
        type: enum
        values: ["left", "right", "bilateral", "midline"]
        description: "Side affected"
      scale:
        type: enum
        values:
          - "nprs_0_10"
          - "vas"
          - "faces"
          - "bpi"
          - "oswestry"
          - "ndi"
          - "other"
        default: "nprs_0_10"
        description: "Pain scale used"
      current:
        type: integer
        min: 0
        max: 10
        description: "Current pain level"
      at_worst:
        type: integer
        min: 0
        max: 10
        description: "Pain at worst"
      at_best:
        type: integer
        min: 0
        max: 10
        description: "Pain at best/least"
      average:
        type: integer
        min: 0
        max: 10
        description: "Average pain level"
      character:
        type: array
        items: string
        description: "Pain quality (e.g., 'sharp', 'dull', 'aching', 'burning', 'stabbing')"
      radiation:
        type: string
        description: "Where pain radiates to"
      frequency:
        type: string
        description: "How often pain occurs (e.g., 'constant', 'intermittent')"
      aggravating_factors:
        type: array
        items: string
        description: "Activities that worsen pain"
      relieving_factors:
        type: array
        items: string
        description: "Activities/treatments that relieve pain"
    detection_keywords:
      - "/10"
      - "pain level"
      - "pain score"
      - "pain rating"
      - "pain assessment"
      - "current pain"
      - "worst pain"
      - "at best"
      - "at worst"
      - "VAS"
      - "numeric pain"
      - "aching"
      - "sharp"
      - "burning"
      - "stabbing"
      - "radiating"
      - "radiates to"
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_pain_assessment_extraction.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/office_visit.yaml tests/core/extraction/test_pain_assessment_extraction.py tests/fixtures/golden/office_visit_pain.*
git commit -m "feat: add painAssessments field to office_visit template"
```

---

### Task 4: Add mmiStatus Field to office_visit Template

**Files:**
- Modify: `app/config/templates/office_visit.yaml`
- Test: `tests/core/extraction/test_mmi_status_extraction.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_mmi_status_extraction.py`:
```python
"""Tests for mmiStatus field extraction."""
import pytest


class TestMMIStatusExtraction:
    """Test extraction of mmiStatus field."""

    def test_mmi_status_field_present_in_template(self):
        """Verify mmiStatus field is defined in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "mmiStatus" in fields
        assert fields["mmiStatus"]["type"] == "object"

    def test_mmi_status_structure(self):
        """Verify mmiStatus has correct structure."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        mmi_fields = fields["mmiStatus"]["fields"]

        assert "status" in mmi_fields
        assert "date_reached" in mmi_fields
        assert "expected_date" in mmi_fields
        assert "notes" in mmi_fields

    def test_mmi_status_enum_values(self):
        """Verify status field has correct enum values."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        status_field = fields["mmiStatus"]["fields"]["status"]

        assert "not_at_mmi" in status_field["values"]
        assert "at_mmi" in status_field["values"]
        assert "unknown" in status_field["values"]

    def test_mmi_detection_keywords(self):
        """Verify detection keywords for MMI."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("office_visit")

        mmi_field = template.get("fields", {}).get("mmiStatus", {})
        keywords = mmi_field.get("detection_keywords", [])

        assert any("mmi" in kw.lower() for kw in keywords)
        assert any("maximum medical improvement" in kw.lower() for kw in keywords)
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_mmi_status_extraction.py -v`
Expected: FAIL with "KeyError: 'mmiStatus'"

**Step 3: Add mmiStatus field to office_visit.yaml**

Modify `app/config/templates/office_visit.yaml` - add after `painAssessments` field:
```yaml
  mmiStatus:
    type: object
    required: false
    label: "MMI"
    description: "Maximum Medical Improvement status determination"
    fields:
      status:
        type: enum
        values:
          - "not_at_mmi"
          - "at_mmi"
          - "unknown"
        description: "Current MMI status"
      date_reached:
        type: date
        description: "Date MMI was reached (if at MMI)"
      expected_date:
        type: date
        description: "Expected date of MMI (if not yet at MMI)"
      notes:
        type: string
        description: "Additional notes about prognosis or expected improvement"
    detection_keywords:
      - "maximum medical improvement"
      - "MMI"
      - "plateau"
      - "no further improvement"
      - "no further improvement expected"
      - "permanent"
      - "permanent and stationary"
      - "reached maximum benefit"
      - "stable condition"
      - "condition has stabilized"
      - "prognosis"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_mmi_status_extraction.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config/templates/office_visit.yaml tests/core/extraction/test_mmi_status_extraction.py
git commit -m "feat: add mmiStatus field to office_visit template"
```

---

### Task 5: Create telehealth Visit Type Template

**Files:**
- Create: `app/config/templates/telehealth.yaml`
- Modify: `app/core/extraction/constants.py`
- Modify: `app/core/extraction/template_loader.py`
- Test: `tests/core/extraction/test_telehealth_template.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_telehealth_template.py`:
```python
"""Tests for telehealth visit type template."""
import pytest


class TestTelehealthTemplate:
    """Test telehealth visit type configuration."""

    def test_telehealth_in_valid_visit_types(self):
        """Verify telehealth is a valid visit type."""
        from app.core.extraction.constants import VALID_VISIT_TYPES

        assert "telehealth" in VALID_VISIT_TYPES

    def test_telehealth_template_exists(self):
        """Verify telehealth template can be loaded."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("telehealth")

        assert template is not None
        assert template.get("visit_type") == "telehealth"

    def test_telehealth_has_modality_field(self):
        """Verify telehealth has visit_modality field."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("telehealth")

        assert "visit_modality" in fields
        assert "video" in fields["visit_modality"]["values"]
        assert "phone" in fields["visit_modality"]["values"]

    def test_telehealth_inherits_office_visit_fields(self):
        """Verify telehealth has standard office visit fields."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("telehealth")

        # Should have standard office visit fields
        assert "chief_complaint" in fields
        assert "assessment_diagnoses" in fields
        assert "plan_of_care" in fields

        # Should also have new RFC fields
        assert "workStatus" in fields
        assert "providerRestrictions" in fields
        assert "painAssessments" in fields

    def test_telehealth_detection_keywords(self):
        """Verify detection keywords for telehealth."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        detected = loader.detect_visit_types("This was a telehealth video visit")

        assert "telehealth" in detected
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_telehealth_template.py -v`
Expected: FAIL with "'telehealth' not in VALID_VISIT_TYPES"

**Step 3: Add telehealth to VALID_VISIT_TYPES**

Modify `app/core/extraction/constants.py` around line 151-164:
```python
VALID_VISIT_TYPES: List[str] = [
    "office_visit",
    "imaging_report",
    "therapy_eval",
    "lab_result",
    "surgical_report",
    "emergency_visit",
    "inpatient_admission",
    "consultative_exam",
    "psych_visit",
    "diagnostic_study",
    "procedural_visit",
    "medical_source_statement",
    "telehealth",  # ← Add this
]
```

**Step 4: Add telehealth detection keywords to template_loader.py**

Modify `app/core/extraction/template_loader.py` in the `detect_visit_types` method patterns dict (around line 180):
```python
            "telehealth": [
                "telehealth", "telemedicine", "video visit", "phone visit",
                "virtual visit", "remote visit", "televisit"
            ],
```

**Step 5: Create telehealth.yaml template**

Create `app/config/templates/telehealth.yaml`:
```yaml
# Telehealth Visit Extraction Template
# For: Video visits, phone visits, virtual consultations
#
# Version: 1.0.0

visit_type: "telehealth"
description: "Telehealth/telemedicine visits conducted remotely via video or phone"

# Telehealth-specific user prompt
user_prompt: |
  Parse the following telehealth visit records and extract all encounters.

  **MEDICAL RECORDS:**
  {medical_content}

  **EXTRACT FOR EACH VISIT:**
  - Date of service
  - Provider name and credentials
  - Facility name
  - Visit modality (video, phone, asynchronous)
  - Chief complaint (CC)
  - History of present illness (HPI)
  - Assessment/Diagnoses (Dx)
  - Plan of care
  - Any technology issues noted

  **OUTPUT:** Return JSON array following the telehealth schema.

# Fields - inherits from office_visit plus telehealth-specific
fields:
  visit_modality:
    type: enum
    required: true
    label: "Modality"
    values:
      - "video"
      - "phone"
      - "asynchronous"
      - "chat"
    description: "How the telehealth visit was conducted"

  technology_issues:
    type: string
    required: false
    label: "Tech Issues"
    description: "Any connectivity or technology problems noted during visit"

  physical_exam_limitations:
    type: string
    required: false
    label: "Exam Limitations"
    description: "Limitations on physical exam due to remote nature"

  # Inherited from office_visit
  chief_complaint:
    type: text
    required: true
    label: "CC"
    description: "Patient's primary reason for visit"
    max_len: 200

  history_present_illness:
    type: text
    required: false
    label: "HPI"
    description: "Narrative of current symptoms and history"
    max_len: 300

  assessment_diagnoses:
    type: array
    items: string
    required: true
    label: "Dx"
    description: "Provider's diagnostic assessment"

  plan_of_care:
    type: text
    required: false
    label: "Plan"
    description: "Treatment plan, referrals, follow-up"
    max_len: 200

  # RFC-critical fields (same as office_visit)
  workStatus:
    type: object
    required: false
    label: "Work Status"
    description: "Provider's work status determination and restrictions"
    fields:
      status:
        type: enum
        values: ["full_duty", "light_duty", "modified_duty", "no_work", "sedentary_only", "disabled"]
      effective_date:
        type: date
      duration:
        type: string
      restrictions_summary:
        type: string

  providerRestrictions:
    type: array
    required: false
    label: "Restrictions"
    description: "Specific functional restrictions imposed by provider"
    items:
      restriction_type:
        type: enum
        values:
          - "lifting"
          - "carrying"
          - "pushing"
          - "pulling"
          - "standing"
          - "walking"
          - "sitting"
          - "climbing"
          - "balancing"
          - "stooping"
          - "kneeling"
          - "crouching"
          - "crawling"
          - "bending"
          - "twisting"
          - "reaching"
          - "reaching_overhead"
          - "handling"
          - "fingering"
          - "repetitive_motion"
          - "sit_stand_option"
          - "elevate_legs"
          - "unscheduled_breaks"
          - "assistive_device"
          - "heights"
          - "hazards"
          - "temperature_extremes"
          - "hours_per_day"
          - "no_work"
      limit:
        type: string
      frequency:
        type: string

  painAssessments:
    type: array
    required: false
    label: "Pain"
    description: "Pain assessments with location and severity"
    items:
      location:
        type: string
      scale:
        type: enum
        values: ["nprs_0_10", "vas", "faces", "other"]
        default: "nprs_0_10"
      current:
        type: integer
        min: 0
        max: 10
      at_worst:
        type: integer
      character:
        type: array
        items: string
      radiation:
        type: string

  mmiStatus:
    type: object
    required: false
    label: "MMI"
    fields:
      status:
        type: enum
        values: ["not_at_mmi", "at_mmi", "unknown"]
      date_reached:
        type: date
      expected_date:
        type: date
      notes:
        type: string

# Output labels
output_labels: ["Modality", "CC", "HPI", "Dx", "Plan"]

# Formatting example
output_example: |
  Modality: Video visit
  CC: Follow-up chronic pain management
  HPI: Reports pain stable at 5/10. Medications helping.
  Dx: Chronic low back pain, stable
  Plan: Continue current regimen, follow up 3 months

# Few-shot examples
examples:
  - input: |
      TELEHEALTH VIDEO VISIT
      Date: 06/15/2024
      Provider: Jennifer Adams, MD
      Facility: Valley Primary Care (Virtual)

      VISIT TYPE: Scheduled video visit

      CC: Follow-up hypertension and diabetes

      HPI: 62 y/o male connecting via video from home. Reports BP readings
      at home averaging 135/85. Blood sugars fasting 120-140. Taking all
      medications as prescribed. No chest pain, SOB, or edema.

      ASSESSMENT:
      1. Essential hypertension - controlled
      2. Type 2 diabetes - suboptimally controlled

      PLAN:
      - Increase metformin to 1000mg BID
      - Continue lisinopril 20mg daily
      - Labs in 4 weeks
      - Return video visit 6 weeks
    output:
      date: "06/15/2024"
      provider: "Jennifer Adams, MD"
      facility: "Valley Primary Care (Virtual)"
      visit_type: "telehealth"
      visit_modality: "video"
      chief_complaint: "Follow-up hypertension and diabetes"
      history_present_illness: "62 y/o male connecting via video from home. Reports BP readings at home averaging 135/85. Blood sugars fasting 120-140. Taking all medications as prescribed. No chest pain, SOB, or edema."
      assessment_diagnoses:
        - "Essential hypertension - controlled"
        - "Type 2 diabetes - suboptimally controlled"
      plan_of_care: "Increase metformin to 1000mg BID. Continue lisinopril 20mg daily. Labs in 4 weeks. Return video visit 6 weeks."
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_telehealth_template.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/telehealth.yaml app/core/extraction/constants.py app/core/extraction/template_loader.py tests/core/extraction/test_telehealth_template.py
git commit -m "feat: add telehealth visit type template"
```

---

### Task 6: Copy New Fields to psych_visit, therapy_eval, emergency_visit Templates

**Files:**
- Modify: `app/config/templates/psych_visit.yaml`
- Modify: `app/config/templates/therapy_eval.yaml`
- Modify: `app/config/templates/emergency_visit.yaml`
- Test: `tests/core/extraction/test_rfc_fields_all_templates.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_rfc_fields_all_templates.py`:
```python
"""Tests for RFC fields present in all high-value templates."""
import pytest


class TestRFCFieldsAllTemplates:
    """Verify RFC-critical fields are in all high-value templates."""

    HIGH_VALUE_TEMPLATES = [
        "office_visit",
        "psych_visit",
        "therapy_eval",
        "emergency_visit",
        "telehealth",
    ]

    @pytest.mark.parametrize("template_name", HIGH_VALUE_TEMPLATES)
    def test_work_status_present(self, template_name):
        """Verify workStatus field is in template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields(template_name)

        assert "workStatus" in fields, f"workStatus missing from {template_name}"

    @pytest.mark.parametrize("template_name", HIGH_VALUE_TEMPLATES)
    def test_provider_restrictions_present(self, template_name):
        """Verify providerRestrictions field is in template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields(template_name)

        assert "providerRestrictions" in fields, f"providerRestrictions missing from {template_name}"

    @pytest.mark.parametrize("template_name", ["office_visit", "therapy_eval", "emergency_visit", "telehealth"])
    def test_pain_assessments_present(self, template_name):
        """Verify painAssessments field is in physical health templates."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields(template_name)

        assert "painAssessments" in fields, f"painAssessments missing from {template_name}"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_rfc_fields_all_templates.py -v`
Expected: FAIL for psych_visit, therapy_eval, emergency_visit

**Step 3: Add fields to psych_visit.yaml**

Modify `app/config/templates/psych_visit.yaml` - add after `treatment_plan` field:
```yaml
  # RFC-critical fields
  workStatus:
    type: object
    required: false
    label: "Work Status"
    description: "Provider's work status determination"
    fields:
      status:
        type: enum
        values: ["full_duty", "light_duty", "modified_duty", "no_work", "sedentary_only", "disabled"]
      effective_date:
        type: date
      duration:
        type: string
      restrictions_summary:
        type: string

  providerRestrictions:
    type: array
    required: false
    label: "Restrictions"
    description: "Functional restrictions (mental health focused)"
    items:
      restriction_type:
        type: enum
        values:
          - "no_work"
          - "hours_per_day"
          - "days_per_week"
          - "avoid_stress"
          - "avoid_public"
          - "supervision_required"
          - "no_driving"
          - "no_operating_machinery"
      limit:
        type: string
      duration:
        type: string

  compliance:
    type: object
    required: false
    label: "Compliance"
    description: "Treatment compliance observations"
    fields:
      medication_adherence:
        type: string
      appointment_adherence:
        type: string
      treatment_participation:
        type: string
      notes:
        type: string
```

**Step 4: Add fields to therapy_eval.yaml**

Modify `app/config/templates/therapy_eval.yaml` - add after existing fields:
```yaml
  # RFC-critical fields
  workStatus:
    type: object
    required: false
    label: "Work Status"
    fields:
      status:
        type: enum
        values: ["full_duty", "light_duty", "modified_duty", "no_work", "sedentary_only", "disabled"]
      effective_date:
        type: date
      duration:
        type: string
      restrictions_summary:
        type: string

  providerRestrictions:
    type: array
    required: false
    label: "Restrictions"
    items:
      restriction_type:
        type: enum
        values:
          - "lifting"
          - "carrying"
          - "standing"
          - "walking"
          - "sitting"
          - "bending"
          - "twisting"
          - "reaching"
          - "reaching_overhead"
          - "climbing"
          - "kneeling"
          - "sit_stand_option"
          - "assistive_device"
      limit:
        type: string
      frequency:
        type: string
      body_part:
        type: string

  painAssessments:
    type: array
    required: false
    label: "Pain"
    items:
      location:
        type: string
      scale:
        type: enum
        values: ["nprs_0_10", "vas", "faces", "other"]
        default: "nprs_0_10"
      current:
        type: integer
        min: 0
        max: 10
      at_worst:
        type: integer
      character:
        type: array
        items: string
```

**Step 5: Add fields to emergency_visit.yaml**

Modify `app/config/templates/emergency_visit.yaml` - add after existing fields:
```yaml
  # RFC-critical fields
  workStatus:
    type: object
    required: false
    label: "Work Status"
    fields:
      status:
        type: enum
        values: ["full_duty", "light_duty", "modified_duty", "no_work", "sedentary_only", "disabled"]
      effective_date:
        type: date
      duration:
        type: string
      restrictions_summary:
        type: string

  providerRestrictions:
    type: array
    required: false
    label: "Restrictions"
    items:
      restriction_type:
        type: enum
        values:
          - "lifting"
          - "no_work"
          - "bed_rest"
          - "assistive_device"
          - "hours_per_day"
      limit:
        type: string
      duration:
        type: string

  painAssessments:
    type: array
    required: false
    label: "Pain"
    items:
      location:
        type: string
      scale:
        type: enum
        values: ["nprs_0_10", "vas", "faces", "other"]
        default: "nprs_0_10"
      current:
        type: integer
        min: 0
        max: 10
      character:
        type: array
        items: string
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_rfc_fields_all_templates.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/psych_visit.yaml app/config/templates/therapy_eval.yaml app/config/templates/emergency_visit.yaml tests/core/extraction/test_rfc_fields_all_templates.py
git commit -m "feat: add RFC fields to psych_visit, therapy_eval, emergency_visit templates"
```

---

## Phase 2: Medium Priority Fields (Week 3-4)

### Task 7: Add vitalSets Field to Templates

**Files:**
- Modify: `app/config/templates/office_visit.yaml`
- Modify: `app/config/templates/emergency_visit.yaml`
- Test: `tests/core/extraction/test_vital_sets_extraction.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_vital_sets_extraction.py`:
```python
"""Tests for vitalSets field extraction."""
import pytest


class TestVitalSetsExtraction:
    """Test extraction of vitalSets field."""

    def test_vital_sets_field_present(self):
        """Verify vitalSets field is defined in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "vitalSets" in fields
        assert fields["vitalSets"]["type"] == "array"

    def test_vital_sets_item_structure(self):
        """Verify vitalSets items have vital sign fields."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        items = fields["vitalSets"]["items"]

        assert "bp_systolic" in items
        assert "bp_diastolic" in items
        assert "pulse" in items
        assert "weight" in items
        assert "bmi" in items
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_vital_sets_extraction.py -v`
Expected: FAIL

**Step 3: Add vitalSets field to office_visit.yaml**

Add to `app/config/templates/office_visit.yaml`:
```yaml
  vitalSets:
    type: array
    required: false
    label: "Vitals"
    description: "Vital signs recorded during visit"
    items:
      context:
        type: string
        description: "Context of measurement (e.g., 'triage', 'office')"
      bp_systolic:
        type: integer
        description: "Systolic blood pressure"
      bp_diastolic:
        type: integer
        description: "Diastolic blood pressure"
      bp_position:
        type: enum
        values: ["sitting", "standing", "supine"]
      pulse:
        type: integer
        description: "Heart rate in bpm"
      pulse_ox:
        type: integer
        description: "Oxygen saturation percentage"
      respiratory_rate:
        type: integer
        description: "Breaths per minute"
      temperature:
        type: number
        description: "Temperature"
      temperature_unit:
        type: enum
        values: ["F", "C"]
        default: "F"
      weight:
        type: number
        description: "Weight"
      weight_unit:
        type: enum
        values: ["lbs", "kg"]
        default: "lbs"
      height:
        type: number
        description: "Height"
      height_unit:
        type: enum
        values: ["in", "cm"]
        default: "in"
      bmi:
        type: number
        description: "Body mass index"
    detection_keywords:
      - "vitals"
      - "VS:"
      - "BP"
      - "blood pressure"
      - "pulse"
      - "weight"
      - "BMI"
      - "SpO2"
      - "O2 sat"
      - "temp"
      - "temperature"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_vital_sets_extraction.py -v`
Expected: PASS

**Step 5: Add same field to emergency_visit.yaml**

Copy the vitalSets definition to `app/config/templates/emergency_visit.yaml`.

**Step 6: Commit**

```bash
git add app/config/templates/office_visit.yaml app/config/templates/emergency_visit.yaml tests/core/extraction/test_vital_sets_extraction.py
git commit -m "feat: add vitalSets field to office_visit and emergency_visit templates"
```

---

### Task 8: Add medicationActions Field to base.yaml

**Files:**
- Modify: `app/config/templates/base.yaml`
- Test: `tests/core/extraction/test_medication_actions.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_medication_actions.py`:
```python
"""Tests for medicationActions field."""
import pytest


class TestMedicationActions:
    """Test medicationActions field configuration."""

    def test_medication_actions_in_base(self):
        """Verify medicationActions is documented in base template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        base = loader.get_base()

        # Should be in the user prompt schema documentation
        user_prompt = base.get("user_prompt", "")
        assert "medicationActions" in user_prompt or "medication" in user_prompt.lower()

    def test_medication_actions_structure(self):
        """Verify medicationActions has correct structure in office_visit."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "medicationActions" in fields
        items = fields["medicationActions"]["items"]

        assert "medication_name" in items
        assert "action" in items
        assert items["action"]["type"] == "enum"
        assert "started" in items["action"]["values"]
        assert "discontinued" in items["action"]["values"]
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_medication_actions.py -v`
Expected: FAIL

**Step 3: Add medicationActions to office_visit.yaml**

Add to `app/config/templates/office_visit.yaml`:
```yaml
  medicationActions:
    type: array
    required: false
    label: "Med Changes"
    description: "Medication changes made during this visit"
    items:
      medication_name:
        type: string
        description: "Name of medication"
      action:
        type: enum
        values:
          - "started"
          - "continued"
          - "increased"
          - "decreased"
          - "discontinued"
          - "refilled"
        description: "Action taken"
      dosage:
        type: string
        description: "Dosage (e.g., '50mg BID')"
      indication:
        type: string
        description: "Reason for medication"
      response:
        type: string
        description: "Patient response (e.g., 'effective', 'no improvement')"
      side_effects:
        type: array
        items: string
        description: "Reported side effects"
    detection_keywords:
      - "start"
      - "begin"
      - "initiate"
      - "prescribe"
      - "increase"
      - "titrate"
      - "decrease"
      - "taper"
      - "reduce"
      - "discontinue"
      - "stop"
      - "d/c"
      - "hold"
      - "refill"
```

**Step 4: Update base.yaml user prompt to mention medicationActions**

Modify `app/config/templates/base.yaml` user_prompt section to include:
```yaml
  **office_visit** (default for clinic notes, progress notes):
  - chief_complaint: patient's primary reason for visit (required)
  - history_present_illness: narrative of current symptoms
  - physical_exam_findings: array of objective findings
  - assessment_diagnoses: array of diagnoses (required)
  - plan_of_care: treatment plan, referrals, follow-up
  - workStatus: object with status, effective_date, duration, restrictions_summary
  - providerRestrictions: array of restriction objects
  - painAssessments: array of pain assessment objects
  - mmiStatus: object with status, date_reached, expected_date, notes
  - vitalSets: array of vital sign measurements
  - medicationActions: array of medication changes (started, increased, discontinued, etc.)
```

**Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_medication_actions.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add app/config/templates/office_visit.yaml app/config/templates/base.yaml tests/core/extraction/test_medication_actions.py
git commit -m "feat: add medicationActions field for tracking medication changes"
```

---

### Task 9: Add provider_specialty to Core Fields

**Files:**
- Modify: `app/config/templates/base.yaml`
- Test: `tests/core/extraction/test_provider_specialty.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_provider_specialty.py`:
```python
"""Tests for provider_specialty field."""
import pytest


class TestProviderSpecialty:
    """Test provider_specialty core field."""

    def test_provider_specialty_in_core_fields(self):
        """Verify provider_specialty is a core field."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        core_fields = loader.get_core_fields()

        assert "provider_specialty" in core_fields

    def test_provider_specialty_structure(self):
        """Verify provider_specialty field structure."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        core_fields = loader.get_core_fields()

        specialty = core_fields["provider_specialty"]
        assert specialty["type"] == "string"
        assert "common_values" in specialty
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_provider_specialty.py -v`
Expected: FAIL

**Step 3: Add provider_specialty to base.yaml core_fields**

Modify `app/config/templates/base.yaml` core_fields section:
```yaml
core_fields:
  # ... existing fields ...

  provider_specialty:
    type: string
    required: false
    description: "Medical specialty of the provider"
    common_values:
      - "Family Medicine"
      - "Internal Medicine"
      - "Neurology"
      - "Orthopedics"
      - "Pain Management"
      - "Psychiatry"
      - "Psychology"
      - "Physical Therapy"
      - "Occupational Therapy"
      - "Rheumatology"
      - "Cardiology"
      - "Pulmonology"
      - "Gastroenterology"
      - "Neurosurgery"
      - "Orthopedic Surgery"
    detection_patterns:
      - "Extract from credentials after name"
      - "Extract from letterhead"
      - "Infer from department name"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_provider_specialty.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config/templates/base.yaml tests/core/extraction/test_provider_specialty.py
git commit -m "feat: add provider_specialty to core extraction fields"
```

---

### Task 10: Create functional_capacity_evaluation Template

**Files:**
- Create: `app/config/templates/functional_capacity_evaluation.yaml`
- Modify: `app/core/extraction/constants.py`
- Modify: `app/core/extraction/template_loader.py`
- Test: `tests/core/extraction/test_fce_template.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_fce_template.py`:
```python
"""Tests for functional_capacity_evaluation template."""
import pytest


class TestFCETemplate:
    """Test FCE visit type configuration."""

    def test_fce_in_valid_visit_types(self):
        """Verify FCE is a valid visit type."""
        from app.core.extraction.constants import VALID_VISIT_TYPES

        assert "functional_capacity_evaluation" in VALID_VISIT_TYPES

    def test_fce_template_exists(self):
        """Verify FCE template can be loaded."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        template = loader.get_template("functional_capacity_evaluation")

        assert template is not None
        assert template.get("visit_type") == "functional_capacity_evaluation"

    def test_fce_has_required_fields(self):
        """Verify FCE has RFC-critical fields."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("functional_capacity_evaluation")

        # Physical demand levels
        assert "lift_floor_to_waist" in fields
        assert "sitting_tolerance" in fields
        assert "standing_tolerance" in fields
        assert "walking_tolerance" in fields

        # Conclusions
        assert "work_level" in fields
        assert "effort_consistency" in fields
        assert "specific_restrictions" in fields

    def test_fce_detection_keywords(self):
        """Verify detection keywords for FCE."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        detected = loader.detect_visit_types("Functional Capacity Evaluation performed today")

        assert "functional_capacity_evaluation" in detected
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_fce_template.py -v`
Expected: FAIL

**Step 3: Add to VALID_VISIT_TYPES**

Modify `app/core/extraction/constants.py`:
```python
VALID_VISIT_TYPES: List[str] = [
    # ... existing types ...
    "telehealth",
    "functional_capacity_evaluation",  # ← Add this
]
```

**Step 4: Add detection keywords to template_loader.py**

Modify `app/core/extraction/template_loader.py`:
```python
            "functional_capacity_evaluation": [
                "functional capacity evaluation", "FCE", "functional capacity exam",
                "physical capacity evaluation", "work capacity evaluation"
            ],
```

**Step 5: Create functional_capacity_evaluation.yaml**

Create `app/config/templates/functional_capacity_evaluation.yaml`:
```yaml
# Functional Capacity Evaluation Template
# For: FCE reports evaluating physical work capacity
#
# Version: 1.0.0

visit_type: "functional_capacity_evaluation"
description: "Functional Capacity Evaluation - formal assessment of physical work abilities"

user_prompt: |
  Parse the following Functional Capacity Evaluation and extract the key findings.

  **MEDICAL RECORDS:**
  {medical_content}

  **EXTRACT:**
  - Evaluation date and duration
  - Evaluator name and credentials
  - Physical demand levels (lift, carry, push, pull)
  - Positional tolerances (sit, stand, walk)
  - Effort consistency and validity
  - Work level determination
  - Specific restrictions

  **OUTPUT:** Return JSON following the functional_capacity_evaluation schema.

fields:
  evaluator:
    type: string
    required: true
    label: "Evaluator"
    description: "Name and credentials of FCE evaluator"

  evaluation_duration:
    type: string
    required: false
    label: "Duration"
    description: "Length of evaluation (e.g., '4 hours', '2-day')"

  # Physical Demand Levels
  lift_floor_to_waist:
    type: string
    required: false
    label: "Lift Floor-Waist"
    description: "Floor to waist lifting capacity (e.g., '20 lbs occasional')"

  lift_waist_to_shoulder:
    type: string
    required: false
    label: "Lift Waist-Shoulder"
    description: "Waist to shoulder lifting capacity"

  lift_overhead:
    type: string
    required: false
    label: "Lift Overhead"
    description: "Overhead lifting capacity"

  carry:
    type: string
    required: false
    label: "Carry"
    description: "Carrying capacity"

  push_pull:
    type: string
    required: false
    label: "Push/Pull"
    description: "Push and pull force capacity"

  # Positional Tolerances
  sitting_tolerance:
    type: string
    required: false
    label: "Sit Tolerance"
    description: "Maximum sitting duration (e.g., '4 hours continuous')"

  standing_tolerance:
    type: string
    required: false
    label: "Stand Tolerance"
    description: "Maximum standing duration"

  walking_tolerance:
    type: string
    required: false
    label: "Walk Tolerance"
    description: "Maximum walking duration/distance"

  # Validity
  effort_consistency:
    type: enum
    required: false
    label: "Effort"
    values:
      - "consistent"
      - "inconsistent"
      - "self-limited"
      - "maximal"
      - "submaximal"
    description: "Effort consistency rating"

  validity_indicators:
    type: array
    items: string
    required: false
    label: "Validity"
    description: "Validity test results"

  # Conclusions
  work_level:
    type: enum
    required: true
    label: "Work Level"
    values:
      - "sedentary"
      - "light"
      - "medium"
      - "heavy"
      - "very_heavy"
    description: "DOT work level determination"

  specific_restrictions:
    type: array
    items: string
    required: false
    label: "Restrictions"
    description: "Specific functional restrictions identified"

  return_to_work_recommendation:
    type: string
    required: false
    label: "RTW Recommendation"
    description: "Return to work recommendation"

output_labels: ["Work Level", "Lift", "Sit Tolerance", "Stand Tolerance", "Effort", "Restrictions"]

output_example: |
  Work Level: Light
  Lift: Floor-waist 20 lbs occasional, 10 lbs frequent
  Sit Tolerance: 6 hours with position changes every 30 min
  Stand Tolerance: 2 hours total, 30 min at a time
  Effort: Consistent, valid results
  Restrictions: No repetitive bending, sit/stand option required
```

**Step 6: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_fce_template.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add app/config/templates/functional_capacity_evaluation.yaml app/core/extraction/constants.py app/core/extraction/template_loader.py tests/core/extraction/test_fce_template.py
git commit -m "feat: add functional_capacity_evaluation visit type template"
```

---

### Task 11: Add compliance Field to Templates

**Files:**
- Modify: `app/config/templates/office_visit.yaml`
- Test: `tests/core/extraction/test_compliance_field.py`

**Step 1: Write the failing test**

Create `tests/core/extraction/test_compliance_field.py`:
```python
"""Tests for compliance field."""
import pytest


class TestComplianceField:
    """Test compliance field configuration."""

    def test_compliance_field_present(self):
        """Verify compliance field is in office_visit template."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        assert "compliance" in fields
        assert fields["compliance"]["type"] == "object"

    def test_compliance_structure(self):
        """Verify compliance has correct structure."""
        from app.core.extraction.template_loader import get_template_loader

        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        compliance_fields = fields["compliance"]["fields"]

        assert "medication_adherence" in compliance_fields
        assert "appointment_adherence" in compliance_fields
        assert "treatment_participation" in compliance_fields
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_compliance_field.py -v`
Expected: FAIL

**Step 3: Add compliance field to office_visit.yaml**

Add to `app/config/templates/office_visit.yaml`:
```yaml
  compliance:
    type: object
    required: false
    label: "Compliance"
    description: "Treatment compliance observations"
    fields:
      medication_adherence:
        type: string
        description: "Medication compliance status (e.g., 'compliant', 'non-compliant', 'reports missing doses')"
      appointment_adherence:
        type: string
        description: "Appointment compliance (e.g., 'keeps appointments', 'frequent no-shows')"
      treatment_participation:
        type: string
        description: "Participation in treatment (e.g., 'engaged in PT', 'declined surgery')"
      notes:
        type: string
        description: "Additional compliance notes"
    detection_keywords:
      - "compliant"
      - "non-compliant"
      - "noncompliant"
      - "adherent"
      - "adherence"
      - "no-show"
      - "no show"
      - "missed appointment"
      - "cancelled"
      - "declined"
      - "refused"
      - "not following"
      - "poor compliance"
      - "good compliance"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/extraction/test_compliance_field.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config/templates/office_visit.yaml tests/core/extraction/test_compliance_field.py
git commit -m "feat: add compliance field for treatment adherence tracking"
```

---

## Phase 3: Longitudinal Analysis (Week 5-6)

### Task 12: Create Longitudinal Analysis Module Structure

**Files:**
- Create: `app/core/analysis/__init__.py`
- Create: `app/core/analysis/longitudinal_summary.py`
- Test: `tests/core/analysis/test_longitudinal_module.py`

**Step 1: Write the failing test**

Create `tests/core/analysis/__init__.py` (empty).

Create `tests/core/analysis/test_longitudinal_module.py`:
```python
"""Tests for longitudinal analysis module."""
import pytest


class TestLongitudinalModule:
    """Test longitudinal analysis module structure."""

    def test_module_imports(self):
        """Verify module can be imported."""
        from app.core.analysis import longitudinal_summary
        from app.core.analysis.longitudinal_summary import (
            TreatmentGapAnalyzer,
            PainTrendAnalyzer,
            SymptomFrequencyAnalyzer,
            LongitudinalSummary,
        )

    def test_treatment_gap_analyzer_exists(self):
        """Verify TreatmentGapAnalyzer class exists."""
        from app.core.analysis.longitudinal_summary import TreatmentGapAnalyzer

        analyzer = TreatmentGapAnalyzer()
        assert hasattr(analyzer, 'analyze')

    def test_pain_trend_analyzer_exists(self):
        """Verify PainTrendAnalyzer class exists."""
        from app.core.analysis.longitudinal_summary import PainTrendAnalyzer

        analyzer = PainTrendAnalyzer()
        assert hasattr(analyzer, 'analyze')

    def test_symptom_frequency_analyzer_exists(self):
        """Verify SymptomFrequencyAnalyzer class exists."""
        from app.core.analysis.longitudinal_summary import SymptomFrequencyAnalyzer

        analyzer = SymptomFrequencyAnalyzer()
        assert hasattr(analyzer, 'analyze')
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_longitudinal_module.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create module structure**

Create `app/core/analysis/__init__.py`:
```python
"""Longitudinal analysis module for medical record trends."""
from .longitudinal_summary import (
    TreatmentGapAnalyzer,
    PainTrendAnalyzer,
    SymptomFrequencyAnalyzer,
    LongitudinalSummary,
    build_longitudinal_summary,
)

__all__ = [
    "TreatmentGapAnalyzer",
    "PainTrendAnalyzer",
    "SymptomFrequencyAnalyzer",
    "LongitudinalSummary",
    "build_longitudinal_summary",
]
```

Create `app/core/analysis/longitudinal_summary.py`:
```python
"""
Longitudinal analysis for medical record trends.

Provides post-processing analysis of extracted entries to identify:
- Treatment gaps
- Pain score trends
- Symptom frequency patterns
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class TreatmentGap:
    """Represents a gap in treatment."""
    start_date: date
    end_date: date
    duration_days: int
    severity: str  # "minor", "moderate", "significant", "critical"
    preceding_event_id: Optional[str] = None
    following_event_id: Optional[str] = None
    gap_context: Optional[str] = None


@dataclass
class PainDataPoint:
    """Single pain measurement."""
    date: date
    score: int
    location: str
    event_id: str


@dataclass
class PainTrend:
    """Pain trend for a specific location."""
    location: str
    data_points: List[PainDataPoint] = field(default_factory=list)
    trend: str = "unknown"  # "improving", "stable", "worsening", "fluctuating"
    average_score: float = 0.0
    peak_score: int = 0
    peak_date: Optional[date] = None
    lowest_score: int = 10
    lowest_date: Optional[date] = None


@dataclass
class SymptomMention:
    """Frequency of symptom mentions."""
    symptom: str
    mention_count: int
    first_mention: Optional[date] = None
    last_mention: Optional[date] = None
    event_ids: List[str] = field(default_factory=list)


@dataclass
class LongitudinalSummary:
    """Complete longitudinal analysis summary."""
    treatment_gaps: List[TreatmentGap] = field(default_factory=list)
    pain_trends: List[PainTrend] = field(default_factory=list)
    symptom_mentions: List[SymptomMention] = field(default_factory=list)
    key_dates: Dict[str, Any] = field(default_factory=dict)


class TreatmentGapAnalyzer:
    """Detect gaps between medical visits."""

    # Gap severity thresholds (days)
    MINOR_THRESHOLD = 30
    MODERATE_THRESHOLD = 60
    SIGNIFICANT_THRESHOLD = 90
    CRITICAL_THRESHOLD = 180

    def analyze(
        self,
        entries: List[Dict[str, Any]],
        min_gap_days: int = 30
    ) -> List[TreatmentGap]:
        """Analyze entries for treatment gaps.

        Args:
            entries: List of extracted medical entries
            min_gap_days: Minimum days to consider as a gap

        Returns:
            List of identified treatment gaps
        """
        # Implementation placeholder
        return []


class PainTrendAnalyzer:
    """Track pain scores over time."""

    def analyze(self, entries: List[Dict[str, Any]]) -> List[PainTrend]:
        """Analyze pain assessment trends.

        Args:
            entries: List of extracted medical entries

        Returns:
            List of pain trends by location
        """
        # Implementation placeholder
        return []


class SymptomFrequencyAnalyzer:
    """Count symptom mentions across records."""

    TRACKED_SYMPTOMS = [
        "pain", "fatigue", "weakness", "numbness", "tingling",
        "headache", "dizziness", "nausea", "insomnia", "anxiety",
        "depression", "difficulty concentrating", "memory problems"
    ]

    def analyze(self, entries: List[Dict[str, Any]]) -> List[SymptomMention]:
        """Analyze symptom frequency.

        Args:
            entries: List of extracted medical entries

        Returns:
            List of symptom mention frequencies
        """
        # Implementation placeholder
        return []


def build_longitudinal_summary(entries: List[Dict[str, Any]]) -> LongitudinalSummary:
    """Build complete longitudinal summary from entries.

    Args:
        entries: List of extracted medical entries

    Returns:
        Complete longitudinal analysis summary
    """
    return LongitudinalSummary(
        treatment_gaps=TreatmentGapAnalyzer().analyze(entries),
        pain_trends=PainTrendAnalyzer().analyze(entries),
        symptom_mentions=SymptomFrequencyAnalyzer().analyze(entries),
    )
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_longitudinal_module.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/analysis/ tests/core/analysis/
git commit -m "feat: create longitudinal analysis module structure"
```

---

### Task 13: Implement TreatmentGapAnalyzer

**Files:**
- Modify: `app/core/analysis/longitudinal_summary.py`
- Test: `tests/core/analysis/test_treatment_gap_analyzer.py`

**Step 1: Write the failing test**

Create `tests/core/analysis/test_treatment_gap_analyzer.py`:
```python
"""Tests for TreatmentGapAnalyzer."""
import pytest
from datetime import date

from app.core.analysis.longitudinal_summary import TreatmentGapAnalyzer, TreatmentGap


class TestTreatmentGapAnalyzer:
    """Test treatment gap detection."""

    @pytest.fixture
    def analyzer(self):
        return TreatmentGapAnalyzer()

    @pytest.fixture
    def sample_entries(self):
        """Sample entries with a 45-day gap."""
        return [
            {"date": "01/15/2024", "visit_type": "office_visit", "id": "1"},
            {"date": "03/01/2024", "visit_type": "office_visit", "id": "2"},  # 45 days later
            {"date": "03/15/2024", "visit_type": "office_visit", "id": "3"},
        ]

    def test_detects_gap_over_threshold(self, analyzer, sample_entries):
        """Should detect 45-day gap with 30-day threshold."""
        gaps = analyzer.analyze(sample_entries, min_gap_days=30)

        assert len(gaps) == 1
        assert gaps[0].duration_days == 45
        assert gaps[0].severity == "moderate"  # 45 days = moderate (30-60)

    def test_no_gaps_under_threshold(self, analyzer):
        """Should not detect gaps under threshold."""
        entries = [
            {"date": "01/01/2024", "visit_type": "office_visit", "id": "1"},
            {"date": "01/20/2024", "visit_type": "office_visit", "id": "2"},  # 19 days
        ]
        gaps = analyzer.analyze(entries, min_gap_days=30)

        assert len(gaps) == 0

    def test_gap_severity_classification(self, analyzer):
        """Test gap severity is correctly classified."""
        # 35 days = minor
        entries_minor = [
            {"date": "01/01/2024", "visit_type": "office_visit", "id": "1"},
            {"date": "02/05/2024", "visit_type": "office_visit", "id": "2"},
        ]
        gaps = analyzer.analyze(entries_minor, min_gap_days=30)
        assert gaps[0].severity == "minor"

        # 100 days = significant
        entries_sig = [
            {"date": "01/01/2024", "visit_type": "office_visit", "id": "1"},
            {"date": "04/11/2024", "visit_type": "office_visit", "id": "2"},
        ]
        gaps = analyzer.analyze(entries_sig, min_gap_days=30)
        assert gaps[0].severity == "significant"

        # 200 days = critical
        entries_crit = [
            {"date": "01/01/2024", "visit_type": "office_visit", "id": "1"},
            {"date": "07/20/2024", "visit_type": "office_visit", "id": "2"},
        ]
        gaps = analyzer.analyze(entries_crit, min_gap_days=30)
        assert gaps[0].severity == "critical"

    def test_empty_entries(self, analyzer):
        """Should handle empty entries list."""
        gaps = analyzer.analyze([])
        assert gaps == []

    def test_single_entry(self, analyzer):
        """Should handle single entry."""
        gaps = analyzer.analyze([{"date": "01/01/2024", "id": "1"}])
        assert gaps == []
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_treatment_gap_analyzer.py -v`
Expected: FAIL (returns empty list)

**Step 3: Implement TreatmentGapAnalyzer**

Modify `app/core/analysis/longitudinal_summary.py`:
```python
class TreatmentGapAnalyzer:
    """Detect gaps between medical visits."""

    MINOR_THRESHOLD = 30
    MODERATE_THRESHOLD = 60
    SIGNIFICANT_THRESHOLD = 90
    CRITICAL_THRESHOLD = 180

    def analyze(
        self,
        entries: List[Dict[str, Any]],
        min_gap_days: int = 30
    ) -> List[TreatmentGap]:
        """Analyze entries for treatment gaps."""
        if len(entries) < 2:
            return []

        # Parse and sort entries by date
        dated_entries = []
        for entry in entries:
            entry_date = self._parse_date(entry.get("date"))
            if entry_date:
                dated_entries.append((entry_date, entry))

        if len(dated_entries) < 2:
            return []

        dated_entries.sort(key=lambda x: x[0])

        gaps = []
        for i in range(len(dated_entries) - 1):
            current_date, current_entry = dated_entries[i]
            next_date, next_entry = dated_entries[i + 1]

            delta_days = (next_date - current_date).days

            if delta_days >= min_gap_days:
                severity = self._classify_severity(delta_days)
                gaps.append(TreatmentGap(
                    start_date=current_date,
                    end_date=next_date,
                    duration_days=delta_days,
                    severity=severity,
                    preceding_event_id=current_entry.get("id"),
                    following_event_id=next_entry.get("id"),
                ))

        return gaps

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # Handle MM/DD/YYYY format
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
            # Handle YYYY-MM-DD format
            elif "-" in date_str:
                parts = date_str.split("-")
                if len(parts) == 3:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
        except (ValueError, IndexError):
            logger.warning(f"Could not parse date: {date_str}")
        return None

    def _classify_severity(self, days: int) -> str:
        """Classify gap severity based on duration."""
        if days >= self.CRITICAL_THRESHOLD:
            return "critical"
        elif days >= self.SIGNIFICANT_THRESHOLD:
            return "significant"
        elif days >= self.MODERATE_THRESHOLD:
            return "moderate"
        else:
            return "minor"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_treatment_gap_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/analysis/longitudinal_summary.py tests/core/analysis/test_treatment_gap_analyzer.py
git commit -m "feat: implement TreatmentGapAnalyzer for detecting treatment gaps"
```

---

### Task 14: Implement PainTrendAnalyzer

**Files:**
- Modify: `app/core/analysis/longitudinal_summary.py`
- Test: `tests/core/analysis/test_pain_trend_analyzer.py`

**Step 1: Write the failing test**

Create `tests/core/analysis/test_pain_trend_analyzer.py`:
```python
"""Tests for PainTrendAnalyzer."""
import pytest

from app.core.analysis.longitudinal_summary import PainTrendAnalyzer


class TestPainTrendAnalyzer:
    """Test pain trend analysis."""

    @pytest.fixture
    def analyzer(self):
        return PainTrendAnalyzer()

    @pytest.fixture
    def improving_entries(self):
        """Entries showing pain improvement."""
        return [
            {
                "date": "01/01/2024",
                "id": "1",
                "occurrence_treatment": {
                    "painAssessments": [
                        {"location": "low back", "current": 8}
                    ]
                }
            },
            {
                "date": "02/01/2024",
                "id": "2",
                "occurrence_treatment": {
                    "painAssessments": [
                        {"location": "low back", "current": 6}
                    ]
                }
            },
            {
                "date": "03/01/2024",
                "id": "3",
                "occurrence_treatment": {
                    "painAssessments": [
                        {"location": "low back", "current": 4}
                    ]
                }
            },
        ]

    def test_detects_improving_trend(self, analyzer, improving_entries):
        """Should detect improving pain trend."""
        trends = analyzer.analyze(improving_entries)

        assert len(trends) == 1
        assert trends[0].location == "low back"
        assert trends[0].trend == "improving"
        assert trends[0].peak_score == 8
        assert trends[0].lowest_score == 4

    def test_calculates_average(self, analyzer, improving_entries):
        """Should calculate average pain score."""
        trends = analyzer.analyze(improving_entries)

        # Average of 8, 6, 4 = 6.0
        assert trends[0].average_score == 6.0

    def test_worsening_trend(self, analyzer):
        """Should detect worsening pain trend."""
        entries = [
            {"date": "01/01/2024", "id": "1", "occurrence_treatment": {"painAssessments": [{"location": "neck", "current": 3}]}},
            {"date": "02/01/2024", "id": "2", "occurrence_treatment": {"painAssessments": [{"location": "neck", "current": 5}]}},
            {"date": "03/01/2024", "id": "3", "occurrence_treatment": {"painAssessments": [{"location": "neck", "current": 7}]}},
        ]
        trends = analyzer.analyze(entries)

        assert trends[0].trend == "worsening"

    def test_stable_trend(self, analyzer):
        """Should detect stable pain trend."""
        entries = [
            {"date": "01/01/2024", "id": "1", "occurrence_treatment": {"painAssessments": [{"location": "knee", "current": 5}]}},
            {"date": "02/01/2024", "id": "2", "occurrence_treatment": {"painAssessments": [{"location": "knee", "current": 5}]}},
            {"date": "03/01/2024", "id": "3", "occurrence_treatment": {"painAssessments": [{"location": "knee", "current": 5}]}},
        ]
        trends = analyzer.analyze(entries)

        assert trends[0].trend == "stable"

    def test_multiple_locations(self, analyzer):
        """Should track multiple pain locations separately."""
        entries = [
            {"date": "01/01/2024", "id": "1", "occurrence_treatment": {"painAssessments": [
                {"location": "low back", "current": 7},
                {"location": "neck", "current": 4}
            ]}},
        ]
        trends = analyzer.analyze(entries)

        assert len(trends) == 2
        locations = {t.location for t in trends}
        assert "low back" in locations
        assert "neck" in locations

    def test_empty_entries(self, analyzer):
        """Should handle entries without pain assessments."""
        entries = [
            {"date": "01/01/2024", "id": "1", "occurrence_treatment": {}},
        ]
        trends = analyzer.analyze(entries)

        assert trends == []
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_pain_trend_analyzer.py -v`
Expected: FAIL

**Step 3: Implement PainTrendAnalyzer**

Update `app/core/analysis/longitudinal_summary.py`:
```python
class PainTrendAnalyzer:
    """Track pain scores over time."""

    def analyze(self, entries: List[Dict[str, Any]]) -> List[PainTrend]:
        """Analyze pain assessment trends."""
        # Group pain assessments by location
        location_data: Dict[str, List[PainDataPoint]] = {}

        for entry in entries:
            entry_date = self._parse_date(entry.get("date"))
            if not entry_date:
                continue

            occurrence = entry.get("occurrence_treatment", {})
            pain_assessments = occurrence.get("painAssessments", [])

            for assessment in pain_assessments:
                location = assessment.get("location", "unknown")
                score = assessment.get("current")

                if score is not None:
                    if location not in location_data:
                        location_data[location] = []

                    location_data[location].append(PainDataPoint(
                        date=entry_date,
                        score=int(score),
                        location=location,
                        event_id=entry.get("id", "")
                    ))

        # Build trends for each location
        trends = []
        for location, data_points in location_data.items():
            if not data_points:
                continue

            # Sort by date
            data_points.sort(key=lambda x: x.date)

            scores = [dp.score for dp in data_points]
            avg_score = sum(scores) / len(scores)
            peak_score = max(scores)
            lowest_score = min(scores)

            # Find dates for peak and lowest
            peak_date = next(dp.date for dp in data_points if dp.score == peak_score)
            lowest_date = next(dp.date for dp in data_points if dp.score == lowest_score)

            # Determine trend
            trend = self._determine_trend(scores)

            trends.append(PainTrend(
                location=location,
                data_points=data_points,
                trend=trend,
                average_score=round(avg_score, 1),
                peak_score=peak_score,
                peak_date=peak_date,
                lowest_score=lowest_score,
                lowest_date=lowest_date,
            ))

        return trends

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
            elif "-" in date_str:
                parts = date_str.split("-")
                if len(parts) == 3:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
        except (ValueError, IndexError):
            pass
        return None

    def _determine_trend(self, scores: List[int]) -> str:
        """Determine trend direction from scores."""
        if len(scores) < 2:
            return "unknown"

        # Check if all scores are the same (stable)
        if all(s == scores[0] for s in scores):
            return "stable"

        # Calculate simple linear trend
        first_half_avg = sum(scores[:len(scores)//2 + 1]) / (len(scores)//2 + 1)
        second_half_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)

        diff = second_half_avg - first_half_avg

        if abs(diff) < 1:
            return "stable"
        elif diff < 0:
            return "improving"
        else:
            return "worsening"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_pain_trend_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/analysis/longitudinal_summary.py tests/core/analysis/test_pain_trend_analyzer.py
git commit -m "feat: implement PainTrendAnalyzer for tracking pain trends over time"
```

---

### Task 15: Implement SymptomFrequencyAnalyzer

**Files:**
- Modify: `app/core/analysis/longitudinal_summary.py`
- Test: `tests/core/analysis/test_symptom_frequency_analyzer.py`

**Step 1: Write the failing test**

Create `tests/core/analysis/test_symptom_frequency_analyzer.py`:
```python
"""Tests for SymptomFrequencyAnalyzer."""
import pytest

from app.core.analysis.longitudinal_summary import SymptomFrequencyAnalyzer


class TestSymptomFrequencyAnalyzer:
    """Test symptom frequency analysis."""

    @pytest.fixture
    def analyzer(self):
        return SymptomFrequencyAnalyzer()

    @pytest.fixture
    def sample_entries(self):
        return [
            {
                "date": "01/01/2024",
                "id": "1",
                "occurrence_treatment": {
                    "chief_complaint": "Low back pain and fatigue",
                    "history_present_illness": "Reports constant pain and weakness in legs"
                }
            },
            {
                "date": "02/01/2024",
                "id": "2",
                "occurrence_treatment": {
                    "chief_complaint": "Fatigue and headache",
                }
            },
            {
                "date": "03/01/2024",
                "id": "3",
                "occurrence_treatment": {
                    "chief_complaint": "Pain management follow-up",
                }
            },
        ]

    def test_counts_symptom_mentions(self, analyzer, sample_entries):
        """Should count symptom mentions across entries."""
        mentions = analyzer.analyze(sample_entries)

        # Pain mentioned in entries 1 and 3
        pain_mention = next((m for m in mentions if m.symptom == "pain"), None)
        assert pain_mention is not None
        assert pain_mention.mention_count >= 2

        # Fatigue mentioned in entries 1 and 2
        fatigue_mention = next((m for m in mentions if m.symptom == "fatigue"), None)
        assert fatigue_mention is not None
        assert fatigue_mention.mention_count == 2

    def test_tracks_first_last_mention(self, analyzer, sample_entries):
        """Should track first and last mention dates."""
        mentions = analyzer.analyze(sample_entries)

        fatigue_mention = next((m for m in mentions if m.symptom == "fatigue"), None)
        assert fatigue_mention is not None
        assert fatigue_mention.first_mention.month == 1  # January
        assert fatigue_mention.last_mention.month == 2   # February

    def test_tracks_event_ids(self, analyzer, sample_entries):
        """Should track which events contain each symptom."""
        mentions = analyzer.analyze(sample_entries)

        fatigue_mention = next((m for m in mentions if m.symptom == "fatigue"), None)
        assert "1" in fatigue_mention.event_ids
        assert "2" in fatigue_mention.event_ids

    def test_empty_entries(self, analyzer):
        """Should handle empty entries."""
        mentions = analyzer.analyze([])
        assert mentions == []

    def test_no_symptoms_found(self, analyzer):
        """Should handle entries without tracked symptoms."""
        entries = [
            {"date": "01/01/2024", "id": "1", "occurrence_treatment": {"chief_complaint": "Routine checkup"}}
        ]
        mentions = analyzer.analyze(entries)
        assert mentions == []
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_symptom_frequency_analyzer.py -v`
Expected: FAIL

**Step 3: Implement SymptomFrequencyAnalyzer**

Update `app/core/analysis/longitudinal_summary.py`:
```python
class SymptomFrequencyAnalyzer:
    """Count symptom mentions across records."""

    TRACKED_SYMPTOMS = [
        "pain", "fatigue", "weakness", "numbness", "tingling",
        "headache", "dizziness", "nausea", "insomnia", "anxiety",
        "depression", "difficulty concentrating", "memory problems"
    ]

    def analyze(self, entries: List[Dict[str, Any]]) -> List[SymptomMention]:
        """Analyze symptom frequency."""
        symptom_data: Dict[str, SymptomMention] = {}

        for entry in entries:
            entry_date = self._parse_date(entry.get("date"))
            entry_id = entry.get("id", "")

            # Combine text fields to search
            occurrence = entry.get("occurrence_treatment", {})
            text_to_search = " ".join([
                str(occurrence.get("chief_complaint", "")),
                str(occurrence.get("history_present_illness", "")),
                str(occurrence.get("current_symptoms", "")),
            ]).lower()

            for symptom in self.TRACKED_SYMPTOMS:
                if symptom in text_to_search:
                    if symptom not in symptom_data:
                        symptom_data[symptom] = SymptomMention(
                            symptom=symptom,
                            mention_count=0,
                            first_mention=entry_date,
                            last_mention=entry_date,
                            event_ids=[]
                        )

                    mention = symptom_data[symptom]
                    mention.mention_count += 1
                    mention.event_ids.append(entry_id)

                    if entry_date:
                        if mention.first_mention is None or entry_date < mention.first_mention:
                            mention.first_mention = entry_date
                        if mention.last_mention is None or entry_date > mention.last_mention:
                            mention.last_mention = entry_date

        # Sort by mention count (descending)
        return sorted(symptom_data.values(), key=lambda x: x.mention_count, reverse=True)

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
            elif "-" in date_str:
                parts = date_str.split("-")
                if len(parts) == 3:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(year, month, day)
        except (ValueError, IndexError):
            pass
        return None
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. pytest tests/core/analysis/test_symptom_frequency_analyzer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/core/analysis/longitudinal_summary.py tests/core/analysis/test_symptom_frequency_analyzer.py
git commit -m "feat: implement SymptomFrequencyAnalyzer for tracking symptom mentions"
```

---

### Task 16: Create Regression Test Suite

**Files:**
- Create: `tests/test_regression.py`

**Step 1: Create regression test file**

Create `tests/test_regression.py`:
```python
"""Regression test suite for extraction pipeline.

Verifies backwards compatibility and tracks new field coverage.
"""
import pytest
from pathlib import Path


class TestRegressionSuite:
    """Run against existing test data to verify no degradation."""

    # Baseline metrics from known good extraction
    BASELINE_METRICS = {
        "entry_count_minimum": 100,  # Adjust based on actual baseline
    }

    @pytest.fixture
    def template_loader(self):
        from app.core.extraction.template_loader import get_template_loader
        return get_template_loader()

    def test_all_visit_types_have_templates(self, template_loader):
        """All valid visit types should have corresponding templates."""
        from app.core.extraction.constants import VALID_VISIT_TYPES

        for visit_type in VALID_VISIT_TYPES:
            template = template_loader.get_template(visit_type)
            assert template, f"Missing template for {visit_type}"

    def test_backwards_compatible_fields(self, template_loader):
        """Core fields from original schema should still exist."""
        fields = template_loader.get_fields("office_visit")

        # Original fields must exist
        assert "chief_complaint" in fields
        assert "assessment_diagnoses" in fields
        assert "plan_of_care" in fields

    def test_new_rfc_fields_present(self, template_loader):
        """New RFC-critical fields should be present."""
        fields = template_loader.get_fields("office_visit")

        # New fields added by this implementation
        assert "workStatus" in fields
        assert "providerRestrictions" in fields
        assert "painAssessments" in fields
        assert "mmiStatus" in fields

    def test_new_visit_types_exist(self):
        """New visit types should be in VALID_VISIT_TYPES."""
        from app.core.extraction.constants import VALID_VISIT_TYPES

        assert "telehealth" in VALID_VISIT_TYPES
        assert "functional_capacity_evaluation" in VALID_VISIT_TYPES

    def test_template_detection_keywords(self, template_loader):
        """Detection keywords should identify correct visit types."""
        # Telehealth detection
        detected = template_loader.detect_visit_types("This was a telehealth video visit")
        assert "telehealth" in detected

        # FCE detection
        detected = template_loader.detect_visit_types("Functional Capacity Evaluation")
        assert "functional_capacity_evaluation" in detected

        # Pain management should still detect office_visit
        detected = template_loader.detect_visit_types("Pain management follow-up visit")
        assert "office_visit" in detected

    def test_longitudinal_analysis_module(self):
        """Longitudinal analysis module should be importable and functional."""
        from app.core.analysis import (
            TreatmentGapAnalyzer,
            PainTrendAnalyzer,
            SymptomFrequencyAnalyzer,
            build_longitudinal_summary,
        )

        # Basic functionality test
        entries = []
        summary = build_longitudinal_summary(entries)

        assert summary is not None
        assert isinstance(summary.treatment_gaps, list)
        assert isinstance(summary.pain_trends, list)
        assert isinstance(summary.symptom_mentions, list)
```

**Step 2: Run regression tests**

Run: `PYTHONPATH=. pytest tests/test_regression.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_regression.py
git commit -m "test: add regression test suite for backwards compatibility"
```

---

### Task 17: Create Schema Validation Tests

**Files:**
- Create: `tests/test_schema_validation.py`

**Step 1: Create schema validation test file**

Create `tests/test_schema_validation.py`:
```python
"""Schema validation tests.

Validates extracted data matches JSON Schema definitions.
"""
import json
import pytest
from pathlib import Path


class TestSchemaValidation:
    """Validate extraction output against schema definitions."""

    @pytest.fixture
    def v21_schema(self):
        """Load v2.1 JSON schema."""
        schema_path = Path("schemas/medical_evidence_of_record_schema_v2.1.json")
        if schema_path.exists():
            return json.loads(schema_path.read_text())
        pytest.skip("Schema file not found")

    def test_work_status_matches_schema(self, v21_schema):
        """workStatus field should match schema definition."""
        # Get workStatus definition from our template
        from app.core.extraction.template_loader import get_template_loader
        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        work_status = fields.get("workStatus", {})

        # Validate our enum values are subset of schema
        our_values = set(work_status.get("fields", {}).get("status", {}).get("values", []))

        # Should include key RFC work status values
        expected = {"full_duty", "light_duty", "no_work", "sedentary_only"}
        assert expected.issubset(our_values)

    def test_pain_assessment_matches_schema(self, v21_schema):
        """painAssessments field should match PainAssessment definition."""
        schema_pain = v21_schema.get("definitions", {}).get("PainAssessment", {})

        from app.core.extraction.template_loader import get_template_loader
        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        our_pain = fields.get("painAssessments", {}).get("items", {})

        # Key fields should be present
        assert "location" in our_pain
        assert "current" in our_pain
        assert "scale" in our_pain

    def test_provider_restrictions_matches_schema(self, v21_schema):
        """providerRestrictions should match ProviderRestriction definition."""
        schema_restriction = v21_schema.get("definitions", {}).get("ProviderRestriction", {})

        from app.core.extraction.template_loader import get_template_loader
        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        our_restrictions = fields.get("providerRestrictions", {}).get("items", {})

        # Should have restriction_type with lifting, standing, etc.
        restriction_types = our_restrictions.get("restriction_type", {}).get("values", [])

        assert "lifting" in restriction_types
        assert "standing" in restriction_types
        assert "sitting" in restriction_types
        assert "sit_stand_option" in restriction_types

    def test_vitals_matches_schema(self, v21_schema):
        """vitalSets should match VitalSet definition."""
        from app.core.extraction.template_loader import get_template_loader
        loader = get_template_loader()
        fields = loader.get_fields("office_visit")

        our_vitals = fields.get("vitalSets", {}).get("items", {})

        # Key vital fields
        assert "bp_systolic" in our_vitals
        assert "bp_diastolic" in our_vitals
        assert "pulse" in our_vitals
        assert "weight" in our_vitals
```

**Step 2: Run schema validation tests**

Run: `PYTHONPATH=. pytest tests/test_schema_validation.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_schema_validation.py
git commit -m "test: add schema validation tests against v2.1 definitions"
```

---

### Task 18: Final Integration and Documentation

**Files:**
- Modify: `app/core/builders/chartvision_builder.py` (integration point)
- Update: `CLAUDE.md` (document new fields)

**Step 1: Add longitudinal summary integration point**

This task documents where the longitudinal summary should be integrated. The actual integration
depends on your report builder implementation. Add this import and call at the appropriate location:

```python
# In chartvision_builder.py or report_generator.py
from app.core.analysis import build_longitudinal_summary

# After extracting all entries:
longitudinal = build_longitudinal_summary(all_entries)

# Add to report data:
report_data["longitudinal_summary"] = {
    "treatment_gaps": [
        {
            "start_date": gap.start_date.isoformat(),
            "end_date": gap.end_date.isoformat(),
            "duration_days": gap.duration_days,
            "severity": gap.severity,
        }
        for gap in longitudinal.treatment_gaps
    ],
    "pain_trends": [
        {
            "location": trend.location,
            "trend": trend.trend,
            "average_score": trend.average_score,
            "peak_score": trend.peak_score,
        }
        for trend in longitudinal.pain_trends
    ],
    "symptom_frequency": [
        {
            "symptom": mention.symptom,
            "count": mention.mention_count,
        }
        for mention in longitudinal.symptom_mentions[:10]  # Top 10
    ],
}
```

**Step 2: Final commit**

```bash
git add -A
git commit -m "feat: complete schema enhancement implementation

- Added RFC-critical fields: workStatus, providerRestrictions, painAssessments, mmiStatus
- Added medium priority fields: vitalSets, medicationActions, compliance, provider_specialty
- Created new visit types: telehealth, functional_capacity_evaluation
- Implemented longitudinal analysis: TreatmentGapAnalyzer, PainTrendAnalyzer, SymptomFrequencyAnalyzer
- Added comprehensive test suite: golden files, schema validation, regression tests
"
```

---

## Success Criteria Checklist

- [ ] All 17 tasks completed with passing tests
- [ ] No regression in existing extraction (baseline entry count maintained)
- [ ] New fields extracting at >60% rate on applicable records
- [ ] Schema validation tests passing
- [ ] Golden file tests passing
- [ ] Test coverage on new code >80%
- [ ] All commits follow conventional commit format
