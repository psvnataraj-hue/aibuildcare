"""Vehicles (parking) registry — Parking P1.

GET    /api/v1/vehicles                       -- list (VIEW_ALL)
GET    /api/v1/vehicles/{id}                  -- detail (VIEW_ALL)
GET    /api/v1/vehicles/by-plate?plate=X      -- lookup helper (VIEW_ALL)
POST   /api/v1/vehicles                       -- create (MODIFY_STAFF)
PUT    /api/v1/vehicles/{id}                  -- partial update (MODIFY_STAFF)
DELETE /api/v1/vehicles/{id}                  -- soft-delete (MODIFY_STAFF)

Gated by VIEW_ALL for reads and MODIFY_STAFF for mutations (matches
the contractor/staff CRUD precedent). Society-scoped via
`current_society` — callers never see other societies' vehicles.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import current_society, require
from ..services import rbac, vehicles_service

router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"])


class VehicleCreate(BaseModel):
    plate_number: str = Field(min_length=1)
    owner_unit_number: str | None = None
    owner_name: str | None = None
    owner_phone: str | None = None
    vehicle_type: str | None = None
    make_model: str | None = None
    color: str | None = None
    registered_at: str | None = None
    notes: str | None = None


class VehiclePatch(BaseModel):
    plate_number: str | None = None
    owner_unit_number: str | None = None
    owner_name: str | None = None
    owner_phone: str | None = None
    vehicle_type: str | None = None
    make_model: str | None = None
    color: str | None = None
    registered_at: str | None = None
    notes: str | None = None
    active: bool | None = None


@router.get("", dependencies=[Depends(require(rbac.VIEW_ALL))])
def list_vehicles(
    include_inactive: bool = False,
    plate_search: str | None = None,
    sid: int = Depends(current_society),
) -> list[dict]:
    return vehicles_service.list_vehicles(
        sid, include_inactive=include_inactive,
        plate_search=plate_search,
    )


@router.get(
    "/by-plate",
    dependencies=[Depends(require(rbac.VIEW_ALL))],
)
def get_by_plate(
    plate: str = Query(..., min_length=1),
    sid: int = Depends(current_society),
) -> dict:
    """Plate -> owner lookup (helper). 404 when no match instead of
    returning null so the dashboard can show a clean 'not found'."""
    v = vehicles_service.find_by_plate(sid, plate)
    if not v:
        raise HTTPException(404, "no vehicle registered with that plate")
    return v


@router.get(
    "/{vehicle_id}",
    dependencies=[Depends(require(rbac.VIEW_ALL))],
)
def get_vehicle(
    vehicle_id: int, sid: int = Depends(current_society),
) -> dict:
    try:
        return vehicles_service.get_vehicle(vehicle_id, sid)
    except vehicles_service.VehiclesError as e:
        raise HTTPException(404, str(e))


@router.post(
    "", status_code=201,
    dependencies=[Depends(require(rbac.MODIFY_STAFF))],
)
def create_vehicle(
    body: VehicleCreate, sid: int = Depends(current_society),
) -> dict:
    try:
        return vehicles_service.create_vehicle(
            sid, **body.model_dump(),
        )
    except vehicles_service.VehiclesError as e:
        # 409 for duplicate plate (already-exists) vs 400 for bad input
        code = 409 if "already registered" in str(e) else 400
        raise HTTPException(code, str(e))


@router.put(
    "/{vehicle_id}",
    dependencies=[Depends(require(rbac.MODIFY_STAFF))],
)
def update_vehicle(
    vehicle_id: int, body: VehiclePatch,
    sid: int = Depends(current_society),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return vehicles_service.update_vehicle(
            vehicle_id, sid, **fields,
        )
    except vehicles_service.VehiclesError as e:
        msg = str(e)
        if "not found" in msg:
            code = 404
        elif "already registered" in msg:
            code = 409
        else:
            code = 400
        raise HTTPException(code, msg)


@router.delete(
    "/{vehicle_id}",
    dependencies=[Depends(require(rbac.MODIFY_STAFF))],
)
def deactivate_vehicle(
    vehicle_id: int, sid: int = Depends(current_society),
) -> dict:
    """Soft-delete (active=0). Hard delete is intentionally absent;
    parking complaints in P2 will reference this row by id."""
    try:
        return vehicles_service.deactivate_vehicle(vehicle_id, sid)
    except vehicles_service.VehiclesError as e:
        raise HTTPException(404, str(e))
