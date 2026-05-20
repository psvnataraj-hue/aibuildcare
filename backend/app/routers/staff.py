"""E3a: staff CRUD endpoints (the frontend's prerequisite).

GET   /api/v1/staff               -- list (VIEW_ALL)
GET   /api/v1/staff/{id}          -- detail (VIEW_ALL)
POST  /api/v1/staff               -- create + initial categories (MODIFY_STAFF)
PUT   /api/v1/staff/{id}          -- partial update (MODIFY_STAFF)
DELETE /api/v1/staff/{id}         -- soft-delete (active=0) (MODIFY_STAFF)
POST   /api/v1/staff/{id}/categories          -- upsert one (MODIFY_STAFF)
DELETE /api/v1/staff/{id}/categories/{cat}    -- remove one (MODIFY_STAFF)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import current_society, require
from ..services import (
    complaint_service as svc,
    rbac,
    staff_service,
)

router = APIRouter(prefix="/api/v1/staff", tags=["staff"])


class StaffCategory(BaseModel):
    category: str
    primary_category: bool = False
    skill_level: str = "junior"


class StaffCreate(BaseModel):
    name: str = Field(min_length=1)
    phone_primary: str = Field(min_length=1)
    phone_secondary: str | None = None
    whatsapp_enabled: bool = True
    sms_fallback: bool = True
    email: str | None = None
    shift_pattern: str | None = None
    hire_date: str | None = None
    emergency_contact: str | None = None
    notes: str | None = None
    categories: list[StaffCategory] = []


class StaffPatch(BaseModel):
    name: str | None = None
    phone_primary: str | None = None
    phone_secondary: str | None = None
    whatsapp_enabled: bool | None = None
    sms_fallback: bool | None = None
    email: str | None = None
    shift_pattern: str | None = None
    hire_date: str | None = None
    emergency_contact: str | None = None
    notes: str | None = None
    active: bool | None = None


class CategoryAssign(BaseModel):
    category: str
    primary_category: bool = False
    skill_level: str = "junior"


@router.get("", dependencies=[Depends(require(rbac.VIEW_ALL))])
def list_staff(
    include_inactive: bool = False,
    sid: int = Depends(current_society),
) -> list[dict]:
    return staff_service.list_staff(sid, include_inactive=include_inactive)


@router.get("/{staff_id}", dependencies=[Depends(require(rbac.VIEW_ALL))])
def get_staff(
    staff_id: int, sid: int = Depends(current_society)
) -> dict:
    try:
        return staff_service.get_staff(staff_id, sid)
    except svc.ComplaintError as e:
        raise HTTPException(404, str(e))


@router.post("", status_code=201,
             dependencies=[Depends(require(rbac.MODIFY_STAFF))])
def create_staff(
    body: StaffCreate, sid: int = Depends(current_society)
) -> dict:
    try:
        return staff_service.create_staff(
            sid,
            categories=[c.model_dump() for c in body.categories],
            **body.model_dump(exclude={"categories"}),
        )
    except svc.ComplaintError as e:
        raise HTTPException(400, str(e))


@router.put("/{staff_id}",
            dependencies=[Depends(require(rbac.MODIFY_STAFF))])
def update_staff(
    staff_id: int, body: StaffPatch,
    sid: int = Depends(current_society),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return staff_service.update_staff(staff_id, sid, **fields)
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(code, str(e))


@router.delete("/{staff_id}",
               dependencies=[Depends(require(rbac.MODIFY_STAFF))])
def deactivate_staff(
    staff_id: int, sid: int = Depends(current_society)
) -> dict:
    try:
        return staff_service.deactivate_staff(staff_id, sid)
    except svc.ComplaintError as e:
        raise HTTPException(404, str(e))


@router.post("/{staff_id}/categories",
             dependencies=[Depends(require(rbac.MODIFY_STAFF))])
def add_category(
    staff_id: int, body: CategoryAssign,
    sid: int = Depends(current_society),
) -> dict:
    try:
        return staff_service.add_category(
            staff_id, sid, **body.model_dump()
        )
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(code, str(e))


@router.delete("/{staff_id}/categories/{category}",
               dependencies=[Depends(require(rbac.MODIFY_STAFF))])
def remove_category(
    staff_id: int, category: str,
    sid: int = Depends(current_society),
) -> dict:
    try:
        return staff_service.remove_category(staff_id, sid, category)
    except svc.ComplaintError as e:
        raise HTTPException(404, str(e))
