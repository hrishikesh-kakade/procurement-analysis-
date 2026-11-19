import pytest

from app.models.enums import UserRole as R
from tests.factories import API, approved_requisition, create_material, create_supplier


def _rfq(client, quantity=10, materials=1, **overrides):
    items = [
        {"material_id": create_material(client, unit_price="100.00")["id"], "quantity": quantity}
        for _ in range(materials)
    ]
    response = client.post(f"{API}/rfqs", json={"title": "Bearings RFQ", "items": items, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def _publish(client, rfq):
    response = client.post(f"{API}/rfqs/{rfq['id']}/publish")
    assert response.status_code == 200, response.text
    return response.json()


def _quote(client, rfq, supplier_id, price="90.00", days=10):
    return client.post(
        f"{API}/rfqs/{rfq['id']}/quotations",
        json={
            "supplier_id": supplier_id,
            "delivery_days": days,
            "items": [{"rfq_item_id": i["id"], "unit_price": price} for i in rfq["items"]],
        },
    )


def test_create_rfq_starts_as_draft(client):
    rfq = _rfq(client)
    assert rfq["status"] == "draft" and rfq["rfq_number"].startswith("RFQ-")


def test_rfq_from_approved_requisition_copies_items(client):
    material = create_material(client)
    requisition = approved_requisition(client, items=[{"material_id": material["id"], "quantity": 7}])
    response = client.post(f"{API}/rfqs", json={"title": "From requisition", "requisition_id": requisition["id"]})
    assert response.status_code == 201
    body = response.json()
    assert [(i["material_id"], i["quantity"]) for i in body["items"]] == [(material["id"], 7)]


def test_rfq_from_unapproved_requisition_is_conflict(client):
    from tests.factories import create_requisition

    requisition = create_requisition(client)
    response = client.post(f"{API}/rfqs", json={"title": "Too early", "requisition_id": requisition["id"]})
    assert response.status_code == 409


def test_rfq_validation(client):
    assert client.post(f"{API}/rfqs", json={"title": "No items"}).status_code == 422
    material = create_material(client)
    past = {"title": "Late", "due_date": "2020-01-01", "items": [{"material_id": material["id"], "quantity": 1}]}
    assert client.post(f"{API}/rfqs", json=past).status_code == 422


def test_quotation_requires_published_rfq(client):
    rfq = _rfq(client)
    supplier = create_supplier(client)
    assert _quote(client, rfq, supplier["id"]).status_code == 409


def test_publish_flow_and_invalid_transitions(client):
    rfq = _rfq(client)
    _publish(client, rfq)
    assert client.post(f"{API}/rfqs/{rfq['id']}/publish").status_code == 409
    assert client.post(f"{API}/rfqs/{rfq['id']}/cancel").status_code == 200
    assert client.post(f"{API}/rfqs/{rfq['id']}/publish").status_code == 409


def test_quotation_totals_and_rules(client):
    rfq = _rfq(client, quantity=10)
    _publish(client, rfq)
    supplier = create_supplier(client)
    created = _quote(client, rfq, supplier["id"], price="90.00")
    assert created.status_code == 201
    assert created.json()["total_amount"] == 900.0
    assert _quote(client, rfq, supplier["id"]).status_code == 409  # one quotation per supplier
    inactive = create_supplier(client, status="inactive")
    assert _quote(client, rfq, inactive["id"]).status_code == 422
    assert _quote(client, rfq, 9999).status_code == 404


def test_quotation_must_price_every_item(client):
    rfq = _rfq(client, materials=2)
    _publish(client, rfq)
    supplier = create_supplier(client)
    partial = client.post(
        f"{API}/rfqs/{rfq['id']}/quotations",
        json={
            "supplier_id": supplier["id"],
            "delivery_days": 5,
            "items": [{"rfq_item_id": rfq["items"][0]["id"], "unit_price": "10.00"}],
        },
    )
    assert partial.status_code == 422
    assert partial.json()["error"]["code"] == "business_rule_violation"


def _three_quotes(client):
    rfq = _publish(client, _rfq(client, quantity=10))
    a, b, c = (create_supplier(client) for _ in range(3))
    qa = _quote(client, rfq, a["id"], price="100.00", days=10).json()
    qb = _quote(client, rfq, b["id"], price="80.00", days=20).json()
    qc = _quote(client, rfq, c["id"], price="90.00", days=5).json()
    return rfq, (a, b, c), (qa, qb, qc)


def test_comparison_ranks_by_composite_score(client):
    rfq, _, (qa, qb, qc) = _three_quotes(client)
    body = client.get(f"{API}/rfqs/{rfq['id']}/comparison").json()
    assert body["recommended_quotation_id"] == qc["id"]
    assert [r["quotation_id"] for r in body["quotations"]] == [qc["id"], qb["id"], qa["id"]]
    assert [r["rank"] for r in body["quotations"]] == [1, 2, 3]
    assert body["quotations"][0]["composite_score"] == pytest.approx(81.94, abs=0.01)


def test_award_creates_purchase_order_and_updates_scorecard(client):
    rfq, (a, b, c), (qa, qb, qc) = _three_quotes(client)
    awarded = client.post(f"{API}/rfqs/{rfq['id']}/award", json={"quotation_id": qc["id"]})
    assert awarded.status_code == 200
    body = awarded.json()
    assert body["status"] == "awarded" and body["awarded_po_id"]

    order = client.get(f"{API}/purchase-orders/{body['awarded_po_id']}").json()
    assert order["supplier_id"] == c["id"] and order["status"] == "draft"
    assert order["total_amount"] == 900.0

    statuses = {q["supplier_id"]: q["status"] for q in client.get(f"{API}/rfqs/{rfq['id']}/quotations").json()}
    assert statuses == {a["id"]: "rejected", b["id"]: "rejected", c["id"]: "accepted"}

    card = {r["supplier_id"]: r for r in client.get(f"{API}/analytics/supplier-scorecard").json()}
    assert card[c["id"]]["quotation_win_rate_percent"] == 100.0
    assert card[a["id"]]["quotation_win_rate_percent"] == 0.0


def test_award_rules(client):
    rfq, _, (qa, _, qc) = _three_quotes(client)
    other_rfq = _publish(client, _rfq(client))
    foreign = _quote(client, other_rfq, create_supplier(client)["id"]).json()
    assert client.post(f"{API}/rfqs/{rfq['id']}/award", json={"quotation_id": foreign["id"]}).status_code == 404
    assert client.post(f"{API}/rfqs/{rfq['id']}/award", json={"quotation_id": qa["id"]}).status_code == 200
    assert client.post(f"{API}/rfqs/{rfq['id']}/award", json={"quotation_id": qc["id"]}).status_code == 409


def test_award_converts_the_source_requisition(client):
    material = create_material(client, unit_price="50.00")
    requisition = approved_requisition(client, items=[{"material_id": material["id"], "quantity": 4}])
    rfq = client.post(f"{API}/rfqs", json={"title": "Sourcing", "requisition_id": requisition["id"]}).json()
    _publish(client, rfq)
    quote = _quote(client, rfq, create_supplier(client)["id"], price="45.00").json()
    awarded = client.post(f"{API}/rfqs/{rfq['id']}/award", json={"quotation_id": quote["id"]}).json()
    assert client.get(f"{API}/requisitions/{requisition['id']}").json()["status"] == "converted"
    assert client.get(f"{API}/purchase-orders/{awarded['awarded_po_id']}").json()["requisition_id"] == requisition["id"]


def test_rfq_permissions(client, make_client):
    viewer = make_client(R.VIEWER)
    material = create_material(client)
    body = {"title": "Not allowed", "items": [{"material_id": material["id"], "quantity": 1}]}
    assert viewer.post(f"{API}/rfqs", json=body).status_code == 403
    assert viewer.get(f"{API}/rfqs").status_code == 200
