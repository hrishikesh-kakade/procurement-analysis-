from datetime import date
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.db.session import get_db
from app.schemas.common import DateRange, PaginationParams
from app.services.analytics_service import AnalyticsService
from app.services.assistant.service import AssistantService
from app.services.delivery_service import DeliveryService
from app.services.job_service import JobService
from app.services.material_service import MaterialService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.rag.knowledge_service import KnowledgeService
from app.services.requisition_service import RequisitionService
from app.services.rfq_service import RfqService
from app.services.supplier_service import SupplierService
from app.services.user_service import UserService

DbSession = Annotated[Session, Depends(get_db)]


def pagination_params(
    page: Annotated[int, Query(ge=1, description="Page number (1-based)")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


def date_range(
    date_from: Annotated[date | None, Query(description="Inclusive start date (YYYY-MM-DD)")] = None,
    date_to: Annotated[date | None, Query(description="Inclusive end date (YYYY-MM-DD)")] = None,
) -> DateRange:
    if date_from and date_to and date_from > date_to:
        raise BusinessRuleError("date_from must not be after date_to")
    return DateRange(date_from=date_from, date_to=date_to)


Pagination = Annotated[PaginationParams, Depends(pagination_params)]
Range = Annotated[DateRange, Depends(date_range)]


def _supplier_service(db: DbSession) -> SupplierService:
    return SupplierService(db)


def _material_service(db: DbSession) -> MaterialService:
    return MaterialService(db)


def _requisition_service(db: DbSession) -> RequisitionService:
    return RequisitionService(db)


def _purchase_order_service(db: DbSession) -> PurchaseOrderService:
    return PurchaseOrderService(db)


def _delivery_service(db: DbSession) -> DeliveryService:
    return DeliveryService(db)


def _analytics_service(db: DbSession) -> AnalyticsService:
    return AnalyticsService(db)


def _rfq_service(db: DbSession) -> RfqService:
    return RfqService(db)


def _assistant_service(db: DbSession) -> AssistantService:
    return AssistantService(db)


def _job_service(db: DbSession) -> JobService:
    return JobService(db)


def _knowledge_service(db: DbSession) -> KnowledgeService:
    return KnowledgeService(db)


def _user_service(db: DbSession) -> UserService:
    return UserService(db)


SupplierSvc = Annotated[SupplierService, Depends(_supplier_service)]
MaterialSvc = Annotated[MaterialService, Depends(_material_service)]
RequisitionSvc = Annotated[RequisitionService, Depends(_requisition_service)]
PurchaseOrderSvc = Annotated[PurchaseOrderService, Depends(_purchase_order_service)]
DeliverySvc = Annotated[DeliveryService, Depends(_delivery_service)]
AnalyticsSvc = Annotated[AnalyticsService, Depends(_analytics_service)]
UserSvc = Annotated[UserService, Depends(_user_service)]
RfqSvc = Annotated[RfqService, Depends(_rfq_service)]
AssistantSvc = Annotated[AssistantService, Depends(_assistant_service)]
JobSvc = Annotated[JobService, Depends(_job_service)]
KnowledgeSvc = Annotated[KnowledgeService, Depends(_knowledge_service)]
