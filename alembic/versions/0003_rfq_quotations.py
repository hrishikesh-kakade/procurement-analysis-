"""rfq and quotations

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "rfqs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rfq_number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requisition_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("awarded_po_id", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rfqs")),
        sa.UniqueConstraint("rfq_number", name=op.f("uq_rfqs_rfq_number")),
        sa.ForeignKeyConstraint(["requisition_id"], ["requisitions.id"], name=op.f("fk_rfqs_requisition_id_requisitions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["awarded_po_id"], ["purchase_orders.id"], name=op.f("fk_rfqs_awarded_po_id_purchase_orders"), ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_rfqs_requisition_id"), "rfqs", ["requisition_id"])
    op.create_index(op.f("ix_rfqs_status"), "rfqs", ["status"])

    op.create_table(
        "rfq_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rfq_items")),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], name=op.f("fk_rfq_items_rfq_id_rfqs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], name=op.f("fk_rfq_items_material_id_materials"), ondelete="RESTRICT"),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_rfq_items_quantity_positive")),
    )
    op.create_index(op.f("ix_rfq_items_rfq_id"), "rfq_items", ["rfq_id"])

    op.create_table(
        "quotations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rfq_id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotations")),
        sa.UniqueConstraint("rfq_id", "supplier_id", name=op.f("uq_quotations_rfq_id_supplier_id")),
        sa.ForeignKeyConstraint(["rfq_id"], ["rfqs.id"], name=op.f("fk_quotations_rfq_id_rfqs"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"], name=op.f("fk_quotations_supplier_id_suppliers"), ondelete="RESTRICT"),
        sa.CheckConstraint("delivery_days >= 0", name=op.f("ck_quotations_delivery_days_non_negative")),
    )
    op.create_index(op.f("ix_quotations_rfq_id"), "quotations", ["rfq_id"])
    op.create_index(op.f("ix_quotations_supplier_id"), "quotations", ["supplier_id"])

    op.create_table(
        "quotation_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quotation_id", sa.Integer(), nullable=False),
        sa.Column("rfq_item_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotation_items")),
        sa.ForeignKeyConstraint(["quotation_id"], ["quotations.id"], name=op.f("fk_quotation_items_quotation_id_quotations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rfq_item_id"], ["rfq_items.id"], name=op.f("fk_quotation_items_rfq_item_id_rfq_items"), ondelete="CASCADE"),
        sa.CheckConstraint("unit_price >= 0", name=op.f("ck_quotation_items_unit_price_non_negative")),
    )
    op.create_index(op.f("ix_quotation_items_quotation_id"), "quotation_items", ["quotation_id"])


def downgrade() -> None:
    for table in ("quotation_items", "quotations", "rfq_items", "rfqs"):
        op.drop_table(table)
