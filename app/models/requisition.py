from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import money
from app.db.base import Base, TimestampMixin, enum_column
from app.models.enums import RequisitionStatus


class Requisition(TimestampMixin, Base):
    __tablename__ = "requisitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_number: Mapped[str] = mapped_column(String(40), unique=True)
    department: Mapped[str] = mapped_column(String(100), index=True)
    requested_by: Mapped[str] = mapped_column(String(100))
    justification: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RequisitionStatus] = mapped_column(
        enum_column(RequisitionStatus), default=RequisitionStatus.DRAFT, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["RequisitionItem"]] = relationship(
        back_populates="requisition",
        cascade="all, delete-orphan",
        order_by="RequisitionItem.id",
        lazy="selectin",
    )

    @property
    def total_estimated_amount(self) -> Decimal:
        return money.order_total(item.line_total for item in self.items)


class RequisitionItem(Base):
    __tablename__ = "requisition_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("estimated_unit_price >= 0", name="estimated_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(
        ForeignKey("requisitions.id", ondelete="CASCADE"), index=True
    )
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id", ondelete="RESTRICT"))
    quantity: Mapped[int] = mapped_column(Integer)
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    requisition: Mapped[Requisition] = relationship(back_populates="items")

    @property
    def line_total(self) -> Decimal:
        return money.line_total(self.quantity, self.estimated_unit_price)
