from datetime import timedelta

import jwt

from app.core.security import create_access_token
from app.models.enums import UserRole


def test_health_is_public(anonymous_client):
    response = anonymous_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_token_is_rejected(anonymous_client):
    response = anonymous_client.get("/api/v1/suppliers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_garbage_token_is_rejected(anonymous_client):
    response = anonymous_client.get("/api/v1/suppliers", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_expired_token_is_rejected(anonymous_client, make_client):
    user_id = make_client(UserRole.ADMIN).user_id
    token = create_access_token(user_id, "admin", timedelta(seconds=-5))
    response = anonymous_client.get("/api/v1/suppliers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_token_signed_with_another_key_is_rejected(anonymous_client, make_client):
    user_id = make_client(UserRole.ADMIN).user_id
    forged = jwt.encode(
        {"sub": str(user_id), "exp": 4102444800}, "a-different-secret-key-0123456789abcdef", "HS256"
    )
    response = anonymous_client.get("/api/v1/suppliers", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_token_of_inactive_user_is_rejected(make_client):
    inactive = make_client(UserRole.ADMIN, "gone@acme-corp.com", active=False)
    assert inactive.get("/api/v1/suppliers").status_code == 401


def test_valid_token_is_accepted(client):
    assert client.get("/api/v1/suppliers").status_code == 200


def test_unknown_route_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "error" in response.json()
