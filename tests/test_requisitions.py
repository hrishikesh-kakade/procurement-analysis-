from tests.factories import API, approved_requisition, create_material, create_requisition


def test_create_requisition_defaults_price_from_material(client):
    material = create_material(client, unit_price="40.00")
    requisition = create_requisition(client, items=[{"material_id": material["id"], "quantity": 3}])
    assert requisition["status"] == "draft"
    assert requisition["requisition_number"].startswith("REQ-")
    assert requisition["items"][0]["estimated_unit_price"] == 40.0
    assert requisition["total_estimated_amount"] == 120.0


def test_quantity_must_be_greater_than_zero(client):
    material = create_material(client)
    response = client.post(
        f"{API}/requisitions",
        json={
            "department": "IT",
            "requested_by": "Test User",
            "items": [{"material_id": material["id"], "quantity": 0}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_requisition_needs_at_least_one_item(client):
    response = client.post(
        f"{API}/requisitions", json={"department": "IT", "requested_by": "Test User", "items": []}
    )
    assert response.status_code == 422


def test_unknown_material_is_404(client):
    response = client.post(
        f"{API}/requisitions",
        json={
            "department": "IT",
            "requested_by": "Test User",
            "items": [{"material_id": 9999, "quantity": 1}],
        },
    )
    assert response.status_code == 404


def test_full_approval_flow(client):
    requisition = create_requisition(client)
    rid = requisition["id"]
    submitted = client.post(f"{API}/requisitions/{rid}/submit").json()
    assert submitted["status"] == "submitted" and submitted["submitted_at"]
    approved = client.post(f"{API}/requisitions/{rid}/approve").json()
    assert approved["status"] == "approved" and approved["decided_at"]


def test_cannot_approve_unsubmitted_requisition(client):
    rid = create_requisition(client)["id"]
    response = client.post(f"{API}/requisitions/{rid}/approve")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


def test_cannot_approve_an_already_rejected_requisition(client):
    rid = create_requisition(client)["id"]
    client.post(f"{API}/requisitions/{rid}/submit")
    rejected = client.post(f"{API}/requisitions/{rid}/reject", json={"reason": "Over budget"})
    assert rejected.status_code == 200
    assert rejected.json()["rejection_reason"] == "Over budget"
    response = client.post(f"{API}/requisitions/{rid}/approve")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_status_transition"


def test_cannot_reject_an_approved_requisition(client):
    rid = approved_requisition(client)["id"]
    response = client.post(f"{API}/requisitions/{rid}/reject", json={"reason": "Changed my mind"})
    assert response.status_code == 409


def test_reject_requires_a_reason(client):
    rid = create_requisition(client)["id"]
    client.post(f"{API}/requisitions/{rid}/submit")
    assert client.post(f"{API}/requisitions/{rid}/reject", json={}).status_code == 422


def test_cannot_submit_twice(client):
    rid = create_requisition(client)["id"]
    assert client.post(f"{API}/requisitions/{rid}/submit").status_code == 200
    assert client.post(f"{API}/requisitions/{rid}/submit").status_code == 409


def test_cannot_submit_without_items(client):
    requisition = create_requisition(client)
    item_id = requisition["items"][0]["id"]
    removed = client.delete(f"{API}/requisitions/{requisition['id']}/items/{item_id}")
    assert removed.status_code == 200 and removed.json()["items"] == []
    response = client.post(f"{API}/requisitions/{requisition['id']}/submit")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "business_rule_violation"


def test_submitted_requisition_cannot_be_modified(client):
    rid = create_requisition(client)["id"]
    client.post(f"{API}/requisitions/{rid}/submit")
    assert client.patch(f"{API}/requisitions/{rid}", json={"department": "Finance"}).status_code == 409
    assert client.delete(f"{API}/requisitions/{rid}").status_code == 409


def test_add_item_and_reject_duplicate_material(client):
    requisition = create_requisition(client)
    other = create_material(client, unit_price="10.00")
    added = client.post(
        f"{API}/requisitions/{requisition['id']}/items", json={"material_id": other["id"], "quantity": 2}
    )
    assert added.status_code == 201
    assert len(added.json()["items"]) == 2
    duplicate = client.post(
        f"{API}/requisitions/{requisition['id']}/items", json={"material_id": other["id"], "quantity": 1}
    )
    assert duplicate.status_code == 409


def test_put_replaces_items_and_patch_updates_header(client):
    requisition = create_requisition(client)
    material = create_material(client, unit_price="25.00")
    replaced = client.put(
        f"{API}/requisitions/{requisition['id']}",
        json={
            "department": "Finance",
            "requested_by": "New User",
            "items": [{"material_id": material["id"], "quantity": 4}],
        },
    )
    assert replaced.status_code == 200
    assert replaced.json()["total_estimated_amount"] == 100.0
    patched = client.patch(f"{API}/requisitions/{requisition['id']}", json={"requested_by": "Other User"})
    assert patched.json()["requested_by"] == "Other User"


def test_list_filters_by_status_and_department(client):
    create_requisition(client, department="IT")
    approved_requisition(client, department="Finance")
    assert client.get(f"{API}/requisitions", params={"status": "approved"}).json()["total"] == 1
    assert client.get(f"{API}/requisitions", params={"department": "it"}).json()["total"] == 1


def test_delete_draft(client):
    rid = create_requisition(client)["id"]
    assert client.delete(f"{API}/requisitions/{rid}").status_code == 204
    assert client.get(f"{API}/requisitions/{rid}").status_code == 404
