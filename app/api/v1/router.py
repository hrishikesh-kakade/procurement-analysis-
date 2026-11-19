from fastapi import APIRouter

from app.api.permissions import ADMIN_ONLY, ANALYTICS_READ, AUTHENTICATED
from app.api.v1 import (
    analytics,
    assistant,
    auth,
    knowledge,
    materials,
    purchase_orders,
    reports,
    requisitions,
    rfqs,
    suppliers,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)  # login is public; other auth routes self-protect
api_router.include_router(users.router, dependencies=ADMIN_ONLY)
for module in (analytics, assistant, reports):
    api_router.include_router(module.router, dependencies=ANALYTICS_READ)
for module in (suppliers, materials, requisitions, purchase_orders, rfqs, knowledge):
    api_router.include_router(module.router, dependencies=AUTHENTICATED)
