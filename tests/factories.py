"""Small helpers that create records through the public API."""

import itertools

_counter = itertools.count(1)
API = "/api/v1"


def create_supplier(client, **overrides) -> dict:
    n = next(_counter)
    payload = {
        "name": f"Supplier {n}",
        "category": "electronics",
        "email": f"supplier{n}@acme-corp.com",
        **overrides,
    }
    response = client.post(f"{API}/suppliers", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_material(client, unit_price="100.00", **overrides) -> dict:
    n = next(_counter)
    payload = {
        "sku": f"SKU-{n:04d}",
        "name": f"Material {n}",
        "category": "general",
        "unit_price": unit_price,
        **overrides,
    }
    response = client.post(f"{API}/materials", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_requisition(client, items=None, department="Engineering") -> dict:
    if items is None:
        items = [{"material_id": create_material(client)["id"], "quantity": 5}]
    response = client.post(
        f"{API}/requisitions",
        json={"department": department, "requested_by": "Test User", "items": items},
    )
    assert response.status_code == 201, response.text
    return response.json()


def approved_requisition(client, **kwargs) -> dict:
    requisition = create_requisition(client, **kwargs)
    assert client.post(f"{API}/requisitions/{requisition['id']}/submit").status_code == 200
    response = client.post(f"{API}/requisitions/{requisition['id']}/approve")
    assert response.status_code == 200, response.text
    return response.json()


def create_purchase_order(client, supplier_id, items=None, **overrides) -> dict:
    payload = {"supplier_id": supplier_id, **overrides}
    if items is not None:
        payload["items"] = items
    response = client.post(f"{API}/purchase-orders", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def set_po_status(client, po_id, status):
    return client.patch(f"{API}/purchase-orders/{po_id}/status", json={"status": status})
