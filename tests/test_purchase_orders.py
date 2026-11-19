from tests.factories import (
    API,
    approved_requisition,
    create_material,
    create_purchase_order,
    create_requisition,
    create_supplier,
    set_po_status,
)


def _order(client, supplier_id=None, quantity=4, unit_price="25.50"):
    supplier_id = supplier_id or create_supplier(client)["id"]
    material = create_material(client)
    return create_purchase_order(
        client,
        supplier_id,
        items=[{"material_id": material["id"], "quantity": quantity, "unit_price": unit_price}],
    )


def test_totals_are_calculated_by_the_backend(client):
    supplier = create_supplier(client)
    m1 = create_material(client, unit_price="10.00")
    order = create_purchase_order(
        client,
        supplier["id"],
        items=[
            {"material_id": m1["id"], "quantity": 3},  # defaults to catalogue price 10.00
        ],
    )
    assert order["status"] == "draft"
    assert order["po_number"].startswith("PO-")
    assert order["total_amount"] == 30.0
    assert order["items"][0]["line_total"] == 30.0


def test_order_total_sums_all_lines(client):
    supplier = create_supplier(client)
    m1, m2 = create_material(client), create_material(client)
    order = create_purchase_order(
        client,
        supplier["id"],
        items=[
            {"material_id": m1["id"], "quantity": 3, "unit_price": "19.99"},
            {"material_id": m2["id"], "quantity": 2, "unit_price": "100.00"},
        ],
    )
    assert order["total_amount"] == 259.97


def test_client_cannot_supply_total(client):
    supplier = create_supplier(client)
    material = create_material(client, unit_price="10.00")
    response = client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "total_amount": 1,
            "items": [{"material_id": material["id"], "quantity": 2}],
        },
    )
    assert response.status_code == 201
    assert response.json()["total_amount"] == 20.0


def test_order_for_nonexistent_supplier_is_404(client):
    material = create_material(client)
    response = client.post(
        f"{API}/purchase-orders",
        json={"supplier_id": 9999, "items": [{"material_id": material["id"], "quantity": 1}]},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_order_for_inactive_supplier_is_rejected(client):
    supplier = create_supplier(client, status="inactive")
    material = create_material(client)
    response = client.post(
        f"{API}/purchase-orders",
        json={"supplier_id": supplier["id"], "items": [{"material_id": material["id"], "quantity": 1}]},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "business_rule_violation"


def test_order_requires_items_or_requisition(client):
    supplier = create_supplier(client)
    assert client.post(f"{API}/purchase-orders", json={"supplier_id": supplier["id"]}).status_code == 422


def test_order_quantity_must_be_positive(client):
    supplier = create_supplier(client)
    material = create_material(client)
    response = client.post(
        f"{API}/purchase-orders",
        json={"supplier_id": supplier["id"], "items": [{"material_id": material["id"], "quantity": -1}]},
    )
    assert response.status_code == 422


def test_delivery_date_cannot_precede_order_date(client):
    supplier = create_supplier(client)
    material = create_material(client)
    response = client.post(
        f"{API}/purchase-orders",
        json={
            "supplier_id": supplier["id"],
            "order_date": "2026-03-10",
            "expected_delivery_date": "2026-03-01",
            "items": [{"material_id": material["id"], "quantity": 1}],
        },
    )
    assert response.status_code == 422


def test_convert_approved_requisition_into_order(client):
    supplier = create_supplier(client)
    material = create_material(client, unit_price="50.00")
    requisition = approved_requisition(
        client, items=[{"material_id": material["id"], "quantity": 6}]
    )
    order = create_purchase_order(client, supplier["id"], requisition_id=requisition["id"])
    assert order["requisition_id"] == requisition["id"]
    assert order["total_amount"] == 300.0
    converted = client.get(f"{API}/requisitions/{requisition['id']}").json()
    assert converted["status"] == "converted"


def test_unapproved_requisition_cannot_be_converted(client):
    supplier = create_supplier(client)
    requisition = create_requisition(client)
    response = client.post(
        f"{API}/purchase-orders",
        json={"supplier_id": supplier["id"], "requisition_id": requisition["id"]},
    )
    assert response.status_code == 409


def test_requisition_cannot_be_converted_twice(client):
    supplier = create_supplier(client)
    requisition = approved_requisition(client)
    create_purchase_order(client, supplier["id"], requisition_id=requisition["id"])
    response = client.post(
        f"{API}/purchase-orders",
        json={"supplier_id": supplier["id"], "requisition_id": requisition["id"]},
    )
    assert response.status_code == 409


def test_status_lifecycle_and_invalid_transitions(client):
    order = _order(client)
    po_id = order["id"]
    assert set_po_status(client, po_id, "issued").json()["status"] == "issued"
    cancelled = set_po_status(client, po_id, "cancelled")
    assert cancelled.json()["status"] == "cancelled"
    invalid = set_po_status(client, po_id, "issued")
    assert invalid.status_code == 409
    assert invalid.json()["error"]["code"] == "invalid_status_transition"


def test_receipt_statuses_cannot_be_set_manually(client):
    po_id = _order(client)["id"]
    set_po_status(client, po_id, "issued")
    assert set_po_status(client, po_id, "received").status_code == 422


def test_draft_order_cannot_receive_goods(client):
    order = _order(client)
    response = client.post(
        f"{API}/purchase-orders/{order['id']}/deliveries",
        json={"items": [{"po_item_id": order["items"][0]["id"], "quantity_received": 1}]},
    )
    assert response.status_code == 409


def test_partial_then_full_delivery(client):
    order = _order(client, quantity=10)
    po_id, item_id = order["id"], order["items"][0]["id"]
    set_po_status(client, po_id, "issued")

    first = client.post(
        f"{API}/purchase-orders/{po_id}/deliveries",
        json={"received_by": "Stores", "items": [{"po_item_id": item_id, "quantity_received": 4}]},
    )
    assert first.status_code == 201
    assert client.get(f"{API}/purchase-orders/{po_id}").json()["status"] == "partially_received"

    too_many = client.post(
        f"{API}/purchase-orders/{po_id}/deliveries",
        json={"items": [{"po_item_id": item_id, "quantity_received": 7}]},
    )
    assert too_many.status_code == 422

    second = client.post(
        f"{API}/purchase-orders/{po_id}/deliveries",
        json={"items": [{"po_item_id": item_id, "quantity_received": 6}]},
    )
    assert second.status_code == 201
    final = client.get(f"{API}/purchase-orders/{po_id}").json()
    assert final["status"] == "received"
    assert final["items"][0]["received_quantity"] == 10
    assert len(client.get(f"{API}/purchase-orders/{po_id}/deliveries").json()) == 2


def test_delivery_item_must_belong_to_order(client):
    first, second = _order(client), _order(client)
    set_po_status(client, first["id"], "issued")
    response = client.post(
        f"{API}/purchase-orders/{first['id']}/deliveries",
        json={"items": [{"po_item_id": second["items"][0]["id"], "quantity_received": 1}]},
    )
    assert response.status_code == 422


def test_list_orders_filters(client):
    supplier = create_supplier(client)
    _order(client, supplier_id=supplier["id"])
    issued = _order(client, supplier_id=supplier["id"])
    set_po_status(client, issued["id"], "issued")
    _order(client)
    assert client.get(f"{API}/purchase-orders", params={"supplier_id": supplier["id"]}).json()["total"] == 2
    assert client.get(f"{API}/purchase-orders", params={"status": "issued"}).json()["total"] == 1


def test_supplier_with_orders_cannot_be_deleted(client):
    supplier = create_supplier(client)
    _order(client, supplier_id=supplier["id"])
    response = client.delete(f"{API}/suppliers/{supplier['id']}")
    assert response.status_code == 409


def test_get_missing_order_is_404(client):
    assert client.get(f"{API}/purchase-orders/9999").status_code == 404
