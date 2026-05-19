from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..deps import current_user
from ..schemas import (
    ComplaintCreate,
    AssignRequest,
    StatusUpdateRequest,
    MessageCreate,
    RateRequest,
)
from ..services import complaint_service as svc
from ..services.ws_hub import hub
from ..services.notify import send_whatsapp

router = APIRouter(prefix="/api/v1", tags=["complaints"])


@router.get("/analytics")
def analytics(_: dict = Depends(current_user)) -> dict:
    return svc.analytics()


@router.get("/contractors")
def contractors(_: dict = Depends(current_user)) -> list[dict]:
    from ..db import get_conn

    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contractors WHERE is_active = 1 ORDER BY name"
            ).fetchall()
        ]


@router.get("/complaints")
def list_complaints(
    status: str | None = None,
    q: str | None = None,
    sort: str = "created_at",
    _: dict = Depends(current_user),
) -> list[dict]:
    return svc.list_complaints(status=status, q=q, sort=sort)


@router.post("/complaints", status_code=201)
async def create_complaint(
    body: ComplaintCreate, _: dict = Depends(current_user)
) -> dict:
    c = svc.create_complaint(
        body.raw_text, body.channel, body.reporter_phone, body.reporter_email
    )
    await hub.broadcast("complaint.created", c)
    return c


@router.get("/contractors/by-category")
def contractors_by_category(
    category: str | None = None, _: dict = Depends(current_user)
) -> list[dict]:
    from ..services.contractor_router import contractors_by_category as cbc

    return cbc(category)


@router.get("/contractors/performance")
def contractors_performance(_: dict = Depends(current_user)) -> list[dict]:
    return svc.contractor_performance()


@router.get("/contractors/{cid}/performance")
def contractor_performance(
    cid: int, _: dict = Depends(current_user)
) -> dict:
    rows = svc.contractor_performance(cid)
    if not rows:
        raise HTTPException(status_code=404, detail="contractor not found")
    return rows[0]


@router.get("/complaints/{cid}")
def get_complaint(cid: int, _: dict = Depends(current_user)) -> dict:
    try:
        c = svc.get_complaint(cid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    c["messages"] = svc.list_messages(cid)
    c["rating"] = svc.get_rating(cid)
    return c


@router.post("/complaints/{cid}/assign")
async def assign(
    cid: int, body: AssignRequest, _: dict = Depends(current_user)
) -> dict:
    # capture prior contractor for reassignment notice
    try:
        prev = svc.get_complaint(cid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    prev_cid = prev.get("contractor_id")
    try:
        c = svc.assign_contractor(cid, body.contractor_id)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # notify the newly assigned contractor (graceful no-op w/o Twilio)
    con = svc.get_contractor(body.contractor_id)
    if con and con.get("phone"):
        send_whatsapp(
            con["phone"],
            f"{svc.ACK_TICK} New complaint assigned to {con['name']}. "
            f"Unit {c.get('unit_number') or '?'}, {c.get('category')} "
            f"({c['ticket_number']}). Status: Assigned.",
        )
    # notify the previous contractor they were unassigned
    if prev_cid and prev_cid != body.contractor_id:
        old = svc.get_contractor(prev_cid)
        if old and old.get("phone"):
            send_whatsapp(
                old["phone"],
                f"Update: complaint {c['ticket_number']} "
                f"({c.get('category')}) has been reassigned away from "
                f"{old['name']}. No further action needed.",
            )
    await hub.broadcast("complaint.updated", c)
    return c


@router.post("/complaints/{cid}/rate")
async def rate(
    cid: int, body: RateRequest, _: dict = Depends(current_user)
) -> dict:
    try:
        r = svc.rate_complaint(cid, body.rating, body.feedback)
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
    await hub.broadcast("complaint.rated", {"id": cid, **r})
    return r


@router.post("/complaints/{cid}/status")
async def set_status(
    cid: int, body: StatusUpdateRequest, _: dict = Depends(current_user)
) -> dict:
    try:
        c = svc.update_status(cid, body.status)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await hub.broadcast("complaint.updated", c)
    return c


@router.get("/complaints/{cid}/messages")
def messages(cid: int, _: dict = Depends(current_user)) -> list[dict]:
    return svc.list_messages(cid)


@router.post("/complaints/{cid}/messages", status_code=201)
async def add_message(
    cid: int, body: MessageCreate, _: dict = Depends(current_user)
) -> dict:
    try:
        m = svc.add_message(cid, body.sender, body.body)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await hub.broadcast("message.created", m)
    return m


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        await hub.disconnect(ws)
