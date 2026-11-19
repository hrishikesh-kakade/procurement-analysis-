from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.models.enums import PurchaseOrderStatus
from app.models.requisition import Requisition
from app.models.supplier import Supplier


class PurchaseOrder(TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        CheckConstraint(
            "expected_delivery_date IS NULL OR expected_delivery_date >= order_date",
            name="delivery_after_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    po_number: Mapped[str] = mapped_column(String(40), unique=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    requisition_id: Mapped[int | None] = mapped_column(
        ForeignKey("requisitions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[PurchaseOrderStatus] = mapped_column(
        enum_column(PurchaseOrderStatus), default=PurchaseOrderStatus.DRAFT, index=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    order_date: Mapped[date] = mapped_column(Date, default=date.today, index=True)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    supplier: Mapped[Supplier] = relationship()
    requisition: Mapped[Requisition | None] = relationship()
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderItem.id",
        lazy="selectin",
    )
    deliveries: Mapped[list["Delivery"]] = relationship(  # noqa: F821
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="Delivery.id",
    )


class PurchaseOrderItem(Base):
    __tablename__ = "purchase_order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),
        CheckConstraint(
            "received_quantity >= 0 AND received_quantity <= quantity",
            name="received_within_ordered",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    received_quantity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
