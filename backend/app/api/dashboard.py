import math
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.auth import require_admin
from app.database import get_db
from app.models import Vendor, SubmissionStatus
from app.schemas import DashboardStats, PaginatedVendors, VendorOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), _=Depends(require_admin)):
    """Get dashboard summary statistics."""
    counts = (
        db.query(Vendor.status, func.count(Vendor.id).label("count"))
        .group_by(Vendor.status)
        .all()
    )

    status_map = {row.status: row.count for row in counts}
    total = sum(status_map.values())

    return DashboardStats(
        total=total,
        approved=status_map.get("approved", 0),
        pending=status_map.get("pending", 0),
        rejected=status_map.get("rejected", 0),
        processing=status_map.get("processing", 0),
        error=status_map.get("error", 0),
    )


@router.get("/history", response_model=PaginatedVendors)
def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Get paginated vendor submission history with optional filters."""
    query = db.query(Vendor)

    if status and status != "all":
        try:
            status_enum = SubmissionStatus(status)
            query = query.filter(Vendor.status == status_enum)
        except ValueError:
            pass

    if search:
        query = query.filter(
            Vendor.company_name.ilike(f"%{search}%") |
            Vendor.contact_email.ilike(f"%{search}%") |
            Vendor.run_id.ilike(f"%{search}%")
        )

    total = query.count()
    pages = math.ceil(total / page_size) if total > 0 else 1

    vendors = (
        query.order_by(desc(Vendor.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedVendors(
        items=[
            VendorOut(
                id=str(v.id),
                run_id=v.run_id,
                company_name=v.company_name,
                registration_number=v.registration_number,
                country=v.country,
                contact_name=v.contact_name,
                contact_email=v.contact_email,
                tax_id=v.tax_id,
                bank_account_name=v.bank_account_name,
                bank_country=v.bank_country,
                status=v.status,
                current_stage=v.current_stage if v.current_stage else None,
                decision_summary=v.decision_summary,
                risk_level=v.risk_level,
                is_duplicate=v.is_duplicate,
                duplicate_of_run_id=v.duplicate_of_run_id,
                created_at=v.created_at,
                updated_at=v.updated_at,
                decided_at=v.decided_at,
            )
            for v in vendors
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
