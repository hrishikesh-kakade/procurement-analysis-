"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_suppliers")),
        sa.UniqueConstraint("name", name=op.f("uq_suppliers_name")),
        sa.UniqueConstraint("email", name=op.f("uq_suppliers_email")),
    )
    op.create_index(op.f("ix_suppliers_category"), "suppliers", ["category"])
    op.create_index(op.f("ix_suppliers_status"), "suppliers", ["status"])

    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(50), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_materials")),
        sa.UniqueConstraint("sku", name=op.f("uq_materials_sku")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_materials_unit_price_non_negative")),
    )
    op.create_index(op.f("ix_materials_category"), "materials", ["category"])

    op.create_table(
        "requisitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requisition_number", sa.String(40), nullable=False),
        sa.Column("department", sa.String(100), nullable=False),
        sa.Column("requested_by", sa.String(100), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requisitions")),
        sa.UniqueConstraint("requisition_number", name=op.f("uq_requisitions_requisition_number")),
    )
    op.create_index(op.f("ix_requisitions_department"), "requisitions", ["department"])
    op.create_index(op.f("ix_requisitions_status"), "requisitions", ["status"])

    op.create_table(
        "requisition_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requisition_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("estimated_unit_price", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requisition_items")),
        sa.ForeignKeyConstraint(
            ["requisition_id"], ["requisitions.id"],
            name=op.f("fk_requisition_items_requisition_id_requisitions"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"], ["materials.id"],
            name=op.f("fk_requisition_items_material_id_materials"), ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_requisition_items_quantity_positive")),
        sa.CheckConstraint(
            "estimated_unit_price >= 0", name=op.f("ck_requisition_items_estimated_price_non_negative")
        ),
    )
    op.create_index(op.f("ix_requisition_items_requisition_id"), "requisition_items", ["requisition_id"])

    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("po_number", sa.String(40), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("requisition_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=False),
        sa.Column("expected_delivery_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_orders")),
        sa.UniqueConstraint("po_number", name=op.f("uq_purchase_orders_po_number")),
        sa.ForeignKeyConstraint(
            ["supplier_id"], ["suppliers.id"],
            name=op.f("fk_purchase_orders_supplier_id_suppliers"), ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requisition_id"], ["requisitions.id"],
            name=op.f("fk_purchase_orders_requisition_id_requisitions"), ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "expected_delivery_date IS NULL OR expected_delivery_date >= order_date",
            name=op.f("ck_purchase_orders_delivery_after_order"),
        ),
    )
    op.create_index(op.f("ix_purchase_orders_supplier_id"), "purchase_orders", ["supplier_id"])
    op.create_index(op.f("ix_purchase_orders_requisition_id"), "purchase_orders", ["requisition_id"])
    op.create_index(op.f("ix_purchase_orders_status"), "purchase_orders", ["status"])
    op.create_index(op.f("ix_purchase_orders_order_date"), "purchase_orders", ["order_date"])

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("received_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_purchase_order_items")),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"],
            name=op.f("fk_purchase_order_items_purchase_order_id_purchase_orders"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["material_id"], ["materials.id"],
            name=op.f("fk_purchase_order_items_material_id_materials"), ondelete="RESTRICT",
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_purchase_order_items_quantity_positive")),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_purchase_order_items_unit_price_non_negative")),
        sa.CheckConstraint(
            "received_quantity >= 0 AND received_quantity <= quantity",
            name=op.f("ck_purchase_order_items_received_within_ordered"),
        ),
    )
    op.create_index(
        op.f("ix_purchase_order_items_purchase_order_id"), "purchase_order_items", ["purchase_order_id"]
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purchase_order_id", sa.Integer(), nullable=False),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("received_by", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deliveries")),
        sa.ForeignKeyConstraint(
            ["purchase_order_id"], ["purchase_orders.id"],
            name=op.f("fk_deliveries_purchase_order_id_purchase_orders"), ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_deliveries_purchase_order_id"), "deliveries", ["purchase_order_id"])

    op.create_table(
        "delivery_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("delivery_id", sa.Integer(), nullable=False),
        sa.Column("po_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_delivery_items")),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["deliveries.id"],
            name=op.f("fk_delivery_items_delivery_id_deliveries"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["po_item_id"], ["purchase_order_items.id"],
            name=op.f("fk_delivery_items_po_item_id_purchase_order_items"), ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "quantity_received > 0", name=op.f("ck_delivery_items_quantity_received_positive")
        ),
    )
    op.create_index(op.f("ix_delivery_items_delivery_id"), "delivery_items", ["delivery_id"])


def downgrade() -> None:
    for table in (
        "delivery_items",
        "deliveries",
        "purchase_order_items",
        "purchase_orders",
        "requisition_items",
        "requisitions",
        "materials",
        "suppliers",
    ):
        op.drop_table(table)
