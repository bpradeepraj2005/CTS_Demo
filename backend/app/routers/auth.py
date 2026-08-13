from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Organization, User
from ..schemas import (
    AvailabilityUpdate, Login, SignupPayer, SignupProvider, TokenOut, UserOut,
)
from ..security import (
    create_access_token, current_user, hash_password, require_payer,
    verify_password,
)
from ..services.pipeline import log
from ..services.vocab import SPECIALTIES

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _out(user: User) -> UserOut:
    data = UserOut.model_validate(user)
    data.organization_name = user.organization.name if user.organization else None
    return data


def _get_or_create_org(db: Session, name: str, org_type: str) -> Organization:
    org = (
        db.query(Organization)
        .filter(Organization.name == name.strip(), Organization.org_type == org_type)
        .first()
    )
    if org is None:
        org = Organization(name=name.strip(), org_type=org_type)
        db.add(org)
        db.flush()
    return org


def _reject_duplicate(db: Session, email: str):
    if db.query(User).filter(User.email == email.lower()).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An account already uses this email address",
        )


@router.get("/specialties")
def specialties():
    return {"specialties": SPECIALTIES}


@router.post("/signup/provider", response_model=TokenOut, status_code=201)
def signup_provider(body: SignupProvider, db: Session = Depends(get_db)):
    _reject_duplicate(db, body.email)
    org = _get_or_create_org(db, body.organization_name, "PROVIDER")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="PROVIDER_STAFF",
        organization_id=org.id,
    )
    db.add(user)
    db.flush()
    log(db, "USER_REGISTERED", actor=user, detail={"portal": "provider",
                                                   "organization": org.name})
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=_out(user))


@router.post("/signup/payer", response_model=TokenOut, status_code=201)
def signup_payer(body: SignupPayer, db: Session = Depends(get_db)):
    _reject_duplicate(db, body.email)
    if body.specialty not in SPECIALTIES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Choose a specialty from: {', '.join(SPECIALTIES)}",
        )
    org = _get_or_create_org(db, body.organization_name, "PAYER")
    user = User(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="PAYER_REVIEWER",
        organization_id=org.id,
        specialty=body.specialty,
        license_number=body.license_number,
        daily_capacity=body.daily_capacity,
        is_available=True,
    )
    db.add(user)
    db.flush()
    log(db, "USER_REGISTERED", actor=user, detail={"portal": "payer",
                                                   "specialty": body.specialty,
                                                   "organization": org.name})
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=_out(user))


@router.post("/login", response_model=TokenOut)
def login(body: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect"
        )

    expected = "PROVIDER_STAFF" if body.portal == "provider" else "PAYER_REVIEWER"
    if user.role != expected:
        other = "payer" if body.portal == "provider" else "hospital"
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"This account belongs to the {other} portal. Switch portals to sign in.",
        )

    user.last_login_at = datetime.now(timezone.utc)
    log(db, "USER_LOGIN", actor=user, detail={"portal": body.portal})
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return _out(user)


@router.patch("/availability", response_model=UserOut)
def set_availability(
    body: AvailabilityUpdate,
    user: User = Depends(require_payer),
    db: Session = Depends(get_db),
):
    user.is_available = body.is_available
    user.unavailable_reason = None if body.is_available else (
        body.unavailable_reason or "Marked unavailable"
    )
    log(db, "REVIEWER_AVAILABILITY_CHANGED", actor=user,
        detail={"is_available": body.is_available,
                "reason": user.unavailable_reason})
    db.commit()
    db.refresh(user)
    return _out(user)