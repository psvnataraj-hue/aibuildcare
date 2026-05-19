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
    contractor_id: int


class StatusUpdateRequest(BaseModel):
    status: str


class MessageCreate(BaseModel):
    sender: str = "staff"
    body: str = Field(min_length=1)


class ParsedComplaint(BaseModel):
    unit_number: str | None = None
    category: str = "Other"
    priority: str = "normal"
    acknowledgement: str = ""
    detected_language: str | None = None
