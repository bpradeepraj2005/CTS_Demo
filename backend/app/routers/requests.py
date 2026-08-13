import shutil
import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter, Depends, File, HTTPException, UploadFile, status,
)
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..config import UPLOAD_DIR
from ..database import get_db
from ..models import Appeal, AuditEvent, AuthRequest, Document, Patient, User
from ..schemas import AppealCreate, RequestCreate
from ..security import current_user, require_provider
from ..services import ml
from ..services.pdf_extract import extract_from_file
from ..services.pipeline import adjudicate, log
from ..services.vocab import DIAGNOSIS_CODES

router = APIRouter(prefix="/api", tags=["requests"])

REQUIRED = [
    "age", "sex", "bmi", "diagnosis", "disease_severity", "symptom_burden_0_10",
    "symptom_duration_months", "requested_treatment", "dose_category",
    "frequency", "route", "requested_duration_months", "request_reason",
    "previous_treatment_count", "previous_failed_count",
    "previous_partial_response_count", "previous_adverse_effect_count",
    "longest_previous_treatment_weeks", "provider_specialty", "provider_state",
    "provider_type", "payer",
]


@router.post("/documents/upload", status_code=201)
def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Upload a PDF. Other formats are not read by the extractor.",
        )

    stored = UPLOAD_DIR / f"{uuid.uuid4().hex}.pdf"
    with stored.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)

    try:
        result = extract_from_file(stored)
    except Exception as exc:
        stored.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Could not read this PDF: {exc}",
        )

    if result["char_count"] < 50:
        stored.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No selectable text found. This looks like a scanned image — run OCR "
            "on it first, then upload again.",
        )

    fields = result["fields"]
    doc = Document(
        request_id=None,
        uploaded_by=user.id,
        filename=file.filename,
        stored_path=str(stored),
        page_count=result["page_count"],
        char_count=result["char_count"],
        extraction_confidence=result["confidence"],
        extracted_fields=fields,
        unmatched_fields=result["unmatched"],
        raw_text=result["raw_text"],
    )
    db.add(doc)
    db.flush()
    log(db, "DOCUMENT_UPLOADED", actor=user, detail={
        "document_id": doc.id, "filename": file.filename,
        "pages": result["page_count"], "confidence": result["confidence"],
        "unmatched_count": len(result["unmatched"]),
    })
    db.commit()

    still_missing = [f for f in REQUIRED if fields.get(f) in (None, "")]
    return {
        "document_id": doc.id,
        "filename": file.filename,
        "page_count": result["page_count"],
        "char_count": result["char_count"],
        "extraction_confidence": result["confidence"],
        "fields": {k: v for k, v in fields.items() if not k.startswith("_")},
        "patient_name": fields.get("_patient_name"),
        "mrn": fields.get("_mrn"),
        "missing_required": still_missing,
    }


@router.post("/requests", status_code=201)
def create_request(
    body: RequestCreate,
    user: User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    features = dict(body.features)
    missing = [f for f in REQUIRED if features.get(f) in (None, "")]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Fill in these fields before submitting: " + ", ".join(missing),
        )

    if not features.get("diagnosis_code"):
        features["diagnosis_code"] = DIAGNOSIS_CODES.get(features.get("diagnosis"))
    features.setdefault("comorbidities", "Unknown")
    for flag in ("doctor_note_present", "lab_results_present", "imaging_present",
                 "medication_history_present", "documentation_complete",
                 "member_eligible", "treatment_covered"):
        features[flag] = int(features.get(flag, 0) or 0)

    patient = None
    if body.patient_name or body.mrn:
        patient = Patient(
            organization_id=user.organization_id,
            mrn=body.mrn, full_name=body.patient_name,
            age=features.get("age"), sex=features.get("sex"),
        )
        db.add(patient)
        db.flush()

    count = db.query(AuthRequest).count() + 1
    req = AuthRequest(
        case_number=f"PA-{datetime.now(timezone.utc):%Y%m}-{count:06d}",
        organization_id=user.organization_id,
        created_by=user.id,
        patient_id=patient.id if patient else None,
        features=features,
        status="SUBMITTED",
    )
    db.add(req)
    db.flush()

    log(db, "REQUEST_SUBMITTED", request_id=req.id, actor=user,
        detail={"case_number": req.case_number,
                "diagnosis": features.get("diagnosis"),
                "treatment": features.get("requested_treatment")})

    if body.document_id:
        doc = db.get(Document, body.document_id)
        if doc and doc.uploaded_by == user.id:
            doc.request_id = req.id

    try:
        adjudicate(db, req, user)
    except ml.ModelUnavailable as exc:
        db.rollback()
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))

    db.commit()
    db.refresh(req)
    return _detail(db, req)


@router.get("/requests")
def list_requests(
    user: User = Depends(require_provider),
    db: Session = Depends(get_db),
    status_filter: str | None = None,
):
    q = db.query(AuthRequest).filter(
        AuthRequest.organization_id == user.organization_id
    )
    if status_filter:
        q = q.filter(AuthRequest.status == status_filter)
    rows = q.order_by(desc(AuthRequest.created_at)).limit(300).all()
    return [_summary(r) for r in rows]


@router.get("/requests/{request_id}")
def get_request(
    request_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    if user.role == "PROVIDER_STAFF" and req.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case belongs to another organization")
    return _detail(db, req)


@router.post("/requests/{request_id}/appeal", status_code=201)
def file_appeal(
    request_id: str,
    body: AppealCreate,
    user: User = Depends(require_provider),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None or req.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    if req.decision != "DENIED":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only denied cases can be appealed"
        )
    if db.query(Appeal).filter(Appeal.request_id == req.id,
                               Appeal.status == "OPEN").first():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "An appeal is already open on this case")

    appeal = Appeal(
        request_id=req.id, filed_by=user.id, rationale=body.rationale,
        new_documentation=body.new_documentation,
        predicted_at_filing=req.appeal_prediction,
    )
    db.add(appeal)
    req.status = "APPEALED"
    log(db, "APPEAL_FILED", request_id=req.id, actor=user, detail={
        "new_documentation": body.new_documentation,
        "model_predicted": (req.appeal_prediction or {}).get("top_class"),
        "model_any_appeal_probability":
            (req.appeal_prediction or {}).get("any_appeal_probability"),
    })
    db.commit()
    db.refresh(appeal)
    return {"appeal_id": appeal.id, "status": appeal.status,
            "request_status": req.status}


@router.get("/requests/{request_id}/audit")
def audit_trail(
    request_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    if user.role == "PROVIDER_STAFF" and req.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case belongs to another organization")
    events = (
        db.query(AuditEvent)
        .filter(AuditEvent.request_id == request_id)
        .order_by(AuditEvent.created_at)
        .all()
    )
    return [
        {"id": e.id, "action": e.action, "actor_email": e.actor_email,
         "detail": e.detail, "created_at": e.created_at}
        for e in events
    ]


def _summary(r: AuthRequest) -> dict:
    f = r.features or {}
    return {
        "id": r.id, "case_number": r.case_number, "status": r.status,
        "decision": r.decision, "decision_source": r.decision_source,
        "created_at": r.created_at,
        "policy_fit_score": r.policy_fit_score,
        "necessity_score": r.necessity_score,
        "urgency_score": r.urgency_score,
        "confidence": r.confidence,
        "processing_ms": r.processing_ms,
        "assigned_reviewer_id": r.assigned_reviewer_id,
        "assignment_reason": r.assignment_reason,
        "assignment_was_reassigned": r.assignment_was_reassigned,
        "diagnosis": f.get("diagnosis"),
        "requested_treatment": f.get("requested_treatment"),
        "disease_severity": f.get("disease_severity"),
        "payer": f.get("payer"),
        "provider_specialty": f.get("provider_specialty"),
        "appeal_probability": (r.appeal_prediction or {}).get("any_appeal_probability"),
    }


def _detail(db: Session, r: AuthRequest) -> dict:
    reviewer = db.get(User, r.assigned_reviewer_id) if r.assigned_reviewer_id else None
    appeals = db.query(Appeal).filter(Appeal.request_id == r.id).all()
    docs = db.query(Document).filter(Document.request_id == r.id).all()
    out = _summary(r)
    out.update({
        "features": r.features,
        "criteria": r.criteria,
        "explanation": r.explanation,
        "appeal_prediction": r.appeal_prediction,
        "reviewer_notes": r.reviewer_notes,
        "documentation_score": r.documentation_score,
        "assigned_reviewer": (
            {"id": reviewer.id, "name": reviewer.full_name,
             "specialty": reviewer.specialty} if reviewer else None
        ),
        "documents": [
            {"id": d.id, "filename": d.filename, "page_count": d.page_count,
             "extraction_confidence": d.extraction_confidence}
            for d in docs
        ],
        "appeals": [
            {"id": a.id, "status": a.status, "rationale": a.rationale,
             "new_documentation": a.new_documentation,
             "outcome_notes": a.outcome_notes, "created_at": a.created_at}
            for a in appeals
        ],
    })
    return out