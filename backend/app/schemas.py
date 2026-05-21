from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ComplaintCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    channel: str = "dashboard"
    reporter_phone: str | None = None
    reporter_email: str | None = None
    # P2 — parking-specific fields. Honoured only when the LLM (or
    # rule fallback) classifies the complaint as 'Parking Management';
    # ignored otherwise. vehicle_plate gets normalised + auto-linked
    # to vehicles.id by create_complaint.
    vehicle_plate: str | None = None
    violation_type: str | None = None


class ComplaintOut(BaseModel):
    id: int
    ticket_number: str
    unit_number: str | None
    category: str | None
    priority: str
    status: str
    channel: str
    raw_text: str
    acknowledgement: str | None
    contractor_id: int | None
    created_at: str
    updated_at: str


class AssignRequest(BaseModel):
    # Exactly one of contractor_id / staff_id must be set.
    contractor_id: int | None = None
    staff_id: int | None = None


class StatusUpdateRequest(BaseModel):
    status: str


class MessageCreate(BaseModel):
    sender: str = "staff"
    body: str = Field(min_length=1)


class RateRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    feedback: str | None = None


class ConfigUpdate(BaseModel):
    value: str


class ParsedComplaint(BaseModel):
    unit_number: str | None = None
    category: str = "Other"
    priority: str = "normal"
    acknowledgement: str = ""
    detected_language: str | None = None
    # staff-facing summary per configured language code, e.g.
    # {"hi": "...", "en": "..."}. Empty on the rule-based fallback.
    official_summaries: dict[str, str] = {}
