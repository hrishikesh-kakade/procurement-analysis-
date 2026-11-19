import pytest

from tests.factories import (
    API,
    approved_requisition,
    create_material,
    create_purchase_order,
    create_requisition,
    create_supplier,
    set_po_status,
)


@pytest.fixture
def seeded(client):
    """Two committed orders (Jan: 1000, Feb: 500), one draft and a mix of requisition outcomes."""
    supplier_a = create_supplier(client, name="Supplier A")
    supplier_b = create_supplier(client, name="Supplier B")
    material = create_material(client)

    requisition = approved_requisition(
        client,
        department="Engineering",
        items=[{"material_id": material["id"], "quantity": 10, "estimated_unit_price": "100.00"}],
    )
    po1 = create_purchase_order(
        client, supplier_a["id"], requisition_id=requisition["id"], order_date="2026-01-15"
    )
    set_po_status(client, po1["id"], "issued")
    client.post(
        f"{API}/purchase-orders/{po1['id']}/deliveries",
        json={"items": [{"po_item_id": po1["items"][0]["id"], "quantity_received": 10}]},
    )

    po2 = create_purchase_order(
        client,
        supplier_b["id"],
        items=[{"material_id": material["id"], "quantity": 2, "unit_price": "250.00"}],
        order_date="2026-02-10",
    )
    set_po_status(client, po2["id"], "issued")

    create_purchase_order(  # draft -> excluded from spend
        client,
        supplier_a["id"],
        items=[{"material_id": material["id"], "quantity": 1, "unit_price": "300.00"}],
        order_date="2026-02-20",
    )

    rejected = create_requisition(client, department="IT")
    client.post(f"{API}/requisitions/{rejected['id']}/submit")
    client.post(f"{API}/requisitions/{rejected['id']}/reject", json={"reason": "Not needed"})
    pending = create_requisition(client, department="HR")
    client.post(f"{API}/requisitions/{pending['id']}/submit")
    return {"supplier_a": supplier_a, "supplier_b": supplier_b}


def test_total_spend_excludes_drafts(client, seeded):
    body = client.get(f"{API}/analytics/total-spend").json()
    assert body["total_spend"] == pytest.approx(1500.0)
    assert body["order_count"] == 2


def test_average_po(client, seeded):
    assert client.get(f"{API}/analytics/average-po").json()["average_po_value"] == pytest.approx(750.0)


def test_rejection_rate_counts_decided_requisitions_only(client, seeded):
    body = client.get(f"{API}/analytics/rejection-rate").json()
    assert body["decided_count"] == 2  # converted + rejected (the pending one is excluded)
    assert body["rejected_count"] == 1
    assert body["rejection_rate_percent"] == pytest.approx(50.0)


def test_monthly_spend(client, seeded):
    rows = client.get(f"{API}/analytics/monthly-spend").json()
    assert [(r["month"], r["total_spend"]) for r in rows] == [("2026-01", 1000.0), ("2026-02", 500.0)]


def test_department_spend_groups_unassigned_orders(client, seeded):
    rows = {r["department"]: r["total_spend"] for r in client.get(f"{API}/analytics/department-spend").json()}
    assert rows == {"Engineering": 1000.0, "Unassigned": 500.0}


def test_supplier_performance(client, seeded):
    rows = client.get(f"{API}/analytics/suppliers").json()
    by_id = {r["supplier_id"]: r for r in rows}
    a, b = by_id[seeded["supplier_a"]["id"]], by_id[seeded["supplier_b"]["id"]]
    assert rows[0]["supplier_id"] == a["supplier_id"]  # sorted by spend, descending
    assert a["total_spend"] == pytest.approx(1000.0) and a["fulfillment_rate_percent"] == 100.0
    assert b["total_spend"] == pytest.approx(500.0) and b["fulfillment_rate_percent"] == 0.0


def test_date_range_filtering(client, seeded):
    body = client.get(f"{API}/analytics/total-spend", params={"date_from": "2026-02-01"}).json()
    assert body["total_spend"] == pytest.approx(500.0) and body["order_count"] == 1
    body = client.get(
        f"{API}/analytics/total-spend", params={"date_from": "2026-01-01", "date_to": "2026-01-31"}
    ).json()
    assert body["total_spend"] == pytest.approx(1000.0)
    empty = client.get(f"{API}/analytics/rejection-rate", params={"date_from": "2099-01-01"}).json()
    assert empty["decided_count"] == 0 and empty["rejection_rate_percent"] == 0.0


def test_invalid_date_range_is_rejected(client):
    response = client.get(
        f"{API}/analytics/total-spend", params={"date_from": "2026-03-01", "date_to": "2026-01-01"}
    )
    assert response.status_code == 422
    assert client.get(f"{API}/analytics/total-spend", params={"date_from": "garbage"}).status_code == 422


def test_analytics_on_empty_database(client):
    assert client.get(f"{API}/analytics/total-spend").json()["total_spend"] == 0
    assert client.get(f"{API}/analytics/average-po").json()["average_po_value"] == 0
    assert client.get(f"{API}/analytics/monthly-spend").json() == []
    assert client.get(f"{API}/analytics/suppliers").json() == []
