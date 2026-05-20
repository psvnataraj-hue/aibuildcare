"""Manual escalation + hierarchy management (E1c).

POST /api/v1/complaints/{cid}/escalate   -- bump complaint one level
GET/POST/PUT/DELETE /api/v1/escalation/hierarchy[/{id}] -- people CRUD
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..deps import current_society, require
from ..services import complaint_service as svc
from ..services import escalation_service, rbac
from ..services.ws_hub import hub

router = APIRouter(prefix="/api/v1", tags=["escalation"])


# ---- escalate action ------------------------------------------------
@router.post("/complaints/{cid}/escalate",
             dependencies=[Depends(require(rbac.ESCALATE))])
async def escalate(
    cid: int, sid: int = Depends(current_society)
) -> dict:
    try:
        result = escalation_service.escalate(cid, sid)
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(code, str(e))
    await hub.broadcast("complaint.updated", result)
    return result


# ---- hierarchy CRUD --------------------------------------------------
class HierarchyEntry(BaseModel):
    role_name: str
    person_name: str
    phone: str | None = None
    whatsapp_enabled: bool = True
    email: str | None = None
    escalation_level: int = 1
    response_time_target_minutes: int = 60


class HierarchyPatch(BaseModel):
    role_name: str | None = None
    person_name: str | None = None
    phone: str | None = None
    whatsapp_enabled: bool | None = None
    email: str | None = None
    escalation_level: int | None = None
    response_time_target_minutes: int | None = None
    active: bool | None = None


@router.get("/escalation/hierarchy",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def list_hierarchy(sid: int = Depends(current_society)) -> list[dict]:
    return escalation_service.list_hierarchy(sid)


@router.post("/escalation/hierarchy", status_code=201,
             dependencies=[Depends(require(rbac.MODIFY_CONFIG))])
def add_hierarchy(
    body: HierarchyEntry, sid: int = Depends(current_society)
) -> dict:
    try:
        return escalation_service.add_hierarchy(sid, **body.model_dump())
    except svc.ComplaintError as e:
        raise HTTPException(400, str(e))


@router.put("/escalation/hierarchy/{eid}",
            dependencies=[Depends(require(rbac.MODIFY_CONFIG))])
def update_hierarchy(
    eid: int, body: HierarchyPatch,
    sid: int = Depends(current_society),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return escalation_service.update_hierarchy(eid, sid, **fields)
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(code, str(e))


@router.delete("/escalation/hierarchy/{eid}",
               dependencies=[Depends(require(rbac.MODIFY_CONFIG))])
def delete_hierarchy(
    eid: int, sid: int = Depends(current_society)
) -> dict:
    n = escalation_service.delete_hierarchy(eid, sid)
    if n == 0:
        raise HTTPException(404, "hierarchy entry not found")
    return {"deleted": n}
