"""Vehicles (parking) registry — Parking P1.

Per-society plate registry feeding the (future P2) auto-link of a
parking complaint to its owner. Society-scoped reads + writes. Plate
uniqueness is per-society (different societies can register the same
plate; not a global identity).

Soft-delete semantics: `active=0` instead of physical DELETE. The
DELETE endpoint flips active=0; a separate `restore` flag on update
flips it back. Hard delete is intentionally NOT exposed (parking
violations may still reference a deactivated owner).
"""
from __future__ import annotations

import re

from ..db import get_conn


class VehiclesError(Exception):
    pass


_VEHICLE_TYPES = {
    "car", "two-wheeler", "scooter", "bike", "suv",
    "van", "auto", "truck", "other",
}


def _validate_plate(plate: str) -> str:
    """Strip whitespace + dashes, uppercase. Returns a stored form
    (e.g. 'MH01AB1234' from 'MH 01 AB-1234'). Empty -> raises."""
    if not plate or not plate.strip():
        raise VehiclesError("plate_number is required")
    stored = re.sub(r"[\s\-]", "", plate).upper()
    if not stored:
        raise VehiclesError("plate_number cannot be only whitespace")
    return stored


def _validate_vehicle_type(vtype: str | None) -> str | None:
    if vtype is None or vtype == "":
        return None
    if vtype.lower() not in _VEHICLE_TYPES:
        raise VehiclesError(
            f"vehicle_type must be one of: {sorted(_VEHICLE_TYPES)}"
        )
    return vtype.lower()


def _shape(row: dict) -> dict:
    d = dict(row)
    d["active"] = bool(d.get("active"))
    return d


def list_vehicles(
    society_id: int, include_inactive: bool = False,
    plate_search: str | None = None,
) -> list[dict]:
    with get_conn() as conn:
        clauses = ["society_id = ?"]
        params: list = [society_id]
        if not include_inactive:
            clauses.append("active = 1")
        if plate_search:
            clauses.append("plate_number LIKE ?")
            # normalize the search term the same way we normalize stored
            # plates so 'MH 01' finds 'MH01...'
            normalized = re.sub(r"[\s\-]", "", plate_search).upper()
            params.append(f"%{normalized}%")
        sql = (
            "SELECT * FROM vehicles WHERE "
            + " AND ".join(clauses)
            + " ORDER BY plate_number"
        )
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
        return [_shape(r) for r in rows]


def get_vehicle(vehicle_id: int, society_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM vehicles WHERE id = ? AND society_id = ?",
            (vehicle_id, society_id),
        ).fetchone()
        if not row:
            raise VehiclesError("vehicle not found")
        return _shape(dict(row))


def find_by_plate(
    society_id: int, plate_number: str,
) -> dict | None:
    """Lookup by plate (normalized). Returns None if no match —
    won't be used by routes directly, but P2 will call this when a
    parking complaint comes in to auto-link the owner."""
    try:
        plate = _validate_plate(plate_number)
    except VehiclesError:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM vehicles "
            "WHERE society_id = ? AND plate_number = ? AND active = 1",
            (society_id, plate),
        ).fetchone()
        return _shape(dict(row)) if row else None


def create_vehicle(
    society_id: int,
    plate_number: str,
    owner_unit_number: str | None = None,
    owner_name: str | None = None,
    owner_phone: str | None = None,
    vehicle_type: str | None = None,
    make_model: str | None = None,
    color: str | None = None,
    registered_at: str | None = None,
    notes: str | None = None,
) -> dict:
    plate = _validate_plate(plate_number)
    vtype = _validate_vehicle_type(vehicle_type)
    with get_conn() as conn:
        dup = conn.execute(
            "SELECT id FROM vehicles "
            "WHERE society_id = ? AND plate_number = ?",
            (society_id, plate),
        ).fetchone()
        if dup:
            raise VehiclesError(
                f"plate {plate} already registered in this society"
            )
        conn.execute(
            "INSERT INTO vehicles (society_id, plate_number, "
            "owner_unit_number, owner_name, owner_phone, vehicle_type, "
            "make_model, color, registered_at, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                society_id, plate, owner_unit_number, owner_name,
                owner_phone, vtype, make_model, color, registered_at,
                notes,
            ),
        )
        row = conn.execute(
            "SELECT * FROM vehicles "
            "WHERE society_id = ? AND plate_number = ?",
            (society_id, plate),
        ).fetchone()
        return _shape(dict(row))


def update_vehicle(
    vehicle_id: int, society_id: int, **fields,
) -> dict:
    """Partial update. Pass active=True to reactivate a soft-deleted
    row. plate_number is editable but stays uniqueness-checked."""
    if not fields:
        return get_vehicle(vehicle_id, society_id)
    if "plate_number" in fields and fields["plate_number"] is not None:
        fields["plate_number"] = _validate_plate(fields["plate_number"])
    if "vehicle_type" in fields:
        fields["vehicle_type"] = _validate_vehicle_type(
            fields["vehicle_type"]
        )
    if "active" in fields and fields["active"] is not None:
        fields["active"] = 1 if fields["active"] else 0
    with get_conn() as conn:
        # uniqueness: only check when plate changes
        if "plate_number" in fields and fields["plate_number"]:
            dup = conn.execute(
                "SELECT id FROM vehicles WHERE society_id = ? "
                "AND plate_number = ? AND id != ?",
                (society_id, fields["plate_number"], vehicle_id),
            ).fetchone()
            if dup:
                raise VehiclesError(
                    f"plate {fields['plate_number']} already registered "
                    "in this society"
                )
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [vehicle_id, society_id]
        cur = conn.execute(
            f"UPDATE vehicles SET {sets} "
            "WHERE id = ? AND society_id = ?",
            values,
        )
        if cur.rowcount == 0:
            raise VehiclesError("vehicle not found")
        row = conn.execute(
            "SELECT * FROM vehicles WHERE id = ? AND society_id = ?",
            (vehicle_id, society_id),
        ).fetchone()
        return _shape(dict(row))


def deactivate_vehicle(vehicle_id: int, society_id: int) -> dict:
    """Soft-delete (active=0). Returns the updated row.

    Intentionally not a hard delete — parking complaints in
    `complaints.vehicle_id` may still reference this row and we want
    them to keep displaying the owner name (e.g. for the repeat-
    offender heuristic in P3)."""
    return update_vehicle(vehicle_id, society_id, active=False)
