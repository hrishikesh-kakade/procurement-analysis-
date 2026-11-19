from decimal import Decimal

import pytest

from app.core.exceptions import InvalidTransitionError
from app.core.money import line_total, order_total, quantize_money
from app.models.enums import PurchaseOrderStatus as PO
from app.models.enums import RequisitionStatus as REQ
from app.services.workflow import (
    PURCHASE_ORDER_TRANSITIONS,
    REQUISITION_TRANSITIONS,
    ensure_transition,
)


def test_line_total_rounds_half_up():
    assert line_total(3, Decimal("19.995")) == Decimal("59.99")
    assert line_total(2, "0.005") == Decimal("0.01")


def test_order_total_sums_lines():
    assert order_total([Decimal("10.10"), Decimal("20.20")]) == Decimal("30.30")
    assert order_total([]) == Decimal("0.00")


def test_quantize_money_accepts_floats_without_drift():
    assert quantize_money(0.1 + 0.2) == Decimal("0.30")


@pytest.mark.parametrize(
    ("current", "target"),
    [(REQ.DRAFT, REQ.SUBMITTED), (REQ.SUBMITTED, REQ.APPROVED), (REQ.SUBMITTED, REQ.REJECTED)],
)
def test_valid_requisition_transitions(current, target):
    ensure_transition(REQUISITION_TRANSITIONS, current, target, "requisition")


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (REQ.REJECTED, REQ.APPROVED),
        (REQ.APPROVED, REQ.REJECTED),
        (REQ.DRAFT, REQ.APPROVED),
        (REQ.CONVERTED, REQ.DRAFT),
    ],
)
def test_invalid_requisition_transitions(current, target):
    with pytest.raises(InvalidTransitionError):
        ensure_transition(REQUISITION_TRANSITIONS, current, target, "requisition")


def test_terminal_purchase_order_states_have_no_exits():
    assert PURCHASE_ORDER_TRANSITIONS[PO.RECEIVED] == frozenset()
    assert PURCHASE_ORDER_TRANSITIONS[PO.CANCELLED] == frozenset()
    with pytest.raises(InvalidTransitionError):
        ensure_transition(PURCHASE_ORDER_TRANSITIONS, PO.CANCELLED, PO.ISSUED, "purchase order")
