from tests.factories import API, create_supplier


def test_create_and_get_supplier(client):
    created = create_supplier(client, name="Acme Industrial", category="machinery")
    assert created["status"] == "active"
    fetched = client.get(f"{API}/suppliers/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Acme Industrial"


def test_duplicate_name_is_conflict(client):
    create_supplier(client, name="Acme Industrial")
    response = client.post(
        f"{API}/suppliers",
        json={"name": "acme industrial", "category": "x1", "email": "other@acme-corp.com"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_invalid_email_is_validation_error(client):
    response = client.post(
        f"{API}/suppliers", json={"name": "Valid Name", "category": "tools", "email": "not-an-email"}
    )
    assert response.status_code == 422
    body = response.json()["error"]
    assert body["code"] == "validation_error"
    assert any(d["field"] == "email" for d in body["details"])


def test_missing_supplier_is_404(client):
    response = client.get(f"{API}/suppliers/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_list_supports_search_filter_sort_and_pagination(client):
    create_supplier(client, name="Alpha Electronics", category="electronics")
    create_supplier(client, name="Beta Electronics", category="electronics")
    create_supplier(client, name="Gamma Packaging", category="packaging")

    page = client.get(f"{API}/suppliers", params={"page": 1, "limit": 2, "sort_by": "name", "order": "asc"})
    body = page.json()
    assert body["total"] == 3 and body["pages"] == 2
    assert [s["name"] for s in body["items"]] == ["Alpha Electronics", "Beta Electronics"]

    by_category = client.get(f"{API}/suppliers", params={"category": "ELECTRONICS"}).json()
    assert by_category["total"] == 2

    by_search = client.get(f"{API}/suppliers", params={"search": "gamma"}).json()
    assert [s["name"] for s in by_search["items"]] == ["Gamma Packaging"]


def test_invalid_pagination_is_rejected(client):
    assert client.get(f"{API}/suppliers", params={"limit": 1000}).status_code == 422
    assert client.get(f"{API}/suppliers", params={"page": 0}).status_code == 422


def test_filter_by_status(client):
    create_supplier(client)
    create_supplier(client, status="inactive")
    body = client.get(f"{API}/suppliers", params={"status": "inactive"}).json()
    assert body["total"] == 1


def test_put_replaces_supplier(client):
    supplier = create_supplier(client)
    response = client.put(
        f"{API}/suppliers/{supplier['id']}",
        json={"name": "Renamed Supplier", "category": "tools", "email": "renamed@acme-corp.com"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Supplier"
    assert response.json()["phone"] is None


def test_patch_updates_only_given_fields(client):
    supplier = create_supplier(client, category="electronics")
    response = client.patch(f"{API}/suppliers/{supplier['id']}", json={"status": "blacklisted"})
    assert response.status_code == 200
    assert response.json()["status"] == "blacklisted"
    assert response.json()["category"] == "electronics"


def test_delete_supplier(client):
    supplier = create_supplier(client)
    assert client.delete(f"{API}/suppliers/{supplier['id']}").status_code == 204
    assert client.get(f"{API}/suppliers/{supplier['id']}").status_code == 404
