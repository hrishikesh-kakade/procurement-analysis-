from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column
from app.models.enums import QuotationStatus, RfqStatus


class Rfq(TimestampMixin, Base):
    __tablename__ = "rfqs"

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_number: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    requisition_id: Mapped[int | None] = mapped_column(
        ForeignKey("requisitions.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[RfqStatus] = mapped_column(
        enum_column(RfqStatus), default=RfqStatus.DRAFT, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    awarded_po_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="SET NULL")
    )

    items: Mapped[list["RfqItem"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="RfqItem.id", lazy="selectin"
    )
    quotations: Mapped[list["Quotation"]] = relationship(
        back_populates="rfq", cascade="all, delete-orphan", order_by="Quotation.id", lazy="selectin"
    )


class RfqItem(Base):
    __tablename__ = "rfq_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer)

    rfq: Mapped[Rfq] = relationship(back_populates="items")


class Quotation(TimestampMixin, Base):
    __tablename__ = "quotations"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_id", name="uq_quotations_rfq_id_supplier_id"),
        CheckConstraint("delivery_days >= 0", name="delivery_days_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rfq_id: Mapped[int] = mapped_column(ForeignKey("rfqs.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[int] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[QuotationStatus] = mapped_column(
        enum_column(QuotationStatus), default=QuotationStatus.SUBMITTED
    )
    delivery_days: Mapped[int] = mapped_column(Integer)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    notes: Mapped[str | None] = mapped_column(Text)

    rfq: Mapped[Rfq] = relationship(back_populates="quotations")
    items: Mapped[list["QuotationItem"]] = relationship(
        back_populates="quotation",
        cascade="all, delete-orphan",
        order_by="QuotationItem.id",
        lazy="selectin",
    )


class QuotationItem(Base):
    __tablename__ = "quotation_items"
    __table_args__ = (CheckConstraint("unit_price >= 0", name="unit_price_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), index=True
    )
    rfq_item_id: Mapped[int] = mapped_column(ForeignKey("rfq_items.id", ondelete="CASCADE"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    quotation: Mapped[Quotation] = relationship(back_populates="items")
