import fakeredis
import pytest

from app.auth_service import AccountAlreadyExists, AccountService


@pytest.mark.asyncio
async def test_register_stores_argon2_hash_and_authenticates():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    service = AccountService(redis)
    try:
        account = await service.register("Oussama", "SecurePass123!")
        stored = await redis.hgetall("account:oussama")

        assert account["username"] == "oussama"
        assert stored["password_hash"] != "SecurePass123!"
        assert stored["password_hash"].startswith("$argon2")
        assert (await service.authenticate("OUSSAMA", "SecurePass123!"))["username"] == "oussama"
        assert await service.authenticate("oussama", "not-the-password") is None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_duplicate_account_is_rejected():
    redis = fakeredis.FakeAsyncRedis(decode_responses=True)
    service = AccountService(redis)
    try:
        await service.register("oussama", "SecurePass123!")
        with pytest.raises(AccountAlreadyExists):
            await service.register("OUS SAMA".replace(" ", ""), "AnotherPass123!")
    finally:
        await redis.aclose()
