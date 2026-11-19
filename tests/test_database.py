"""Database-level guarantees (run on SQLite locally and on PostgreSQL in CI/Docker)."""

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import engine
from app.models import Material, Requisition, RequisitionItem, Supplier

EXPECTED_TABLES = {
    "suppliers",
    "materials",
    "requisitions",
    "requisition_items",
    "purchase_orders",
    "purchase_order_items",
    "deliveries",
    "delivery_items",
    "users",
    "rfqs",
    "rfq_items",
    "quotations",
    "quotation_items",
    "knowledge_documents",
}


def test_check_constraint_blocks_non_positive_quantity():
    with Session(engine) as db:
        material = Material(sku="CHK-1", name="Widget", category="x1", unit_price=1)
        requisition = Requisition(requisition_number="REQ-TEST-1", department="IT", requested_by="T")
        db.add_all([material, requisition])
        db.flush()
        db.add(
            RequisitionItem(
                requisition_id=requisition.id, material_id=material.id, quantity=0, estimated_unit_price=1
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()


def test_unique_constraint_on_supplier_email():
    with Session(engine) as db:
        db.add(Supplier(name="One", category="x1", email="same@acme-corp.com"))
        db.add(Supplier(name="Two", category="x1", email="same@acme-corp.com"))
        with pytest.raises(IntegrityError):
            db.flush()


def test_foreign_keys_are_enforced():
    with Session(engine) as db:
        db.add(RequisitionItem(requisition_id=999, material_id=999, quantity=1, estimated_unit_price=1))
        with pytest.raises(IntegrityError):
            db.flush()


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL")
def test_alembic_migrations_upgrade_and_downgrade():
    Base.metadata.drop_all(engine)
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())
    command.downgrade(config, "base")
    assert not EXPECTED_TABLES & set(inspect(engine).get_table_names())
