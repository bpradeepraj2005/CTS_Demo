"""
Prior Authorization PDF extraction service.

Extracts the clinical and administrative fields required by the
prior-authorization decision engine.

Extraction priority:
1. Labelled field capture
2. Controlled vocabulary matching
3. Evidence/section detection

Important:
- Never silently invent a missing value.
- Fields that cannot be confidently extracted are returned in `unmatched`.
- Payer is captured directly from the PDF label before vocabulary matching.
"""

import re
from pathlib import Path

from .vocab import (
    COMORBIDITIES,
    DIAGNOSIS_CODES,
    DIAGNOSES,
    DOSE_CATEGORIES,
    FREQUENCIES,
    PAYERS,
    PROVIDER_TYPES,
    REQUEST_REASONS,
    ROUTES,
    SEVERITIES,
    SPECIALTIES,
    STATES,
    TREATMENTS,
)


NUM = r"([-+]?\d+(?:\.\d+)?)"


# ============================================================
# PDF TEXT READING
# ============================================================

def read_pdf(path: str) -> tuple[str, int]:
    """
    Read text from a PDF using pdfplumber.

    Also reads tables because the generated PA packets
    store most clinical fields inside tables.
    """

    import pdfplumber

    text_parts = []
    pages = 0

    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)

        for page in pdf.pages:

            text = page.extract_text() or ""

            if text:
                text_parts.append(text)

            tables = page.extract_tables() or []

            for table in tables:
                for row in table:
                    if not row:
                        continue

                    cells = [
                        str(cell).strip()
                        for cell in row
                        if cell is not None and str(cell).strip()
                    ]

                    if cells:
                        text_parts.append(" | ".join(cells))

    return "\n".join(text_parts), pages


# ============================================================
# NORMALIZATION
# ============================================================

def _normalize_text(value: str) -> str:
    if value is None:
        return ""

    value = str(value)

    # Normalize PDF whitespace
    value = value.replace("\xa0", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\r\n?", "\n", value)

    return value.strip()


def _clean_value(value: str | None) -> str | None:

    if value is None:
        return None

    value = _normalize_text(value)

    value = value.strip(" .,:;|-")

    if not value:
        return None

    if value.lower() in {
        "n/a",
        "na",
        "none",
        "unknown",
        "-",
        "not available",
        "not provided",
    }:
        return None

    return value


# ============================================================
# LABEL EXTRACTION
# ============================================================

def _label(text: str, *labels) -> str | None:
    """
    Extract values from labelled fields.

    Supports formats such as:

        Payer: Granite Health Assurance
        Payer - Granite Health Assurance
        Payer | Granite Health Assurance

    Also supports table-style text where the label and value
    are separated by whitespace.
    """

    text = _normalize_text(text)

    for label in labels:

        # ----------------------------------------------------
        # Standard labelled format
        # ----------------------------------------------------

        pattern = rf"""
            (?im)
            ^\s*
            {label}
            \s*(?::|\-|\|)\s*
            ([^\n|]+)
        """

        match = re.search(pattern, text, re.VERBOSE)

        if match:
            value = _clean_value(match.group(1))

            if value:
                return value

        # ----------------------------------------------------
        # Same-line table style
        #
        # Example:
        # Payer Granite Health Assurance
        # ----------------------------------------------------

        pattern = rf"""
            (?im)
            \b
            {label}
            \s+
            ([^\n|]+)
        """

        match = re.search(pattern, text, re.VERBOSE)

        if match:
            value = _clean_value(match.group(1))

            if value:

                # Avoid returning the label itself
                if value.lower() != label.lower():
                    return value

    return None


# ============================================================
# NUMERIC LABEL EXTRACTION
# ============================================================

def _label_num(text: str, *labels) -> float | None:

    text = _normalize_text(text)

    for label in labels:

        pattern = rf"""
            (?im)
            \b
            {label}
            \s*
            (?::|\-|\|)?
            \s*
            {NUM}
        """

        match = re.search(pattern, text, re.VERBOSE)

        if match:
            try:
                return float(match.group(1))
            except (ValueError, TypeError):
                pass

    return None


# ============================================================
# CONTROLLED VOCABULARY
# ============================================================

def _vocab(
    text: str,
    options,
    labelled: str | None = None,
) -> str | None:

    text = _normalize_text(text)

    # First use the labelled value
    if labelled:

        labelled_clean = _clean_value(labelled)

        if labelled_clean:

            low = labelled_clean.lower()

            # Exact match
            for option in options:

                if option.lower() == low:
                    return option

            # Partial match
            for option in options:

                option_low = option.lower()

                if option_low in low or low in option_low:
                    return option

    # Then search entire document
    low_text = text.lower()

    hits = []

    for option in options:

        option_low = option.lower()

        if option_low in low_text:
            hits.append(option)

    if hits:
        return max(hits, key=len)

    return None


# ============================================================
# BOOLEAN / EVIDENCE
# ============================================================

def _flag(text: str, *markers) -> int:

    low = _normalize_text(text).lower()

    return int(
        any(marker.lower() in low for marker in markers)
    )


def _yesno(
    value: str | None,
    default: int = 0,
) -> int:

    if not value:
        return default

    low = value.strip().lower()

    if low.startswith(
        (
            "yes",
            "true",
            "1",
            "present",
            "active",
            "eligible",
            "covered",
        )
    ):
        return 1

    if low.startswith(
        (
            "no",
            "false",
            "0",
            "absent",
            "inactive",
            "not",
            "terminated",
        )
    ):
        return 0

    return default


def _int(value):

    if value is None:
        return None

    try:
        return int(round(float(value)))
    except (ValueError, TypeError):
        return None


# ============================================================
# SPECIAL EXTRACTION HELPERS
# ============================================================

def _extract_previous_failed_count(text: str):

    """
    Handles multiple real-world variations:

        Previous Failures 1
        Previous Failure 1
        Previous Failed Count 1
        Previous Treatment Failures 1
        Previous Treatment Failure 1
        Failed Therapies 1
        Treatment Failures 1
        Previous Treatments Failed 1

    Also handles table-style PDFs where there is no colon.
    """

    patterns = [

        r"Previous\s+Failed\s+Count\s*[:\-|]?\s*" + NUM,

        r"Previous\s+Failures?\s*[:\-|]?\s*" + NUM,

        r"Previous\s+Treatment\s+Failures?\s*[:\-|]?\s*" + NUM,

        r"Previous\s+Treatments?\s+Failed\s*[:\-|]?\s*" + NUM,

        r"Failed\s+Therap(?:y|ies)\s*[:\-|]?\s*" + NUM,

        r"Treatment\s+Failures?\s*[:\-|]?\s*" + NUM,

        r"Number\s+of\s+Previous\s+Failures?\s*[:\-|]?\s*" + NUM,
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            return _int(match.group(1))

    return None


def _extract_payer(text: str):

    """
    Extract payer directly from the labelled PDF field.

    This intentionally happens BEFORE PAYERS vocabulary matching.

    That means a valid payer appearing in the PDF is not lost
    simply because it has not yet been added to vocab.py.
    """

    # Most reliable labelled forms
    payer = _label(
        text,
        r"payer",
        r"insurance\s+carrier",
        r"insurance\s+company",
        r"insurer",
        r"health\s+plan",
        r"plan\s+name",
    )

    if payer:
        return payer

    # Controlled vocabulary fallback
    return _vocab(text, PAYERS)


# ============================================================
# MAIN FIELD EXTRACTION
# ============================================================

def extract_fields(
    text: str,
) -> tuple[dict, list[str], float]:

    text = _normalize_text(text)

    fields = {}
    unmatched = []

    def put(key, value):

        value = _clean_value(value)

        if value is None:
            unmatched.append(key)
        else:
            fields[key] = value

    # ========================================================
    # DEMOGRAPHICS
    # ========================================================

    put(
        "age",
        _int(
            _label_num(
                text,
                r"age",
                r"patient\s+age",
            )
        ),
    )

    sex_raw = _label(
        text,
        r"sex",
        r"gender",
    )

    sex = None

    if sex_raw:

        s = sex_raw.strip().upper()

        if s.startswith("F"):
            sex = "F"

        elif s.startswith("M"):
            sex = "M"

    put("sex", sex)

    put(
        "bmi",
        _label_num(
            text,
            r"bmi",
            r"body\s+mass\s+index",
        ),
    )

    # ========================================================
    # CONDITION
    # ========================================================

    diagnosis_label = _label(
        text,
        r"diagnosis",
        r"primary\s+diagnosis",
        r"indication",
        r"condition",
    )

    diagnosis = _vocab(
        text,
        DIAGNOSES,
        diagnosis_label,
    )

    # If vocabulary does not contain the diagnosis,
    # preserve the labelled value.
    if diagnosis is None:
        diagnosis = diagnosis_label

    put(
        "diagnosis",
        diagnosis,
    )

    # Diagnosis code
    code = _label(
        text,
        r"icd[- ]?10(?:\s+code)?",
        r"diagnosis\s+code",
    )

    if code:

        match = re.search(
            r"\b[A-Z]\d{2}(?:\.\d{1,3})?\b",
            code.upper(),
        )

        code = (
            match.group(0)
            if match
            else None
        )

    if not code and diagnosis:

        code = DIAGNOSIS_CODES.get(
            diagnosis
        )

    if not code:

        match = re.search(
            r"\b([A-Z]\d{2}\.\d{1,3})\b",
            text,
        )

        code = (
            match.group(1)
            if match
            else None
        )

    put(
        "diagnosis_code",
        code,
    )

    severity_label = _label(
        text,
        r"severity",
        r"disease\s+severity",
    )

    severity = _vocab(
        text,
        SEVERITIES,
        severity_label,
    )

    if severity is None:
        severity = severity_label

    put(
        "disease_severity",
        severity,
    )

    put(
        "symptom_burden_0_10",
        _label_num(
            text,
            r"symptom\s+burden(?:\s*\(0[- ]?10\))?",
            r"symptom\s+score",
            r"pain\s+score",
        ),
    )

    put(
        "symptom_duration_months",
        _int(
            _label_num(
                text,
                r"symptom\s+duration(?:\s*\(months\))?",
                r"duration\s+of\s+symptoms",
            )
        ),
    )

    comorbidity_label = _label(
        text,
        r"comorbidit(?:y|ies)",
        r"co[- ]?morbidities",
    )

    comorbidities = _vocab(
        text,
        COMORBIDITIES,
        comorbidity_label,
    )

    if comorbidities is None:
        comorbidities = (
            comorbidity_label
            or "Unknown"
        )

    put(
        "comorbidities",
        comorbidities,
    )

    # ========================================================
    # REQUESTED THERAPY
    # ========================================================

    treatment_label = _label(
        text,
        r"requested\s+treatment",
        r"requested\s+(?:drug|medication|therapy)",
        r"treatment\s+requested",
        r"drug",
    )

    treatment = _vocab(
        text,
        TREATMENTS,
        treatment_label,
    )

    if treatment is None:
        treatment = treatment_label

    put(
        "requested_treatment",
        treatment,
    )

    dose_label = _label(
        text,
        r"dose(?:\s+category)?",
        r"dosing",
    )

    put(
        "dose_category",
        _vocab(
            text,
            DOSE_CATEGORIES,
            dose_label,
        ) or dose_label,
    )

    frequency_label = _label(
        text,
        r"frequency",
        r"dosing\s+frequency",
    )

    put(
        "frequency",
        _vocab(
            text,
            FREQUENCIES,
            frequency_label,
        ) or frequency_label,
    )

    route_label = _label(
        text,
        r"route(?:\s+of\s+administration)?",
    )

    put(
        "route",
        _vocab(
            text,
            ROUTES,
            route_label,
        ) or route_label,
    )

    duration = _int(
        _label_num(
            text,
            r"requested\s+duration(?:\s*\(months\))?",
            r"treatment\s+duration",
            r"duration\s*\(months\)",
        )
    )

    put(
        "requested_duration_months",
        duration,
    )

    reason_label = _label(
        text,
        r"reason\s+for\s+request",
        r"request\s+reason",
        r"justification",
    )

    put(
        "request_reason",
        _vocab(
            text,
            REQUEST_REASONS,
            reason_label,
        ) or reason_label,
    )

    # ========================================================
    # TREATMENT HISTORY
    # ========================================================

    put(
        "previous_treatment_count",
        _int(
            _label_num(
                text,
                r"previous\s+treatments?(?:\s+count)?",
                r"prior\s+therap(?:y|ies)",
            )
        ),
    )

    # IMPORTANT FIX:
    # robust previous-failure extraction
    put(
        "previous_failed_count",
        _extract_previous_failed_count(text),
    )

    put(
        "previous_partial_response_count",
        _int(
            _label_num(
                text,
                r"previous\s+partial\s+responses?",
                r"partial\s+responses?(?:\s+count)?",
            )
        ),
    )

    put(
        "previous_adverse_effect_count",
        _int(
            _label_num(
                text,
                r"previous\s+adverse\s+effects?",
                r"adverse\s+(?:effect|event)s?(?:\s+count)?",
            )
        ),
    )

    put(
        "longest_previous_treatment_weeks",
        _int(
            _label_num(
                text,
                r"longest\s+(?:previous\s+)?treatment(?:\s*\(weeks\))?",
                r"longest\s+trial",
            )
        ),
    )

    # ========================================================
    # EVIDENCE
    # ========================================================

    fields["doctor_note_present"] = _flag(
        text,
        "clinical note",
        "physician note",
        "doctor note",
        "progress note",
        "chart note",
        "attending note",
        "clinical documentation",
    )

    fields["lab_results_present"] = _flag(
        text,
        "lab result",
        "laboratory",
        "labs attached",
        "serology",
        "crp",
        "esr",
        "hba1c",
        "blood panel",
    )

    fields["imaging_present"] = _flag(
        text,
        "imaging",
        "radiology",
        "mri",
        "ct scan",
        "x-ray",
        "ultrasound",
        "colonoscopy",
        "endoscopy",
    )

    fields["medication_history_present"] = _flag(
        text,
        "medication history",
        "pharmacy record",
        "med history",
        "prescription history",
        "drug history",
    )

    # If the PDF explicitly says Documentation Complete,
    # respect that value.
    documentation_label = _label(
        text,
        r"documentation\s+complete",
    )

    if documentation_label:
        fields["documentation_complete"] = _yesno(
            documentation_label,
            default=0,
        )
    else:
        evidence_sum = sum(
            fields[k]
            for k in (
                "doctor_note_present",
                "lab_results_present",
                "imaging_present",
                "medication_history_present",
            )
        )

        fields["documentation_complete"] = int(
            evidence_sum == 4
        )

    # ========================================================
    # PROVIDER
    # ========================================================

    specialty_label = _label(
        text,
        r"specialty",
        r"provider\s+specialty",
        r"department",
    )

    put(
        "provider_specialty",
        _vocab(
            text,
            SPECIALTIES,
            specialty_label,
        ) or specialty_label,
    )

    # Provider state
    state_label = _label(
        text,
        r"provider\s+state",
        r"state",
    )

    state = None

    if state_label:

        state_upper = (
            state_label
            .strip()
            .upper()
        )

        if state_upper in STATES:
            state = state_upper

    if not state:

        state_pattern = (
            r"\b("
            + "|".join(
                re.escape(s)
                for s in STATES
            )
            + r")\b"
        )

        match = re.search(
            state_pattern,
            text,
            re.IGNORECASE,
        )

        if match:
            state = match.group(1).upper()

    put(
        "provider_state",
        state,
    )

    provider_type_label = _label(
        text,
        r"provider\s+type",
        r"facility\s+type",
    )

    put(
        "provider_type",
        _vocab(
            text,
            PROVIDER_TYPES,
            provider_type_label,
        ) or provider_type_label,
    )

    # ========================================================
    # PAYER
    # ========================================================

    # IMPORTANT FIX:
    # Capture the actual labelled payer first.
    payer = _extract_payer(text)

    put(
        "payer",
        payer,
    )

    # ========================================================
    # COVERAGE
    # ========================================================

    eligibility_label = _label(
        text,
        r"member\s+eligib(?:le|ility)",
        r"eligibility\s+status",
    )

    fields["member_eligible"] = _yesno(
        eligibility_label,
        default=0,
    )

    coverage_label = _label(
        text,
        r"treatment\s+covered",
        r"coverage\s+status",
        r"covered\s+benefit",
    )

    fields["treatment_covered"] = _yesno(
        coverage_label,
        default=0,
    )

    pa_label = _label(
        text,
        r"prior\s+authorization\s+required",
        r"pa\s+required",
    )

    fields["prior_authorization_required"] = _yesno(
        pa_label,
        default=1,
    )

    # ========================================================
    # SCORES
    # ========================================================

    clinical_score = _label_num(
        text,
        r"clinical\s+evidence\s+score",
        r"evidence\s+score",
    )

    if clinical_score is not None:

        if clinical_score > 1:
            clinical_score /= 100.0

        fields["clinical_evidence_score"] = (
            max(0.0, min(1.0, clinical_score))
        )

    documentation_score = _label_num(
        text,
        r"documentation\s+score",
    )

    if documentation_score is not None:

        if documentation_score > 1:
            documentation_score /= 100.0

        fields["documentation_score"] = (
            max(
                0.0,
                min(
                    1.0,
                    documentation_score,
                ),
            )
        )

    policy_fit_score = _label_num(
        text,
        r"policy\s+fit\s+score",
    )

    if policy_fit_score is not None:

        if policy_fit_score > 1:
            policy_fit_score /= 100.0

        fields["policy_fit_score"] = (
            max(
                0.0,
                min(
                    1.0,
                    policy_fit_score,
                ),
            )
        )

    # ========================================================
    # IDENTIFIERS
    # ========================================================

    fields["_patient_name"] = _label(
        text,
        r"patient\s+name",
        r"patient",
    )

    fields["_mrn"] = _label(
        text,
        r"mrn",
        r"medical\s+record\s+(?:number|no)",
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    required_fields = 24

    confidence = round(
        max(
            0.0,
            min(
                1.0,
                (
                    required_fields
                    - len(unmatched)
                )
                / required_fields,
            ),
        ),
        3,
    )

    return (
        fields,
        unmatched,
        confidence,
    )


# ============================================================
# PUBLIC API
# ============================================================

def extract_from_file(
    path: str | Path,
) -> dict:

    text, pages = read_pdf(
        str(path)
    )

    fields, unmatched, confidence = (
        extract_fields(text)
    )

    return {
        "fields": fields,
        "unmatched": unmatched,
        "confidence": confidence,
        "page_count": pages,
        "char_count": len(text),
        "raw_text": text[:20000],
    }