import asyncio
import hashlib

import fakeredis.aioredis
import pytest

from app.session_service import SessionService


@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
def service(redis_client):
    return SessionService(redis_client, ttl_seconds=120)


@pytest.mark.asyncio
async def test_create_session_stores_hash_and_returns_safe_metadata(service, redis_client):
    token, session = await service.create_session("Oussama", "127.0.0.1", "pytest")

    digest = hashlib.sha256(token.encode()).hexdigest()
    stored = await redis_client.hgetall(f"session:{digest}")

    assert stored["username"] == "oussama"
    assert session["user_id"] == "oussama"
    assert session["session_id"] == stored["session_id"]
    assert token not in str(stored)
    assert 0 < session["ttl_seconds"] <= 120


@pytest.mark.asyncio
async def test_session_can_be_validated_and_listed(service):
    token, created = await service.create_session("oussama")

    validated = await service.get_session(token)
    sessions = await service.list_user_sessions("oussama")

    assert validated is not None
    assert validated["session_id"] == created["session_id"]
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == created["session_id"]


@pytest.mark.asyncio
async def test_revocation_invalidates_token_and_removes_user_index(service):
    token, created = await service.create_session("oussama")

    revoked = await service.revoke_session("oussama", created["session_id"])

    assert revoked is True
    assert await service.get_session(token) is None
    assert await service.list_user_sessions("oussama") == []


@pytest.mark.asyncio
async def test_user_cannot_revoke_another_users_session(service):
    _, created = await service.create_session("oussama")

    revoked = await service.revoke_session("another-user", created["session_id"])

    assert revoked is False
    assert len(await service.list_user_sessions("oussama")) == 1


@pytest.mark.asyncio
async def test_redis_ttl_expires_a_session(service, redis_client):
    token, _ = await service.create_session("oussama")
    digest = hashlib.sha256(token.encode()).hexdigest()
    await redis_client.expire(f"session:{digest}", 1)

    await asyncio.sleep(1.1)

    assert await service.get_session(token) is None
    assert await service.list_user_sessions("oussama") == []


@pytest.mark.asyncio
async def test_can_manage_twenty_simultaneous_sessions(service):
    for number in range(20):
        await service.create_session(
            "demo_user",
            client_ip="127.0.0.1",
            user_agent=f"Demo browser {number + 1}",
        )

    sessions = await service.list_user_sessions("demo_user")

    assert len(sessions) == 20
