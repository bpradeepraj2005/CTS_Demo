"""
Every number here is a live aggregate over the database. Nothing is seeded,
cached, or hardcoded — an empty database returns zeros and the UI says so.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Appeal, AuditEvent, AuthRequest, Document, User
from ..security import current_user, require_payer, require_provider
from ..services import ml

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

AUTO = {"AUTO_APPROVED", "AUTO_DENIED"}
FINAL = {"AUTO_APPROVED", "AUTO_DENIED", "APPROVED", "DENIED"}


def _pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def _trend(rows, days=14):
    today = datetime.now(timezone.utc).date()
    buckets = {today - timedelta(days=i): {"submitted": 0, "approved": 0, "denied": 0}
               for i in range(days)}
    for r in rows:
        created = r.created_at
        if created is None:
            continue
        d = created.date()
        if d in buckets:
            buckets[d]["submitted"] += 1
            if r.decision == "APPROVED":
                buckets[d]["approved"] += 1
            elif r.decision == "DENIED":
                buckets[d]["denied"] += 1
    return [
        {"date": d.isoformat(), **v}
        for d, v in sorted(buckets.items())
    ]


@router.get("/provider")
def provider_dashboard(
    user: User = Depends(require_provider), db: Session = Depends(get_db)
):
    rows = db.query(AuthRequest).filter(
        AuthRequest.organization_id == user.organization_id
    ).all()
    total = len(rows)
    decided = [r for r in rows if r.status in FINAL]
    auto = [r for r in rows if r.status in AUTO]
    approved = [r for r in decided if r.decision == "APPROVED"]
    denied = [r for r in decided if r.decision == "DENIED"]
    pending = [r for r in rows if r.status == "PENDING_REVIEW"]
    times = [r.processing_ms for r in rows if r.processing_ms]

    docs = (
        db.query(func.count(Document.id), func.avg(Document.extraction_confidence))
        .join(AuthRequest, Document.request_id == AuthRequest.id)
        .filter(AuthRequest.organization_id == user.organization_id)
        .first()
    )
    appeal_probs = [
        (r.appeal_prediction or {}).get("any_appeal_probability")
        for r in denied
    ]
    appeal_probs = [p for p in appeal_probs if p is not None]

    return {
        "empty": total == 0,
        "kpis": {
            "total_requests": total,
            "instant_decision_rate": _pct(len(auto), total),
            "approval_rate": _pct(len(approved), len(decided)),
            "denial_rate": _pct(len(denied), len(decided)),
            "pending_review": len(pending),
            "avg_processing_ms": round(sum(times) / len(times), 1) if times else 0.0,
            "p95_processing_ms": (
                round(sorted(times)[int(len(times) * 0.95) - 1], 1)
                if len(times) >= 20 else (round(max(times), 1) if times else 0.0)
            ),
            "under_5s_rate": _pct(sum(1 for t in times if t < 5000), len(times)),
            "documents_processed": docs[0] or 0,
            "avg_extraction_confidence": round(float(docs[1] or 0), 3),
            "mean_appeal_risk_on_denials": (
                round(sum(appeal_probs) / len(appeal_probs), 3) if appeal_probs else 0.0
            ),
        },
        "status_breakdown": [
            {"status": k, "count": v}
            for k, v in Counter(r.status for r in rows).most_common()
        ],
        "top_denial_reasons": _denial_reasons(rows),
        "by_specialty": [
            {"name": k, "count": v}
            for k, v in Counter(
                (r.features or {}).get("provider_specialty") for r in rows
            ).most_common(8) if k
        ],
        "by_treatment": [
            {"name": k, "count": v}
            for k, v in Counter(
                (r.features or {}).get("requested_treatment") for r in rows
            ).most_common(8) if k
        ],
        "trend": _trend(rows),
    }


def _denial_reasons(rows):
    counter = Counter()
    labels = {}
    for r in rows:
        if r.decision != "DENIED" or not r.criteria:
            continue
        for c in r.criteria.get("criteria", []):
            if not c.get("passed"):
                counter[c["code"]] += 1
                labels[c["code"]] = c["label"]
    return [
        {"code": k, "label": labels.get(k, k), "count": v}
        for k, v in counter.most_common(6)
    ]


@router.get("/payer")
def payer_dashboard(
    user: User = Depends(require_payer), db: Session = Depends(get_db)
):
    rows = db.query(AuthRequest).all()
    total = len(rows)
    decided = [r for r in rows if r.status in FINAL]
    auto = [r for r in rows if r.status in AUTO]
    pending = [r for r in rows if r.status == "PENDING_REVIEW"]
    mine = [r for r in pending if r.assigned_reviewer_id == user.id]
    unassigned = [r for r in pending if r.assigned_reviewer_id is None]
    reassigned = [r for r in rows if r.assignment_was_reassigned]
    times = [r.processing_ms for r in rows if r.processing_ms]

    appeals = db.query(Appeal).all()
    overturned = [a for a in appeals if a.status == "OVERTURNED"]

    overrides = db.query(AuditEvent).filter(
        AuditEvent.action == "REVIEWER_DECISION"
    ).all()
    disagreements = [
        e for e in overrides if e.detail and e.detail.get("agreed_with_engine") is False
    ]

    reviewers = db.query(User).filter(User.role == "PAYER_REVIEWER").all()
    load = Counter(r.assigned_reviewer_id for r in pending if r.assigned_reviewer_id)

    return {
        "empty": total == 0,
        "kpis": {
            "total_requests": total,
            "instant_decision_rate": _pct(len(auto), total),
            "pending_review": len(pending),
            "my_queue": len(mine),
            "unassigned": len(unassigned),
            "auto_reassigned": len(reassigned),
            "avg_processing_ms": round(sum(times) / len(times), 1) if times else 0.0,
            "under_5s_rate": _pct(sum(1 for t in times if t < 5000), len(times)),
            "open_appeals": sum(1 for a in appeals if a.status == "OPEN"),
            "appeal_overturn_rate": _pct(len(overturned), len(appeals)),
            "reviewer_override_rate": _pct(len(disagreements), len(overrides)),
            "active_reviewers": sum(1 for r in reviewers if r.is_available),
            "total_reviewers": len(reviewers),
        },
        "urgency_bands": _urgency_bands(pending),
        "reviewer_load": [
            {
                "name": r.full_name, "specialty": r.specialty,
                "open_cases": load.get(r.id, 0),
                "daily_capacity": r.daily_capacity,
                "utilization": _pct(load.get(r.id, 0), r.daily_capacity),
                "is_available": r.is_available,
            }
            for r in reviewers
        ],
        "top_denial_reasons": _denial_reasons(rows),
        "by_payer": [
            {"name": k, "count": v}
            for k, v in Counter((r.features or {}).get("payer") for r in rows).most_common(8)
            if k
        ],
        "trend": _trend(rows),
    }


def _urgency_bands(pending):
    bands = {"Critical (0.75+)": 0, "High (0.55-0.75)": 0,
             "Standard (0.35-0.55)": 0, "Routine (<0.35)": 0}
    for r in pending:
        u = r.urgency_score or 0
        if u >= 0.75:
            bands["Critical (0.75+)"] += 1
        elif u >= 0.55:
            bands["High (0.55-0.75)"] += 1
        elif u >= 0.35:
            bands["Standard (0.35-0.55)"] += 1
        else:
            bands["Routine (<0.35)"] += 1
    return [{"band": k, "count": v} for k, v in bands.items()]


@router.get("/model-card")
def model_card(user: User = Depends(current_user)):
    return {"ready": ml.models_ready(), "metrics": ml.metrics_card()}