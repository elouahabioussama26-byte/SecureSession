import fakeredis.aioredis
import httpx
import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_session_api_login_list_revoke_and_logout():
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    application = create_app(redis_client=redis)

    try:
        async with application.router.lifespan_context(application):
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                unauthenticated = await client.get("/api/sessions")
                assert unauthenticated.status_code == 401

                first_login = await client.post(
                    "/api/sessions",
                    json={"username": "oussama"},
                )
                assert first_login.status_code == 201
                assert "httponly" in first_login.headers.get("set-cookie", "").lower()
                first_session_id = first_login.json()["session"]["session_id"]

                current = await client.get("/api/sessions/me")
                assert current.status_code == 200

                second_login = await client.post(
                    "/api/sessions",
                    json={"username": "oussama"},
                )
                assert second_login.status_code == 201

                listing = await client.get("/api/sessions")
                assert listing.status_code == 200
                assert listing.json()["total"] == 2

                revoke = await client.delete(
                    f"/api/sessions/{first_session_id}"
                )
                assert revoke.status_code == 204

                listing_after_revoke = await client.get("/api/sessions")
                assert listing_after_revoke.json()["total"] == 1

                logout = await client.delete("/api/sessions/me")
                assert logout.status_code == 204

                invalid_after_logout = await client.get("/api/sessions/me")
                assert invalid_after_logout.status_code == 401
    finally:
        await redis.aclose()
