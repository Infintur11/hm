from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_permissions
from app.schemas.corporate import (
    CorporateClientCreate, CorporateClientUpdate, CorporateLimitUpdate,
    CustomKpiCreate
)
from app.services.corporate_service import (
    get_corporate_clients, get_corporate_client_detail,
    create_corporate_client, update_corporate_client,
    update_credit_limit, get_corporate_summary
)
from app.services.kpi_service import (
    get_active_custom_kpis, get_available_query_catalog,
    add_custom_kpi, delete_custom_kpi,
    get_granular_financial_breakdown
)
from typing import Optional

router = APIRouter(prefix="/api/corporate", tags=["Corporate, Insurance & KPI Studio"])

# =========================================================================
# 1. CORPORATE & INSURANCE CLIENT TIE-UPS
# =========================================================================

@router.get("/clients")
def api_list_corporate_clients(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Lists corporate and insurance tie-up partners with credit limits and utilization."""
    return get_corporate_clients(db, active_only)

@router.get("/summary")
def api_corporate_summary(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Summary metrics of all corporate credit limits and utilization pool."""
    return get_corporate_summary(db)

@router.get("/clients/{client_id}")
def api_get_corporate_client(
    client_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Detailed corporate partner account with billed invoices."""
    return get_corporate_client_detail(db, client_id)

@router.post("/clients")
def api_create_corporate_client(
    data: CorporateClientCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Admin & Superadmin create insurance / corporate tie-up accounts."""
    if user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only hospital administrators can configure corporate accounts")
    return create_corporate_client(db, data)

@router.put("/clients/{client_id}")
def api_update_corporate_client(
    client_id: int,
    data: CorporateClientUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Admin & Superadmin update corporate partner details."""
    if user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only hospital administrators can update corporate accounts")
    return update_corporate_client(db, client_id, data)

@router.put("/clients/{client_id}/limit")
def api_update_credit_limit(
    client_id: int,
    data: CorporateLimitUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Directly adjust the monthly credit limit for a corporate / insurance partner."""
    if user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only hospital administrators can adjust corporate credit limits")
    return update_credit_limit(db, client_id, data.monthly_credit_limit, data.notes)


# =========================================================================
# 2. DYNAMIC PRE-BUILT SQL KPI STUDIO
# =========================================================================

@router.get("/kpis/active")
def api_get_active_kpis(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Active KPI cards pinned by Admin to top of dashboard."""
    return get_active_custom_kpis(db)

@router.get("/kpis/catalog")
def api_get_kpi_catalog(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Catalog of pre-built SQL analytical queries with live values."""
    return get_available_query_catalog(db)

@router.post("/kpis")
def api_add_kpi_card(
    data: CustomKpiCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Admin pins a pre-built SQL query as a top dashboard metric card."""
    if user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only administrators can customize dashboard KPIs")
    return add_custom_kpi(db, data.query_key, data.title, data.accent_color)

@router.delete("/kpis/{kpi_id}")
def api_delete_kpi_card(
    kpi_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Admin removes a KPI metric card from top dashboard."""
    if user.role not in ["ADMIN", "SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only administrators can customize dashboard KPIs")
    return delete_custom_kpi(db, kpi_id)


# =========================================================================
# 3. GRANULAR FINANCIAL ANALYTICS
# =========================================================================

@router.get("/analytics/granular")
def api_get_granular_financials(
    period: Optional[str] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Produces minute, granular outputs breaking down data across all dimensions."""
    return get_granular_financial_breakdown(db, period)
