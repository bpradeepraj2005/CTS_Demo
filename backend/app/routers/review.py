from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Appeal, AuthRequest, User
from ..schemas import AppealResolve, ReviewDecision
from ..security import require_payer
from ..services import routing
from ..services.pipeline import log
from .requests import _detail, _summary

router = APIRouter(prefix="/api/review", tags=["review"])


@router.get("/queue")
def queue(
    scope: str = "mine",
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    """Pending cases ordered by urgency. scope: mine | unassigned | all"""
    q = db.query(AuthRequest).filter(AuthRequest.status == "PENDING_REVIEW")
    if scope == "mine":
        q = q.filter(AuthRequest.assigned_reviewer_id == user.id)
    elif scope == "unassigned":
        q = q.filter(AuthRequest.assigned_reviewer_id.is_(None))
    rows = q.order_by(desc(AuthRequest.urgency_score),
                      desc(AuthRequest.created_at)).limit(300).all()

    reviewers = {u.id: u for u in db.query(User).filter(
        User.role == "PAYER_REVIEWER").all()}
    out = []
    for r in rows:
        item = _summary(r)
        rv = reviewers.get(r.assigned_reviewer_id)
        item["assigned_reviewer"] = (
            {"id": rv.id, "name": rv.full_name, "specialty": rv.specialty}
            if rv else None
        )
        out.append(item)
    return out


@router.get("/cases/{request_id}")
def case_detail(
    request_id: str,
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    detail = _detail(db, req)
    detail["routing_candidates"] = routing.rank_reviewers(db, req.features)
    return detail


@router.post("/cases/{request_id}/decide")
def decide(
    request_id: str,
    body: ReviewDecision,
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    if req.status != "PENDING_REVIEW":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This case is already {req.status.replace('_', ' ').lower()}",
        )

    engine_leaning = (
        "APPROVED" if (req.necessity_score or 0) >= 0.5 else "DENIED"
    )
    req.decision = body.decision
    req.status = body.decision
    req.decision_source = "REVIEWER"
    req.decision_at = datetime.now(timezone.utc)
    req.reviewer_notes = body.notes
    if req.assigned_reviewer_id is None:
        req.assigned_reviewer_id = user.id
        req.assignment_reason = f"Claimed by {user.full_name} from the shared queue."

    log(db, "REVIEWER_DECISION", request_id=req.id, actor=user, detail={
        "decision": body.decision,
        "notes": body.notes,
        "engine_leaning": engine_leaning,
        "agreed_with_engine": body.decision == engine_leaning,
        "necessity_score": req.necessity_score,
        "policy_fit_score": req.policy_fit_score,
    })
    db.commit()
    db.refresh(req)
    return _detail(db, req)


@router.post("/cases/{request_id}/reassign")
def reassign(
    request_id: str,
    reviewer_id: str,
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    req = db.get(AuthRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such case")
    target = db.get(User, reviewer_id)
    if target is None or target.role != "PAYER_REVIEWER":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such reviewer")

    previous = req.assigned_reviewer_id
    req.assigned_reviewer_id = target.id
    req.assignment_was_reassigned = True
    req.assignment_reason = f"Manually reassigned to {target.full_name} by {user.full_name}."
    log(db, "REVIEWER_REASSIGNED", request_id=req.id, actor=user,
        detail={"from": previous, "to": target.id, "manual": True})
    db.commit()
    db.refresh(req)
    return _detail(db, req)


@router.get("/reviewers")
def reviewers(user: User = Depends(require_payer), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.role == "PAYER_REVIEWER").all()
    open_counts = {}
    for r in db.query(AuthRequest).filter(
        AuthRequest.status == "PENDING_REVIEW",
        AuthRequest.assigned_reviewer_id.isnot(None),
    ).all():
        open_counts[r.assigned_reviewer_id] = open_counts.get(r.assigned_reviewer_id, 0) + 1

    return [
        {
            "id": r.id, "name": r.full_name, "email": r.email,
            "specialty": r.specialty, "daily_capacity": r.daily_capacity,
            "is_available": r.is_available,
            "unavailable_reason": r.unavailable_reason,
            "open_cases": open_counts.get(r.id, 0),
            "is_self": r.id == user.id,
        }
        for r in rows
    ]


@router.get("/appeals")
def list_appeals(user: User = Depends(require_payer), db: Session = Depends(get_db)):
    rows = (
        db.query(Appeal, AuthRequest)
        .join(AuthRequest, Appeal.request_id == AuthRequest.id)
        .order_by(desc(Appeal.created_at))
        .limit(200)
        .all()
    )
    return [
        {
            "id": a.id, "status": a.status, "rationale": a.rationale,
            "new_documentation": a.new_documentation,
            "created_at": a.created_at, "outcome_notes": a.outcome_notes,
            "case_number": r.case_number, "request_id": r.id,
            "diagnosis": (r.features or {}).get("diagnosis"),
            "requested_treatment": (r.features or {}).get("requested_treatment"),
            "predicted_at_filing": a.predicted_at_filing,
        }
        for a, r in rows
    ]


@router.post("/appeals/{appeal_id}/resolve")
def resolve_appeal(
    appeal_id: str,
    body: AppealResolve,
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    appeal = db.get(Appeal, appeal_id)
    if appeal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such appeal")
    if appeal.status != "OPEN":
        raise HTTPException(status.HTTP_409_CONFLICT, "This appeal is already resolved")

    appeal.status = body.status
    appeal.outcome_notes = body.outcome_notes
    appeal.resolved_at = datetime.now(timezone.utc)

    req = db.get(AuthRequest, appeal.request_id)
    if body.status == "OVERTURNED":
        req.decision = "APPROVED"
        req.status = "APPROVED"
        req.decision_source = "REVIEWER"
        req.decision_at = datetime.now(timezone.utc)
    else:
        req.status = "DENIED"

    log(db, "APPEAL_RESOLVED", request_id=req.id, actor=user,
        detail={"outcome": body.status, "notes": body.outcome_notes})
    db.commit()
    return {"appeal_id": appeal.id, "status": appeal.status,
            "request_status": req.status}