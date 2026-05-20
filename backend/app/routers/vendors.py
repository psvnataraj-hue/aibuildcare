"""Vendor / personal-job directory endpoints.

Resident-facing read of society-vetted contractors who handle personal
jobs, with click-to-chat WhatsApp links. Gated by FILE_COMPLAINT
(every authenticated role that can file complaints can also see the
vendor list — including residents, when the resident portal lands).
"""
from fastapi import APIRouter, Depends, Query

from ..deps import current_society, require
from ..services import rbac, vendor_directory

router = APIRouter(prefix="/api/v1", tags=["vendors"])


@router.get("/vendors/by-category",
            dependencies=[Depends(require(rbac.FILE_COMPLAINT))])
def vendors_by_category(
    category: str = Query(..., min_length=1),
    sid: int = Depends(current_society),
) -> list[dict]:
    return vendor_directory.list_vendors(sid, category)
