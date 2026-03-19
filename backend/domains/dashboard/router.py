"""Domain router entry for `dashboard`."""

from fastapi import APIRouter

from .router_accounts import router as accounts_router
from .router_margin import router as margin_router
from .router_overview import router as overview_router

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
router.include_router(overview_router)
router.include_router(accounts_router)
router.include_router(margin_router)

__all__ = ["router"]
