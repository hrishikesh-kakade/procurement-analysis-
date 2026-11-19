"""Status state machines. Every status change in the system goes through ensure_transition."""

from collections.abc import Mapping

from app.core.exceptions import InvalidTransitionError
from app.models.enums import PurchaseOrderStatus as PO
from app.models.enums import RequisitionStatus as REQ
from app.models.enums import RfqStatus as RFQ

REQUISITION_TRANSITIONS: Mapping[REQ, frozenset[REQ]] = {
    REQ.DRAFT: frozenset({REQ.SUBMITTED}),
    REQ.SUBMITTED: frozenset({REQ.APPROVED, REQ.REJECTED}),
    REQ.APPROVED: frozenset({REQ.CONVERTED}),
    REQ.REJECTED: frozenset(),
    REQ.CONVERTED: frozenset(),
}

PURCHASE_ORDER_TRANSITIONS: Mapping[PO, frozenset[PO]] = {
    PO.DRAFT: frozenset({PO.ISSUED, PO.CANCELLED}),
    PO.ISSUED: frozenset({PO.PARTIALLY_RECEIVED, PO.RECEIVED, PO.CANCELLED}),
    PO.PARTIALLY_RECEIVED: frozenset({PO.RECEIVED}),
    PO.RECEIVED: frozenset(),
    PO.CANCELLED: frozenset(),
}


def ensure_transition(transitions: Mapping, current, target, entity: str) -> None:
    if target not in transitions[current]:
        raise InvalidTransitionError(
            f"Cannot change {entity} status from '{current}' to '{target}'"
        )

RFQ_TRANSITIONS: Mapping[RFQ, frozenset[RFQ]] = {
    RFQ.DRAFT: frozenset({RFQ.PUBLISHED, RFQ.CANCELLED}),
    RFQ.PUBLISHED: frozenset({RFQ.CLOSED, RFQ.AWARDED, RFQ.CANCELLED}),
    RFQ.CLOSED: frozenset({RFQ.AWARDED, RFQ.CANCELLED}),
    RFQ.AWARDED: frozenset(),
    RFQ.CANCELLED: frozenset(),
}
