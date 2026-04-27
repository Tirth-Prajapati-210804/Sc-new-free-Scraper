from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.collection import router as collection_router
from app.api.v1.routes.prices import router as prices_router
from app.api.v1.routes.route_groups import router as route_groups_router
from app.api.v1.routes.stats import router as stats_router
from app.api.v1.routes.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(collection_router)
router.include_router(route_groups_router)
router.include_router(prices_router)
router.include_router(stats_router)
router.include_router(users_router)
