"""Create a demo account and 20 fictitious Redis-backed sessions."""
import asyncio

from redis.asyncio import Redis

from app.auth_service import AccountAlreadyExists, AccountService
from app.config import settings
from app.session_service import SessionService

DEMO_USERNAME = "demo_user"
DEMO_PASSWORD = "DemoPass123!"


async def main() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        accounts = AccountService(redis)
        try:
            await accounts.register(DEMO_USERNAME, DEMO_PASSWORD)
            print("Created the demo account.")
        except AccountAlreadyExists:
            print("The demo account already exists; keeping its current password.")

        service = SessionService(redis, settings.session_ttl_seconds)

        # Remove older demo sessions so each run produces exactly 20 active ones.
        old_sessions = await service.list_user_sessions(DEMO_USERNAME)
        for session in old_sessions:
            await service.revoke_session(DEMO_USERNAME, session["session_id"])

        browsers = [
            "Firefox on Ubuntu",
            "Chrome on Ubuntu",
            "Firefox on Android",
            "Chrome on Android",
            "Safari on iOS",
        ]
        for number in range(20):
            await service.create_session(
                DEMO_USERNAME,
                client_ip=f"192.0.2.{number + 1}",
                user_agent=browsers[number % len(browsers)],
            )

        sessions = await service.list_user_sessions(DEMO_USERNAME)
        print(f"Created {len(sessions)} fictitious active sessions for '{DEMO_USERNAME}'.")
        print(f"Dashboard login: {DEMO_USERNAME}")
        print(f"Demo password on first account creation: {DEMO_PASSWORD}")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
