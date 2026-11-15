import fakeredis
import httpx
import pytest

from app.main import create_app


@pytest.mark.asyncio
async def test_registration_login_session_management_and_logout():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    application = create_app(redis_client=redis)

    try:
        async with application.router.lifespan_context(application):
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                # New users cannot access protected routes.
                unauthenticated = await client.get("/api/sessions")
                assert unauthenticated.status_code == 401

                # Registration creates an account and signs the user in.
                registration = await client.post(
                    "/api/accounts",
                    json={"username": "Oussama", "password": "SecurePass123!"},
                )
                assert registration.status_code == 201
                assert "httponly" in registration.headers.get("set-cookie", "").lower()
                account_hash = await redis.hgetall("account:oussama")
                assert account_hash["username"] == "oussama"
                assert account_hash["password_hash"] != "SecurePass123!"
                first_session_id = registration.json()["session"]["session_id"]

                # Duplicate usernames are not allowed.
                duplicate = await client.post(
                    "/api/accounts",
                    json={"username": "oussama", "password": "AnotherPass123!"},
                )
                assert duplicate.status_code == 409

                # Incorrect password is rejected.
                wrong_password = await client.post(
                    "/api/sessions",
                    json={"username": "oussama", "password": "WrongPass123!"},
                )
                assert wrong_password.status_code == 401

                current = await client.get("/api/sessions/me")
                assert current.status_code == 200

                # A second login creates another independent active session.
                login = await client.post(
                    "/api/sessions",
                    json={"username": "OUS SAMA".replace(" ", ""), "password": "SecurePass123!"},
                )
                assert login.status_code == 200

                listing = await client.get("/api/sessions")
                assert listing.status_code == 200
                assert listing.json()["total"] == 2

                revoke = await client.delete(f"/api/sessions/{first_session_id}")
                assert revoke.status_code == 204

                listing_after_revoke = await client.get("/api/sessions")
                assert listing_after_revoke.json()["total"] == 1

                logout = await client.delete("/api/sessions/me")
                assert logout.status_code == 204

                invalid_after_logout = await client.get("/api/sessions/me")
                assert invalid_after_logout.status_code == 401


@pytest.mark.asyncio
async def test_registration_validates_password_length():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    application = create_app(redis_client=redis)
    try:
        async with application.router.lifespan_context(application):
            transport = httpx.ASGITransport(app=application)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.post(
                    "/api/accounts",
                    json={"username": "oussama", "password": "short"},
                )
                assert response.status_code == 422
    finally:
        await redis.aclose()
