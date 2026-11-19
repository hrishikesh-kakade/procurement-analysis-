import pytest

from app.models.enums import UserRole as R
from tests.factories import (
    API,
    create_material,
    create_purchase_order,
    create_requisition,
    create_supplier,
)

ALL_ROLES = list(R)
SUPPLIER = {"name": "RBAC Supplier", "category": "tools", "email": "rbac@acme-corp.com"}


def _expect(role, allowed):
    return 201 if role in allowed else 403


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_read_suppliers_and_requisitions(make_client, role):
    c = make_client(role)
    assert c.get(f"{API}/suppliers").status_code == 200
    assert c.get(f"{API}/requisitions").status_code == 200
    assert c.get(f"{API}/purchase-orders").status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_supplier_writes_need_admin_or_manager(make_client, role):
    response = make_client(role).post(f"{API}/suppliers", json=SUPPLIER)
    assert response.status_code == _expect(role, {R.ADMIN, R.PROCUREMENT_MANAGER})
    if response.status_code == 403:
        assert response.json()["error"]["code"] == "forbidden"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_requisition_creation_permissions(client, make_client, role):
    material = create_material(client)
    body = {
        "department": "IT",
        "requested_by": "Someone",
        "items": [{"material_id": material["id"], "quantity": 1}],
    }
    response = make_client(role).post(f"{API}/requisitions", json=body)
    assert response.status_code == _expect(role, {R.ADMIN, R.PROCUREMENT_MANAGER, R.REQUESTER})


@pytest.mark.parametrize("role", ALL_ROLES)
def test_only_approvers_can_approve(client, make_client, role):
    requisition = create_requisition(client)
    client.post(f"{API}/requisitions/{requisition['id']}/submit")
    response = make_client(role).post(f"{API}/requisitions/{requisition['id']}/approve")
    allowed = {R.ADMIN, R.PROCUREMENT_MANAGER, R.APPROVER}
    assert response.status_code == (200 if role in allowed else 403)


@pytest.mark.parametrize("role", ALL_ROLES)
def test_purchase_order_creation_permissions(client, make_client, role):
    supplier, material = create_supplier(client), create_material(client)
    body = {"supplier_id": supplier["id"], "items": [{"material_id": material["id"], "quantity": 1}]}
    response = make_client(role).post(f"{API}/purchase-orders", json=body)
    assert response.status_code == _expect(role, {R.ADMIN, R.PROCUREMENT_MANAGER})


@pytest.mark.parametrize("role", ALL_ROLES)
def test_analytics_access(make_client, role):
    response = make_client(role).get(f"{API}/analytics/total-spend")
    assert response.status_code == (403 if role == R.REQUESTER else 200)


@pytest.mark.parametrize("role", [r for r in ALL_ROLES if r != R.ADMIN])
def test_user_management_is_admin_only(make_client, role):
    c = make_client(role)
    assert c.get(f"{API}/users").status_code == 403
    assert c.post(
        f"{API}/users",
        json={"email": "x@acme-corp.com", "full_name": "X Y", "password": "Passw0rd!"},
    ).status_code == 403


def test_admin_creates_and_lists_users(client):
    created = client.post(
        f"{API}/users",
        json={"email": "New.User@Acme-Corp.com", "full_name": "New User", "password": "Passw0rd!", "role": "approver"},
    )
    assert created.status_code == 201
    assert created.json()["email"] == "new.user@acme-corp.com"
    assert created.json()["role"] == "approver"
    assert "password" not in str(created.json()).lower()
    approvers = client.get(f"{API}/users", params={"role": "approver"}).json()
    assert approvers["total"] == 1


def test_user_creation_validation(client):
    base = {"email": "u@acme-corp.com", "full_name": "U Ser", "password": "Passw0rd!"}
    assert client.post(f"{API}/users", json=base).status_code == 201
    assert client.post(f"{API}/users", json=base).status_code == 409  # duplicate e-mail
    weak = {**base, "email": "w@acme-corp.com", "password": "short1"}
    assert client.post(f"{API}/users", json=weak).status_code == 422
    no_digit = {**base, "email": "n@acme-corp.com", "password": "onlyletters"}
    assert client.post(f"{API}/users", json=no_digit).status_code == 422
    bad_role = {**base, "email": "r@acme-corp.com", "role": "superuser"}
    assert client.post(f"{API}/users", json=bad_role).status_code == 422


def test_role_changes_take_effect_immediately(client, make_client):
    viewer = make_client(R.VIEWER, "promote@acme-corp.com")
    assert viewer.post(f"{API}/suppliers", json=SUPPLIER).status_code == 403
    promoted = client.patch(f"{API}/users/{viewer.user_id}", json={"role": "procurement_manager"})
    assert promoted.status_code == 200
    assert viewer.post(f"{API}/suppliers", json=SUPPLIER).status_code == 201  # same token


def test_deactivated_user_loses_access_immediately(client, make_client):
    user = make_client(R.VIEWER, "leaver@acme-corp.com")
    assert user.get(f"{API}/suppliers").status_code == 200
    assert client.patch(f"{API}/users/{user.user_id}", json={"is_active": False}).status_code == 200
    assert user.get(f"{API}/suppliers").status_code == 401


def test_admin_cannot_demote_or_deactivate_self(client):
    assert client.patch(f"{API}/users/{client.user_id}", json={"role": "viewer"}).status_code == 422
    assert client.patch(f"{API}/users/{client.user_id}", json={"is_active": False}).status_code == 422
    assert client.patch(f"{API}/users/{client.user_id}", json={"full_name": "Renamed Root"}).status_code == 200


def test_unknown_user_is_404(client):
    assert client.get(f"{API}/users/9999").status_code == 404


def test_create_helpers_still_work_with_manager_token(make_client):
    manager = make_client(R.PROCUREMENT_MANAGER)
    supplier, material = create_supplier(manager), create_material(manager)
    assert create_purchase_order(
        manager, supplier["id"], items=[{"material_id": material["id"], "quantity": 2}]
    )["status"] == "draft"
