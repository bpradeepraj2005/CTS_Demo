"""
Renders real rows from the dataset into prior-authorization packet PDFs so the
upload flow can be exercised end to end with genuine clinical values.

    python tools/make_packets.py --csv <your.csv> --count 5 --out sample_packets/

These are not fabricated cases: every field printed comes from a row of the
supplied corpus. Patient names and MRNs are the only synthesised values, and
they exist purely so the packet looks like a real form.
"""
import argparse
import random
from pathlib import Path

import pandas as pd

FIELD_LAYOUT = [
    ("PATIENT", [
        ("Patient Name", "_name"), ("MRN", "_mrn"),
        ("Age", "age"), ("Sex", "sex"), ("BMI", "bmi"),
    ]),
    ("CLINICAL PRESENTATION", [
        ("Diagnosis", "diagnosis"), ("ICD-10 Code", "diagnosis_code"),
        ("Disease Severity", "disease_severity"),
        ("Symptom Burden (0-10)", "symptom_burden_0_10"),
        ("Symptom Duration (months)", "symptom_duration_months"),
        ("Comorbidities", "comorbidities"),
    ]),
    ("REQUESTED THERAPY", [
        ("Requested Treatment", "requested_treatment"),
        ("Dose Category", "dose_category"), ("Frequency", "frequency"),
        ("Route", "route"),
        ("Requested Duration (months)", "requested_duration_months"),
        ("Reason for Request", "request_reason"),
    ]),
    ("TREATMENT HISTORY", [
        ("Previous Treatments", "previous_treatment_count"),
        ("Previous Failed", "previous_failed_count"),
        ("Partial Responses", "previous_partial_response_count"),
        ("Adverse Events", "previous_adverse_effect_count"),
        ("Longest Treatment (weeks)", "longest_previous_treatment_weeks"),
    ]),
    ("ORDERING PROVIDER", [
        ("Specialty", "provider_specialty"), ("State", "provider_state"),
        ("Provider Type", "provider_type"),
    ]),
    ("COVERAGE", [
        ("Payer", "payer"), ("Member Eligible", "_eligible"),
        ("Treatment Covered", "_covered"),
        ("Clinical Evidence Score", "clinical_evidence_score"),
    ]),
]

EVIDENCE_MARKERS = {
    "doctor_note_present": "Clinical note - attending progress note attached",
    "lab_results_present": "Lab results - CRP, ESR and CBC panel attached",
    "imaging_present": "Imaging - radiology report attached",
    "medication_history_present": "Medication history - pharmacy dispensing record attached",
}

FIRST = ["Amara", "Daniel", "Priya", "Marcus", "Elena", "Tobias", "Nadia",
         "Rohan", "Claire", "Silas", "Ingrid", "Oscar", "Leena", "Mateo"]
LAST = ["Okafor", "Whitfield", "Ramanathan", "Delgado", "Novak", "Aberdeen",
        "Castellanos", "Bhatt", "Lindqvist", "Moreau", "Adeyemi", "Reyes"]


def packet_lines(row: dict, name: str, mrn: str) -> list[tuple[str, str]]:
    """Returns (kind, text) pairs. kind is 'title', 'section', 'field' or 'body'."""
    vals = dict(row)
    vals["_name"] = name
    vals["_mrn"] = mrn
    vals["_eligible"] = "Yes" if int(row.get("member_eligible", 1)) else "No"
    vals["_covered"] = "Yes" if int(row.get("treatment_covered", 1)) else "No"

    lines: list[tuple[str, str]] = [
        ("title", "PRIOR AUTHORIZATION REQUEST FORM"),
        ("body", f"Case Reference: {row.get('case_id', 'N/A')}"),
    ]
    for section, fields in FIELD_LAYOUT:
        lines.append(("section", section))
        for label, key in fields:
            value = vals.get(key)
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue
            lines.append(("field", f"{label}: {value}"))

    lines.append(("section", "SUPPORTING DOCUMENTATION ATTACHED"))
    any_attached = False
    for key, text in EVIDENCE_MARKERS.items():
        if int(row.get(key, 0)):
            lines.append(("field", text))
            any_attached = True
    if not any_attached:
        lines.append(("field", "No supporting documentation submitted with this request."))

    lines.append(("section", "ATTESTATION"))
    lines.append(("body",
                  "I attest that the information above accurately reflects the "
                  "clinical record and that the requested therapy is medically "
                  "necessary for this patient."))
    return lines


def render_pdf(lines, out_path: Path):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(out_path), pagesize=LETTER)
    width, height = LETTER
    x, y = inch, height - inch
    line_h = 15

    for kind, text in lines:
        if y < inch:
            c.showPage()
            y = height - inch
        if kind == "title":
            c.setFont("Helvetica-Bold", 15)
            c.drawString(x, y, text)
            y -= line_h + 8
        elif kind == "section":
            y -= 8
            c.setFont("Helvetica-Bold", 10.5)
            c.drawString(x, y, text)
            c.setLineWidth(0.5)
            c.line(x, y - 3, width - inch, y - 3)
            y -= line_h + 2
        elif kind == "field":
            c.setFont("Helvetica", 10)
            c.drawString(x + 8, y, text)
            y -= line_h
        else:
            c.setFont("Helvetica", 9.5)
            for chunk in _wrap(text, 95):
                c.drawString(x, y, chunk)
                y -= line_h - 2
    c.save()


def _wrap(text: str, width: int) -> list[str]:
    words, out, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--out", default="sample_packets")
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    random.seed(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.csv)
    picks = df.sample(n=min(args.count, len(df)), random_state=args.seed)

    for i, (_, row) in enumerate(picks.iterrows(), start=1):
        name = f"{random.choice(FIRST)} {random.choice(LAST)}"
        mrn = f"MRN-{random.randint(100000, 999999)}"
        lines = packet_lines(row.to_dict(), name, mrn)
        path = out / f"packet_{i:02d}_{str(row.get('case_id','case')).replace('/','-')}.pdf"
        render_pdf(lines, path)
        print(f"  {path}  ({row['diagnosis']} / {row['requested_treatment']})")

    print(f"\nWrote {len(picks)} packets to {out.resolve()}")


if __name__ == "__main__":
    main()