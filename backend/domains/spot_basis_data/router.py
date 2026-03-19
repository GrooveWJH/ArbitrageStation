"""Domain router entry for `spot_basis_data`."""

from fastapi import APIRouter

from .router_base import router as base_router
from .router_jobs import router as jobs_router

router = APIRouter(prefix="/api/spot-basis-data", tags=["spot-basis-data"])
router.include_router(base_router)
router.include_router(jobs_router)

__all__ = ["router"]
