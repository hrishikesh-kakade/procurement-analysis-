"""Populate the database with demo data.  Usage: python -m scripts.seed"""

import random
from datetime import date, timedelta

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models import Supplier
from app.models.enums import PurchaseOrderStatus
from app.schemas.delivery import DeliveryCreate, DeliveryItemCreate
from app.schemas.material import MaterialCreate
from app.schemas.purchase_order import PurchaseOrderCreate
from app.schemas.rfq import QuotationCreate, QuotationItemCreate, RfqCreate, RfqItemCreate
from app.schemas.requisition import RequisitionCreate, RequisitionItemCreate
from app.schemas.supplier import SupplierCreate
from app.services.delivery_service import DeliveryService
from app.services.material_service import MaterialService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.rfq_service import RfqService
from app.services.requisition_service import RequisitionService
from app.services.supplier_service import SupplierService

SUPPLIERS = [
    ("Acme Industrial Supplies", "machinery", "sales@acme-industrial.com"),
    ("Brightline Electronics", "electronics", "orders@brightline-electronics.com"),
    ("PackWell Packaging", "packaging", "hello@packwell.in"),
    ("OfficeHub Traders", "office-supplies", "support@officehub.in"),
    ("ChemPure Labs", "chemicals", "accounts@chempure.com"),
    ("SwiftMove Logistics", "logistics", "ops@swiftmove.in"),
]
MATERIALS = [
    ("MCH-001", "Hydraulic pump", "machinery", "each", "18500.00"),
    ("MCH-002", "Industrial bearing set", "machinery", "set", "2400.00"),
    ("ELE-001", "PLC controller", "electronics", "each", "32000.00"),
    ("ELE-002", "Industrial sensor", "electronics", "each", "1850.50"),
    ("PKG-001", "Corrugated box (50 pack)", "packaging", "pack", "950.00"),
    ("OFF-001", "A4 paper (ream)", "office-supplies", "ream", "320.00"),
    ("CHM-001", "Industrial solvent 20L", "chemicals", "drum", "4100.00"),
    ("LOG-001", "Pallet wrap roll", "packaging", "roll", "275.00"),
]
DEPARTMENTS = ["Engineering", "Operations", "IT", "Finance", "HR", "Maintenance"]


def main() -> None:
    random.seed(42)
    with SessionLocal() as db:
        if db.scalar(select(func.count(Supplier.id))):
            print("Database already contains data - skipping seed.")
            return

        suppliers = [
            SupplierService(db).create(SupplierCreate(name=n, category=c, email=e))
            for n, c, e in SUPPLIERS
        ]
        materials = [
            MaterialService(db).create(
                MaterialCreate(sku=s, name=n, category=c, unit=u, unit_price=p)
            )
            for s, n, c, u, p in MATERIALS
        ]
        requisitions, orders, deliveries = RequisitionService(db), PurchaseOrderService(db), DeliveryService(db)

        for _ in range(40):
            picked = random.sample(materials, k=random.randint(1, 3))
            requisition = requisitions.create(
                RequisitionCreate(
                    department=random.choice(DEPARTMENTS),
                    requested_by=random.choice(["A. Sharma", "R. Patil", "S. Iyer", "M. Khan"]),
                    justification="Routine replenishment",
                    items=[
                        RequisitionItemCreate(material_id=m.id, quantity=random.randint(2, 60))
                        for m in picked
                    ],
                )
            )
            requisitions.submit(requisition.id)
            if random.random() < 0.2:
                requisitions.reject(requisition.id, "Budget not available this quarter")
                continue
            requisitions.approve(requisition.id)
            if random.random() < 0.15:
                continue  # approved but not yet ordered

            order_date = date.today() - timedelta(days=random.randint(5, 180))
            category = picked[0].category
            supplier = next((s for s in suppliers if s.category == category), random.choice(suppliers))
            order = orders.create(
                PurchaseOrderCreate(
                    supplier_id=supplier.id,
                    requisition_id=requisition.id,
                    order_date=order_date,
                    expected_delivery_date=order_date + timedelta(days=14),
                )
            )
            orders.update_status(order.id, PurchaseOrderStatus.ISSUED)
            roll = random.random()
            if roll < 0.7:  # fully received
                lines = [DeliveryItemCreate(po_item_id=i.id, quantity_received=i.quantity) for i in order.items]
            elif roll < 0.85:  # partially received
                lines = [
                    DeliveryItemCreate(po_item_id=i.id, quantity_received=max(1, i.quantity // 2))
                    for i in order.items
                ]
            else:
                continue
            deliveries.record(order.id, DeliveryCreate(received_by="Stores", items=lines))

        rfqs = RfqService(db)
        for index, title in enumerate(["Bearings and sensors - annual contract", "Packaging materials Q1"]):
            rfq = rfqs.create(
                RfqCreate(
                    title=title,
                    items=[RfqItemCreate(material_id=m.id, quantity=random.randint(50, 200)) for m in materials[index * 2 : index * 2 + 2]],
                )
            )
            rfq = rfqs.publish(rfq.id)
            quotes = []
            for supplier in random.sample(suppliers, 3):
                factor = random.uniform(0.9, 1.15)
                quotes.append(
                    rfqs.submit_quotation(
                        rfq.id,
                        QuotationCreate(
                            supplier_id=supplier.id,
                            delivery_days=random.randint(5, 30),
                            items=[
                                QuotationItemCreate(
                                    rfq_item_id=item.id,
                                    unit_price=round(float(materials[index * 2 + n].unit_price) * factor, 2),
                                )
                                for n, item in enumerate(rfq.items)
                            ],
                        ),
                    )
                )
            if index == 0:  # award the first RFQ to the recommended quotation
                best = rfqs.compare(rfq.id)["recommended_quotation_id"]
                rfqs.award(rfq.id, best)

        print("Seeded demo data: suppliers, materials, requisitions, orders, deliveries and RFQs.")


if __name__ == "__main__":
    main()
