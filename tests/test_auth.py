import jwt

from app.core.config import get_settings
from app.models.enums import UserRole
from tests.conftest import PASSWORD

API = "/api/v1"


def _login(client, email, password=PASSWORD):
    return client.post(f"{API}/auth/login", data={"username": email, "password": password})


def test_login_returns_a_usable_jwt(anonymous_client, make_client):
    make_client(UserRole.PROCUREMENT_MANAGER, "manager@acme-corp.com")
    response = _login(anonymous_client, "manager@acme-corp.com")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0

    claims = jwt.decode(body["access_token"], get_settings().secret_key, algorithms=["HS256"])
    assert claims["role"] == "procurement_manager" and "exp" in claims

    me = anonymous_client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "manager@acme-corp.com"
    assert me.json()["last_login_at"] is not None


def test_login_email_is_case_insensitive(anonymous_client, make_client):
    make_client(UserRole.VIEWER, "viewer@acme-corp.com")
    assert _login(anonymous_client, "VIEWER@Acme-Corp.com").status_code == 200


def test_wrong_password_and_unknown_user_look_identical(anonymous_client, make_client):
    make_client(UserRole.VIEWER, "viewer@acme-corp.com")
    wrong = _login(anonymous_client, "viewer@acme-corp.com", "Wrong-pass-1")
    unknown = _login(anonymous_client, "nobody@acme-corp.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_inactive_user_cannot_log_in(anonymous_client, make_client):
    make_client(UserRole.VIEWER, "off@acme-corp.com", active=False)
    assert _login(anonymous_client, "off@acme-corp.com").status_code == 401


def test_passwords_are_never_returned(client):
    body = client.get(f"{API}/auth/me").json()
    assert "password" not in str(body).lower()


def test_change_password_flow(anonymous_client, make_client):
    user = make_client(UserRole.VIEWER, "viewer@acme-corp.com")
    new_password = "Brand-new-pass-9"

    wrong_current = user.post(
        f"{API}/auth/change-password", json={"current_password": "nope", "new_password": new_password}
    )
    assert wrong_current.status_code == 422

    weak = user.post(
        f"{API}/auth/change-password", json={"current_password": PASSWORD, "new_password": "onlyletters"}
    )
    assert weak.status_code == 422

    ok = user.post(
        f"{API}/auth/change-password", json={"current_password": PASSWORD, "new_password": new_password}
    )
    assert ok.status_code == 204
    assert _login(anonymous_client, "viewer@acme-corp.com", PASSWORD).status_code == 401
    assert _login(anonymous_client, "viewer@acme-corp.com", new_password).status_code == 200
