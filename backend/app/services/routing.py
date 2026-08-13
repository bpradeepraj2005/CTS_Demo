"""
Assigns a pending case to a clinical reviewer.

Reviewers are real registered payer users -- there is no synthetic roster. If
nobody has signed up on the payer side yet, the case stays in the unassigned
queue and the API says so.

Scoring, highest wins:
  specialty match   0.45   the reviewer's specialty matches the ordering one
  spare capacity    0.30   open slots today against declared daily capacity
  queue depth       0.15   fewer cases already waiting on them
  recency           0.10   spread work across the team rather than one person

An unavailable reviewer is skipped entirely, and the next-best reviewer is
recorded as an alternate assignment with the reason attached.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AuthRequest, User

# Which specialty normally owns which condition. Anything unmapped falls back
# to any available reviewer.
DIAGNOSIS_SPECIALTY = {
    "Crohn's disease": "Gastroenterology",
    "Ulcerative colitis": "Gastroenterology",
    "Plaque psoriasis": "Dermatology",
    "Atopic dermatitis": "Dermatology",
    "Psoriatic arthritis": "Rheumatology",
    "Rheumatoid arthritis": "Rheumatology",
    "Osteoporosis": "Endocrinology",
    "Type 2 diabetes mellitus": "Endocrinology",
    "Multiple sclerosis": "Neurology",
    "Chronic migraine": "Neurology",
    "Moderate persistent asthma": "Pulmonology",
    "Chronic obstructive pulmonary disease": "Pulmonology",
    "Heart failure": "Cardiology",
    "Endometriosis": "Gynecology",
    "Narcolepsy": "Sleep Medicine",
}


def required_specialty(features: dict) -> str | None:
    return (
        DIAGNOSIS_SPECIALTY.get(features.get("diagnosis"))
        or features.get("provider_specialty")
    )


def _workload(db: Session, org_id: str) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    rows = (
        db.query(AuthRequest.assigned_reviewer_id, func.count(AuthRequest.id))
        .filter(
            AuthRequest.assigned_reviewer_id.isnot(None),
            AuthRequest.status == "PENDING_REVIEW",
        )
        .group_by(AuthRequest.assigned_reviewer_id)
        .all()
    )
    return {r[0]: r[1] for r in rows}


def _last_assigned(db: Session) -> dict[str, datetime]:
    rows = (
        db.query(AuthRequest.assigned_reviewer_id, func.max(AuthRequest.created_at))
        .filter(AuthRequest.assigned_reviewer_id.isnot(None))
        .group_by(AuthRequest.assigned_reviewer_id)
        .all()
    )
    return {r[0]: r[1] for r in rows if r[1]}


def rank_reviewers(db: Session, features: dict) -> list[dict]:
    reviewers = db.query(User).filter(User.role == "PAYER_REVIEWER").all()
    if not reviewers:
        return []

    want = required_specialty(features)
    load = _workload(db, None)
    last = _last_assigned(db)
    now = datetime.now(timezone.utc)
    max_load = max([load.get(r.id, 0) for r in reviewers] + [1])

    ranked = []
    for r in reviewers:
        capacity = max(r.daily_capacity or 12, 1)
        open_now = load.get(r.id, 0)
        spare = max(0.0, (capacity - open_now) / capacity)
        queue = 1 - (open_now / max_load if max_load else 0)

        last_at = last.get(r.id)
        if last_at is None:
            recency = 1.0
        else:
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            hours = (now - last_at).total_seconds() / 3600
            recency = min(1.0, hours / 24)

        match = 1.0 if (want and r.specialty == want) else 0.0
        score = 0.45 * match + 0.30 * spare + 0.15 * queue + 0.10 * recency

        ranked.append({
            "reviewer_id": r.id,
            "name": r.full_name,
            "specialty": r.specialty,
            "specialty_match": bool(match),
            "open_cases": open_now,
            "daily_capacity": capacity,
            "at_capacity": open_now >= capacity,
            "is_available": bool(r.is_available),
            "unavailable_reason": r.unavailable_reason,
            "score": round(score, 4),
            "factors": {
                "specialty_match": round(0.45 * match, 4),
                "spare_capacity": round(0.30 * spare, 4),
                "queue_depth": round(0.15 * queue, 4),
                "recency": round(0.10 * recency, 4),
            },
        })

    ranked.sort(key=lambda x: -x["score"])
    return ranked


def assign(db: Session, features: dict) -> dict:
    ranked = rank_reviewers(db, features)
    if not ranked:
        return {
            "reviewer_id": None,
            "reason": "No payer reviewers have registered yet. Case held in the "
                      "unassigned queue.",
            "reassigned": False,
            "candidates": [],
        }

    eligible = [r for r in ranked if r["is_available"] and not r["at_capacity"]]
    first_choice = ranked[0]

    if not eligible:
        return {
            "reviewer_id": None,
            "reason": "Every reviewer is unavailable or at capacity. Case held in "
                      "the unassigned queue.",
            "reassigned": False,
            "candidates": ranked[:5],
        }

    chosen = eligible[0]
    reassigned = chosen["reviewer_id"] != first_choice["reviewer_id"]

    if reassigned:
        blocked = (
            first_choice["unavailable_reason"]
            or ("at daily capacity" if first_choice["at_capacity"] else "unavailable")
        )
        reason = (
            f"{first_choice['name']} is {blocked}. Reassigned to {chosen['name']}"
            + (f" ({chosen['specialty']})" if chosen["specialty"] else "")
            + "."
        )
    else:
        want = required_specialty(features)
        if chosen["specialty_match"]:
            reason = (
                f"Matched to {chosen['name']} on {want}, "
                f"{chosen['open_cases']} of {chosen['daily_capacity']} slots in use."
            )
        else:
            reason = (
                f"No {want} reviewer available. Routed to {chosen['name']}"
                + (f" ({chosen['specialty']})" if chosen["specialty"] else "")
                + " by available capacity."
            )

    return {
        "reviewer_id": chosen["reviewer_id"],
        "reason": reason,
        "reassigned": reassigned,
        "candidates": ranked[:5],
    }