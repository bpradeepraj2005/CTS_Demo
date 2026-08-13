"""
Medical-necessity rules engine.

This is deliberately a deterministic rules engine rather than a classifier.
The training corpus contains denied cases only, so an approve/deny boundary
cannot be learned from it -- and a payer decision that affects care needs to be
reconstructable line by line for an audit anyway.

Every criterion returns a verdict, the observed value, the threshold it was
tested against, and the weight it carries. That ledger is what the reviewer
sees and what gets written to the audit trail.
"""
from ..config import (
    AUTO_APPROVE_MIN_POLICY_FIT,
    AUTO_DENY_MAX_POLICY_FIT,
    MIN_DOCUMENTATION_SCORE,
)

SEVERITY_RANK = {"Mild": 0, "Moderate": 1, "Severe": 2}

# Therapies a payer normally gates behind a documented conventional-therapy
# trial. Weighted, not absolute: a severe presentation can carry a case that
# is one step-therapy trial short.
STEP_THERAPY_REQUIRED_MIN_TRIALS = 1


def evaluate(features: dict, policy_fit: float) -> dict:
    criteria: list[dict] = []

    def add(code, label, passed, observed, expected, weight, blocking=False):
        criteria.append({
            "code": code, "label": label, "passed": bool(passed),
            "observed": observed, "expected": expected,
            "weight": weight, "blocking": blocking,
        })

    eligible = int(features.get("member_eligible", 1)) == 1
    add("ELIG", "Member eligible on date of service", eligible,
        "Eligible" if eligible else "Not eligible", "Eligible", 0.0, blocking=True)

    covered = int(features.get("treatment_covered", 1)) == 1
    add("COV", "Requested therapy is a covered benefit", covered,
        "Covered" if covered else "Not covered", "Covered", 0.0, blocking=True)

    doc_score = float(features.get("documentation_score", 0))
    add("DOC", "Supporting documentation complete", doc_score >= MIN_DOCUMENTATION_SCORE,
        f"{doc_score:.0%} of required attachments",
        f"at least {MIN_DOCUMENTATION_SCORE:.0%}", 0.20)

    severity = features.get("disease_severity", "Mild")
    burden = float(features.get("symptom_burden_0_10", 0))
    sev_ok = SEVERITY_RANK.get(severity, 0) >= 1 or burden >= 6.0
    add("SEV", "Documented severity supports escalation", sev_ok,
        f"{severity}, symptom burden {burden:.1f}/10",
        "Moderate or above, or burden 6.0+", 0.20)

    tried = int(features.get("previous_treatment_count", 0))
    failed = int(features.get("previous_failed_count", 0))
    partial = int(features.get("previous_partial_response_count", 0))
    adverse = int(features.get("previous_adverse_effect_count", 0))
    step_ok = (failed + partial + adverse) >= STEP_THERAPY_REQUIRED_MIN_TRIALS
    add("STEP", "Step therapy satisfied", step_ok,
        f"{tried} prior therapies, {failed} failed, {partial} partial, "
        f"{adverse} with adverse effects",
        f"at least {STEP_THERAPY_REQUIRED_MIN_TRIALS} failed, partial or "
        f"not-tolerated trial", 0.20)

    weeks = int(features.get("longest_previous_treatment_weeks", 0))
    trial_ok = weeks >= 8 or tried == 0
    add("TRIAL", "Prior therapy given an adequate trial", trial_ok,
        f"longest trial {weeks} weeks", "8 weeks or more", 0.10)

    duration = int(features.get("requested_duration_months", 3))
    dur_ok = duration <= 12
    add("DUR", "Requested duration within policy limit", dur_ok,
        f"{duration} months", "12 months or less", 0.05)

    fit_ok = policy_fit >= AUTO_APPROVE_MIN_POLICY_FIT
    add("FIT", "Policy alignment score", fit_ok,
        f"{policy_fit:.3f}", f"{AUTO_APPROVE_MIN_POLICY_FIT:.2f} or above", 0.25)

    blockers = [c for c in criteria if c["blocking"] and not c["passed"]]
    scored = [c for c in criteria if not c["blocking"]]
    total_weight = sum(c["weight"] for c in scored) or 1.0
    necessity = sum(c["weight"] for c in scored if c["passed"]) / total_weight

    if blockers:
        decision, status = "DENIED", "AUTO_DENIED"
        rationale = (
            "Denied on coverage grounds: "
            + "; ".join(c["label"].lower() for c in blockers) + "."
        )
        confidence = 0.99
    elif necessity >= 0.80 and policy_fit >= AUTO_APPROVE_MIN_POLICY_FIT:
        decision, status = "APPROVED", "AUTO_APPROVED"
        rationale = (
            f"All medical-necessity criteria met ({necessity:.0%} of weighted "
            f"criteria) with policy alignment at {policy_fit:.2f}."
        )
        confidence = round(min(0.99, 0.70 + necessity * 0.30), 3)
    elif necessity <= 0.40 and policy_fit <= AUTO_DENY_MAX_POLICY_FIT:
        decision, status = "DENIED", "AUTO_DENIED"
        failed_labels = [c["label"].lower() for c in scored if not c["passed"]]
        rationale = (
            "Medical-necessity criteria not satisfied: "
            + "; ".join(failed_labels[:3]) + "."
        )
        confidence = round(min(0.99, 0.70 + (1 - necessity) * 0.30), 3)
    else:
        decision, status = None, "PENDING_REVIEW"
        unmet = [c["label"].lower() for c in scored if not c["passed"]]
        rationale = (
            "Routed to a clinical reviewer: "
            + (", ".join(unmet[:3]) if unmet else "policy alignment is borderline")
            + "."
        )
        confidence = round(1 - abs(necessity - 0.5) * 2 * 0.4, 3)

    return {
        "decision": decision,
        "status": status,
        "necessity_score": round(necessity, 4),
        "confidence": confidence,
        "rationale": rationale,
        "criteria": criteria,
    }


def urgency_score(features: dict, necessity: float) -> float:
    """Queue priority for cases that need a human. Higher goes first."""
    severity = SEVERITY_RANK.get(features.get("disease_severity", "Mild"), 0) / 2
    burden = float(features.get("symptom_burden_0_10", 0)) / 10
    duration = min(float(features.get("symptom_duration_months", 0)) / 60, 1.0)
    failures = min(int(features.get("previous_failed_count", 0)) / 3, 1.0)
    borderline = 1 - abs(necessity - 0.5) * 2  # most contested cases first
    score = (
        0.30 * severity + 0.25 * burden + 0.10 * duration
        + 0.15 * failures + 0.20 * borderline
    )
    return round(min(1.0, score), 4)