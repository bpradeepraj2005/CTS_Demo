from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class SignupProvider(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    organization_name: str = Field(min_length=2)


class SignupPayer(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    organization_name: str = Field(min_length=2)
    specialty: str
    license_number: str | None = None
    daily_capacity: int = Field(default=12, ge=1, le=100)


class Login(BaseModel):
    email: EmailStr
    password: str
    portal: Literal["provider", "payer"]


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    specialty: str | None = None
    daily_capacity: int | None = None
    is_available: bool = True
    unavailable_reason: str | None = None
    organization_name: str | None = None

    class Config:
        from_attributes = True


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AvailabilityUpdate(BaseModel):
    is_available: bool
    unavailable_reason: str | None = None


class RequestCreate(BaseModel):
    features: dict[str, Any]
    document_id: str | None = None
    patient_name: str | None = None
    mrn: str | None = None


class ReviewDecision(BaseModel):
    decision: Literal["APPROVED", "DENIED"]
    notes: str = Field(min_length=5)


class AppealCreate(BaseModel):
    rationale: str = Field(min_length=10)
    new_documentation: bool = False


class AppealResolve(BaseModel):
    status: Literal["UPHELD", "OVERTURNED"]
    outcome_notes: str = Field(min_length=5)


class RequestSummary(BaseModel):
    id: str
    case_number: str
    status: str
    decision: str | None
    created_at: datetime
    policy_fit_score: float | None
    necessity_score: float | None
    urgency_score: float | None
    confidence: float | None
    processing_ms: float | None
    assigned_reviewer_id: str | None
    assignment_reason: str | None
    assignment_was_reassigned: bool | None
    features: dict[str, Any]
    appeal_prediction: dict[str, Any] | None

    class Config:
        from_attributes = True