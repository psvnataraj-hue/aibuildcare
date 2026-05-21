from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from ..deps import current_user, current_society, require
from ..schemas import (
    ComplaintCreate,
    AssignRequest,
    StatusUpdateRequest,
    MessageCreate,
    RateRequest,
    ConfigUpdate,
)
from ..services import complaint_service as svc
from ..services import rbac, system_config
from ..services.ws_hub import hub
from ..services.notify import send_whatsapp

router = APIRouter(prefix="/api/v1", tags=["complaints"])


@router.get("/analytics",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def analytics() -> dict:
    return svc.analytics()


@router.get("/contractors",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractors() -> list[dict]:
    from ..db import get_conn

    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM contractors WHERE is_active = 1 ORDER BY name"
            ).fetchall()
        ]


@router.get("/complaints",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def list_complaints(
    status: str | None = None,
    q: str | None = None,
    sort: str = "created_at",
    sid: int = Depends(current_society),
) -> list[dict]:
    return svc.list_complaints(
        status=status, q=q, sort=sort, society_id=sid
    )


@router.get("/complaints/mine",
            dependencies=[Depends(require(rbac.RESOLVE))])
def list_my_assignments(
    include_resolved: bool = False,
    sid: int = Depends(current_society),
    user: dict = Depends(current_user),
) -> dict:
    """E3i: complaints currently assigned to the calling user.

    Links user.email -> staff_members.email to find the staff record.
    Returns {staff: {...} | None, complaints: [...]}; an empty staff
    on the frontend means 'no staff_members row matches your email
    yet — ask admin to add you to /staff'.
    """
    from ..db import get_conn

    email = (user.get("email") or "").strip().lower()
    if not email:
        return {"staff": None, "complaints": []}
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, phone_primary FROM staff_members "
            "WHERE society_id = ? AND lower(email) = ? AND active = 1",
            (sid, email),
        ).fetchone()
    if not row:
        return {"staff": None, "complaints": []}
    staff = dict(row)
    return {
        "staff": staff,
        "complaints": svc.list_complaints_assigned_to_staff(
            staff["id"],
            society_id=sid,
            include_resolved=include_resolved,
        ),
    }


@router.post("/complaints", status_code=201,
             dependencies=[Depends(require(rbac.FILE_COMPLAINT))])
async def create_complaint(
    body: ComplaintCreate, sid: int = Depends(current_society)
) -> dict:
    try:
        c = svc.create_complaint(
            body.raw_text, body.channel, body.reporter_phone,
            body.reporter_email, society_id=sid,
            vehicle_plate=body.vehicle_plate,
            violation_type=body.violation_type,
        )
    except svc.ComplaintError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await hub.broadcast("complaint.created", c)
    return c


@router.get("/admin/config",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def get_admin_config() -> dict:
    return system_config.all_config()


@router.post("/admin/config/{key}",
             dependencies=[Depends(require(rbac.MODIFY_CONFIG))])
def set_admin_config(key: str, body: ConfigUpdate) -> dict:
    return system_config.set_config(key, body.value)


@router.get("/contractors/analytics/summary",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractors_analytics_summary() -> dict:
    return svc.analytics_summary()


@router.get("/contractors/{cid}/analytics",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractor_analytics(cid: int) -> dict:
    a = svc.contractor_analytics(cid)
    if not a:
        raise HTTPException(status_code=404, detail="contractor not found")
    return a


@router.get("/contractors/by-category",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractors_by_category(category: str | None = None) -> list[dict]:
    from ..services.contractor_router import contractors_by_category as cbc

    return cbc(category)


@router.get("/contractors/performance",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractors_performance() -> list[dict]:
    return svc.contractor_performance()


@router.get("/contractors/{cid}/performance",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def contractor_performance(cid: int) -> dict:
    rows = svc.contractor_performance(cid)
    if not rows:
        raise HTTPException(status_code=404, detail="contractor not found")
    return rows[0]


@router.get("/complaints/{cid}",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def get_complaint(
    cid: int, sid: int = Depends(current_society)
) -> dict:
    try:
        c = svc.get_complaint(cid, society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    c["messages"] = svc.list_messages(cid, society_id=sid)
    c["rating"] = svc.get_rating(cid, society_id=sid)
    return c


@router.post("/complaints/{cid}/assign",
             dependencies=[Depends(require(rbac.ASSIGN))])
async def assign(
    cid: int, body: AssignRequest, sid: int = Depends(current_society)
) -> dict:
    """Assign EITHER a staff_member or a contractor (exactly one).
    Reassigning to a different contractor also notifies the previous
    contractor that they're no longer responsible."""
    if bool(body.contractor_id) == bool(body.staff_id):
        raise HTTPException(
            400,
            "exactly one of contractor_id or staff_id must be provided",
        )
    try:
        prev = svc.get_complaint(cid, society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    prev_cid = prev.get("contractor_id")

    if body.staff_id:
        try:
            c = svc.assign_staff(cid, body.staff_id, society_id=sid)
        except svc.ComplaintError as e:
            raise HTTPException(status_code=404, detail=str(e))
        # notify the previous contractor (if any) that they were
        # unassigned by this staff handover
        if prev_cid:
            old = svc.get_contractor(prev_cid)
            if old and old.get("phone"):
                send_whatsapp(
                    old["phone"],
                    f"Update: complaint {c['ticket_number']} "
                    f"({c.get('category')}) has been handed over to "
                    f"in-house staff. No further action needed.",
                )
        await hub.broadcast("complaint.updated", c)
        return c

    # contractor path (existing behaviour)
    try:
        c = svc.assign_contractor(cid, body.contractor_id, society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    con = svc.get_contractor(body.contractor_id)
    if con and con.get("phone"):
        send_whatsapp(
            con["phone"],
            f"{svc.ACK_TICK} New complaint assigned to {con['name']}. "
            f"Unit {c.get('unit_number') or '?'}, {c.get('category')} "
            f"({c['ticket_number']}). Status: Assigned.",
        )
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


@router.post("/complaints/{cid}/rate",
             dependencies=[Depends(require(rbac.FILE_COMPLAINT))])
async def rate(
    cid: int, body: RateRequest,
    sid: int = Depends(current_society),
    user: dict = Depends(current_user),
) -> dict:
    # B4 (Gemini audit): a 'resident' role can only rate complaints
    # THEY filed. reporter_email is the ownership marker. Other roles
    # (staff/manager/admin/...) are moderating, not creating fake
    # ratings, and stay unaffected.
    #
    # Normalize both sides + reject empty: emails on email-channel
    # intake come verbatim from the From: header so case can differ
    # from the user's registered email; and legacy rows / malformed
    # JWTs can leave either side as "" which would loose-match.
    if user.get("role") == "resident":
        try:
            owner = svc.get_complaint(cid, society_id=sid)
        except svc.ComplaintError as e:
            raise HTTPException(status_code=404, detail=str(e))
        me = (user.get("email") or "").strip().casefold()
        them = (owner.get("reporter_email") or "").strip().casefold()
        if not me or me != them:
            raise HTTPException(
                status_code=403,
                detail="residents can only rate their own complaints",
            )
    try:
        r = svc.rate_complaint(
            cid, body.rating, body.feedback, society_id=sid
        )
    except svc.ComplaintError as e:
        code = 404 if "not found" in str(e) else 400
        raise HTTPException(status_code=code, detail=str(e))
    await hub.broadcast("complaint.rated", {"id": cid, **r})
    return r


# --- P4: parking enforcement — clamping authorization -----------------
@router.post("/complaints/{cid}/authorize-clamping",
             dependencies=[Depends(require(rbac.AUTHORIZE_ENFORCEMENT))])
async def authorize_clamping(
    cid: int,
    sid: int = Depends(current_society),
    user: dict = Depends(current_user),
) -> dict:
    """Authorize clamping a vehicle reported in a parking complaint.

    Sets clamped=1, clamped_at, clamping_authorized_by on the
    complaint row. Idempotent — re-authorizing a clamped complaint
    is a no-op that returns current state. WhatsApps the linked
    vehicle's owner (if any).

    Restricted to Parking Management category — calling on any other
    category returns 400.
    """
    try:
        c = svc.get_complaint(cid, society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if c.get("category") != svc.PARKING_CATEGORY:
        raise HTTPException(
            status_code=400,
            detail=(
                "authorize-clamping is only valid on Parking Management "
                "complaints"
            ),
        )
    try:
        updated = svc.authorize_clamping(cid, user["id"], society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await hub.broadcast("complaint.updated", updated)
    return updated


@router.post("/complaints/{cid}/status",
             dependencies=[Depends(require(rbac.RESOLVE))])
async def set_status(
    cid: int, body: StatusUpdateRequest,
    sid: int = Depends(current_society),
) -> dict:
    try:
        c = svc.update_status(cid, body.status, society_id=sid)
    except svc.ComplaintError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await hub.broadcast("complaint.updated", c)
    return c


@router.get("/complaints/{cid}/messages",
            dependencies=[Depends(require(rbac.VIEW_ALL))])
def messages(
    cid: int, sid: int = Depends(current_society)
) -> list[dict]:
    return svc.list_messages(cid, society_id=sid)


@router.post("/complaints/{cid}/messages", status_code=201,
             dependencies=[Depends(require(rbac.RESOLVE))])
async def add_message(
    cid: int, body: MessageCreate, sid: int = Depends(current_society)
) -> dict:
    try:
        m = svc.add_message(cid, body.sender, body.body, society_id=sid)
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
