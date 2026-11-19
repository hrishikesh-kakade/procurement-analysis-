import fakeredis
import pytest
import redis

from app.core.cache import Cache
from tests.factories import API, create_material, create_purchase_order, create_supplier, set_po_status


def test_get_or_set_caches_until_namespace_is_invalidated():
    cache = Cache(fakeredis.FakeRedis(decode_responses=True), ttl=60)
    calls = []

    def producer():
        calls.append(1)
        return {"value": len(calls)}

    assert cache.get_or_set("ns", {"a": 1}, producer) == {"value": 1}
    assert cache.get_or_set("ns", {"a": 1}, producer) == {"value": 1}  # served from cache
    assert len(calls) == 1
    assert cache.get_or_set("ns", {"a": 2}, producer) == {"value": 2}  # different parameters
    cache.invalidate("ns")
    assert cache.get_or_set("ns", {"a": 1}, producer) == {"value": 3}  # version bumped


def test_disabled_cache_always_calls_producer():
    cache = Cache(None)
    assert not cache.enabled
    assert [cache.get_or_set("ns", {}, lambda: 7) for _ in range(2)] == [7, 7]
    cache.invalidate("ns")  # no-op


class _BrokenRedis:
    def __getattr__(self, name):
        def fail(*args, **kwargs):
            raise redis.ConnectionError("redis is down")

        return fail


def test_cache_fails_open_when_redis_is_down():
    cache = Cache(_BrokenRedis())
    assert cache.get_or_set("ns", {}, lambda: "fresh") == "fresh"
    cache.invalidate("ns")  # must not raise


@pytest.fixture
def fake_cache(monkeypatch):
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    cache = Cache(fake_client, ttl=60)
    monkeypatch.setattr("app.core.cache.get_cache", lambda: cache)
    return fake_client


def test_analytics_endpoints_are_cached_and_invalidated_on_writes(client, fake_cache):
    supplier = create_supplier(client)
    material = create_material(client, unit_price="10.00")
    order = create_purchase_order(client, supplier["id"], items=[{"material_id": material["id"], "quantity": 5}])

    assert client.get(f"{API}/analytics/total-spend").json()["total_spend"] == 0
    assert fake_cache.keys("cache:analytics:*")  # the result was cached

    set_po_status(client, order["id"], "issued")  # a write invalidates the namespace
    assert client.get(f"{API}/analytics/total-spend").json()["total_spend"] == 50.0
