import os

# Must be set before the application is imported. Tests never touch the real DATABASE_URL:
# they use TEST_DATABASE_URL (PostgreSQL in CI/Docker) or fall back to in-memory SQLite.
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "sqlite://")
os.environ["SECRET_KEY"] = "test-secret-key-for-the-test-suite-0123456789"
os.environ["ENVIRONMENT"] = "test"
os.environ.pop("ADMIN_EMAIL", None)
os.environ.pop("ADMIN_PASSWORD", None)
for _name in ("REDIS_URL", "QDRANT_URL", "ANTHROPIC_API_KEY"):
    os.environ.pop(_name, None)
os.environ["EMBEDDING_BACKEND"] = "hashing"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.services.rag.vector_store import get_vector_store  # noqa: E402

PASSWORD = "Passw0rd!"
_PASSWORD_HASH = hash_password(PASSWORD)  # hashed once: Argon2 is deliberately slow


@pytest.fixture(autouse=True)
def database():
    get_vector_store.cache_clear()  # fresh in-memory vector index per test
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def make_client():
    """Create a user with the given role and return a TestClient authenticated as that user."""

    def _make(role: UserRole = UserRole.ADMIN, email: str | None = None, active: bool = True):
        with SessionLocal() as db:
            user = User(
                email=email or f"{role.value}@acme-corp.com",
                full_name=f"Test {role.value}",
                hashed_password=_PASSWORD_HASH,
                role=role,
                is_active=active,
            )
            db.add(user)
            db.commit()
            user_id = user.id
        token = create_access_token(user_id, role)
        test_client = TestClient(app, headers={"Authorization": f"Bearer {token}"})
        test_client.user_id = user_id
        return test_client

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    """An authenticated admin - used by the CRUD/workflow tests."""
    return make_client(UserRole.ADMIN, "root@acme-corp.com")


@pytest.fixture
def anonymous_client() -> TestClient:
    return TestClient(app)
