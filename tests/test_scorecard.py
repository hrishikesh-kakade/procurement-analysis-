from tests.factories import API, create_material, create_purchase_order, create_supplier, set_po_status


def _delivered_order(client, supplier_id, received_date):
    material = create_material(client, unit_price="10.00")
    order = create_purchase_order(
        client,
        supplier_id,
        items=[{"material_id": material["id"], "quantity": 10}],
        order_date="2026-01-10",
        expected_delivery_date="2026-01-20",
    )
    set_po_status(client, order["id"], "issued")
    response = client.post(
        f"{API}/purchase-orders/{order['id']}/deliveries",
        json={"received_date": received_date, "items": [{"po_item_id": order["items"][0]["id"], "quantity_received": 10}]},
    )
    assert response.status_code == 201, response.text


def test_scorecard_scores_ratings_and_ordering(client):
    punctual = create_supplier(client, name="Punctual Ltd")
    late = create_supplier(client, name="Late Ltd")
    idle = create_supplier(client, name="Idle Ltd")
    _delivered_order(client, punctual["id"], "2026-01-15")
    _delivered_order(client, late["id"], "2026-02-01")

    rows = client.get(f"{API}/analytics/supplier-scorecard").json()
    by_id = {r["supplier_id"]: r for r in rows}

    good = by_id[punctual["id"]]
    assert good["fulfillment_rate_percent"] == 100.0
    assert good["on_time_delivery_rate_percent"] == 100.0
    assert good["quotation_win_rate_percent"] is None  # no RFQ history -> metric ignored
    assert good["score"] == 100.0 and good["rating"] == "A"

    slow = by_id[late["id"]]
    assert slow["on_time_delivery_rate_percent"] == 0.0
    assert slow["score"] == 50.0 and slow["rating"] == "C"

    assert by_id[idle["id"]]["score"] is None and by_id[idle["id"]]["rating"] is None
    assert [r["supplier_id"] for r in rows] == [punctual["id"], late["id"], idle["id"]]
