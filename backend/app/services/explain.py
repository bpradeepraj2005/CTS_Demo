"""
Local explanations for the policy-fit model.

Attribution is computed by single-feature ablation against a reference profile:
for each feature, re-score the case with that one feature replaced by the
corpus reference value and take the difference. The result is the marginal
contribution of that feature *for this case*, in the units of the prediction.

Faithful, cheap (one forward pass per feature), and dependency-free. It is a
first-order approximation, so interactions are not decomposed -- the UI says so.
"""
import json
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ..config import MODELS_DIR
from . import ml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ml"))
from feature_schema import CATEGORICAL, derive_features  # noqa: E402

REFERENCE_PATH = MODELS_DIR / "reference_profile.json"

# Fields the clinician can act on, shown first in the explanation panel.
ACTIONABLE = {
    "documentation_score", "documentation_flag_sum", "doctor_note_present",
    "lab_results_present", "imaging_present", "medication_history_present",
    "documentation_complete", "previous_failed_count",
    "longest_previous_treatment_weeks", "requested_duration_months",
}

FRIENDLY = {
    "documentation_score": "Documentation completeness",
    "documentation_flag_sum": "Attachments provided",
    "doctor_note_present": "Clinical note attached",
    "lab_results_present": "Lab results attached",
    "imaging_present": "Imaging attached",
    "medication_history_present": "Medication history attached",
    "documentation_complete": "Documentation marked complete",
    "disease_severity": "Disease severity",
    "symptom_burden_0_10": "Symptom burden",
    "symptom_duration_months": "Symptom duration",
    "previous_treatment_count": "Prior therapies tried",
    "previous_failed_count": "Prior therapies failed",
    "previous_partial_response_count": "Partial responses",
    "previous_adverse_effect_count": "Adverse effects on prior therapy",
    "longest_previous_treatment_weeks": "Longest prior trial",
    "treatment_failure_ratio": "Failure rate on prior therapy",
    "requested_treatment": "Requested therapy",
    "requested_duration_months": "Requested duration",
    "request_reason": "Stated reason for request",
    "dose_category": "Dose category",
    "frequency": "Dosing frequency",
    "route": "Route of administration",
    "diagnosis": "Diagnosis",
    "diagnosis_code": "ICD-10 code",
    "comorbidities": "Comorbidities",
    "provider_specialty": "Ordering specialty",
    "provider_type": "Provider type",
    "provider_state": "Provider state",
    "payer": "Payer",
    "member_eligible": "Member eligibility",
    "treatment_covered": "Benefit coverage",
    "age": "Age",
    "sex": "Sex",
    "bmi": "BMI",
    "bmi_category": "BMI category",
    "age_group": "Age band",
    "total_prior_events": "Total prior treatment events",
}


@lru_cache(maxsize=1)
def reference_profile() -> dict:
    if REFERENCE_PATH.exists():
        return json.loads(REFERENCE_PATH.read_text())
    raise ml.ModelUnavailable(
        "reference_profile.json not found. Run: python ml/build_reference.py --csv <your.csv>"
    )


def explain_policy_fit(features: dict, top_n: int = 10) -> dict:
    bundle = ml._policy_fit_bundle()
    model = bundle["model"]
    columns = bundle["features"]
    ref = reference_profile()

    full = derive_features(features)
    base_df = ml.build_frame(features, columns)
    base_pred = float(model.predict(base_df)[0])

    rows = []
    for col in columns:
        if col not in ref:
            continue
        ablated = dict(full)
        ablated[col] = ref[col]
        rows.append((col, ablated))

    if not rows:
        return {"base_score": round(base_pred, 4), "contributions": []}

    frame = pd.DataFrame([{c: r[1].get(c) for c in columns} for r in rows],
                         columns=columns)
    for c in columns:
        if c in CATEGORICAL:
            frame[c] = frame[c].astype("category")
        else:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")

    preds = model.predict(frame)

    contributions = []
    for (col, _), ablated_pred in zip(rows, preds):
        delta = base_pred - float(ablated_pred)
        if abs(delta) < 1e-6:
            continue
        contributions.append({
            "feature": col,
            "label": FRIENDLY.get(col, col.replace("_", " ").capitalize()),
            "value": _fmt(full.get(col)),
            "reference": _fmt(ref[col]),
            "contribution": round(delta, 5),
            "direction": "supports" if delta > 0 else "weakens",
            "actionable": col in ACTIONABLE,
        })

    contributions.sort(key=lambda c: -abs(c["contribution"]))
    top = contributions[:top_n]
    return {
        "base_score": round(base_pred, 4),
        "reference_score": round(base_pred - sum(c["contribution"] for c in contributions), 4),
        "method": "single-feature ablation against corpus reference profile",
        "caveat": "First-order attribution. Feature interactions are not decomposed.",
        "contributions": top,
        "levers": [c for c in contributions if c["actionable"] and c["contribution"] < 0][:4],
    }


def _fmt(v):
    if isinstance(v, float):
        return round(v, 3)
    return v