import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text,
)
from sqlalchemy.orm import relationship

from .database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    # "PROVIDER" (hospital) or "PAYER" (insurance)
    org_type = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    users = relationship("User", back_populates="organization")


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    # PROVIDER_STAFF | PAYER_REVIEWER
    role = Column(String, nullable=False, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), nullable=False)

    # Reviewer-only profile fields, used by the routing engine.
    specialty = Column(String, nullable=True)
    license_number = Column(String, nullable=True)
    daily_capacity = Column(Integer, default=12)
    is_available = Column(Boolean, default=True, nullable=False)
    unavailable_reason = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="users")


class Patient(Base):
    __tablename__ = "patients"
    id = Column(String, primary_key=True, default=_uuid)
    organization_id = Column(String, ForeignKey("organizations.id"), index=True)
    mrn = Column(String, index=True)
    full_name = Column(String)
    age = Column(Integer)
    sex = Column(String)
    created_at = Column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=_uuid)
    request_id = Column(String, ForeignKey("auth_requests.id"), index=True)
    uploaded_by = Column(String, ForeignKey("users.id"))
    filename = Column(String, nullable=False)
    stored_path = Column(String, nullable=False)
    page_count = Column(Integer)
    char_count = Column(Integer)
    extraction_confidence = Column(Float)
    extracted_fields = Column(JSON)
    unmatched_fields = Column(JSON)
    raw_text = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now)


class AuthRequest(Base):
    __tablename__ = "auth_requests"
    id = Column(String, primary_key=True, default=_uuid)
    case_number = Column(String, unique=True, index=True)
    organization_id = Column(String, ForeignKey("organizations.id"), index=True)
    created_by = Column(String, ForeignKey("users.id"))
    patient_id = Column(String, ForeignKey("patients.id"), nullable=True)

    features = Column(JSON, nullable=False)

    # SUBMITTED | AUTO_APPROVED | AUTO_DENIED | PENDING_REVIEW |
    # APPROVED | DENIED | APPEALED
    status = Column(String, nullable=False, index=True, default="SUBMITTED")
    decision = Column(String, nullable=True)
    decision_source = Column(String, nullable=True)  # ENGINE | REVIEWER
    decision_at = Column(DateTime(timezone=True), nullable=True)

    policy_fit_score = Column(Float)
    documentation_score = Column(Float)
    necessity_score = Column(Float)
    urgency_score = Column(Float)
    confidence = Column(Float)
    processing_ms = Column(Float)

    criteria = Column(JSON)          # rules-engine ledger
    explanation = Column(JSON)       # feature attributions
    appeal_prediction = Column(JSON) # appeal-propensity model output

    assigned_reviewer_id = Column(String, ForeignKey("users.id"), nullable=True)
    assignment_reason = Column(String, nullable=True)
    assignment_was_reassigned = Column(Boolean, default=False)

    reviewer_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)

    documents = relationship("Document", cascade="all,delete")


class Appeal(Base):
    __tablename__ = "appeals"
    id = Column(String, primary_key=True, default=_uuid)
    request_id = Column(String, ForeignKey("auth_requests.id"), index=True)
    filed_by = Column(String, ForeignKey("users.id"))
    rationale = Column(Text)
    new_documentation = Column(Boolean, default=False)
    status = Column(String, default="OPEN")  # OPEN | UPHELD | OVERTURNED
    outcome_notes = Column(Text, nullable=True)
    predicted_at_filing = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(String, primary_key=True, default=_uuid)
    request_id = Column(String, index=True, nullable=True)
    actor_id = Column(String, nullable=True)
    actor_email = Column(String, nullable=True)
    action = Column(String, nullable=False, index=True)
    detail = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=_now, index=True)