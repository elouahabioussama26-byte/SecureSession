"""Create 20 fictitious sessions for the university project demonstration."""
import asyncio

from redis.asyncio import Redis

from app.config import settings
from app.session_service import SessionService


async def main() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        service = SessionService(redis, settings.session_ttl_seconds)
        username = "demo_user"

        # Remove older demo sessions so each run produces exactly 20 active ones.
        old_sessions = await service.list_user_sessions(username)
        for session in old_sessions:
            await service.revoke_session(username, session["session_id"])

        browsers = [
            "Firefox on Ubuntu",
            "Chrome on Ubuntu",
            "Firefox on Android",
            "Chrome on Android",
            "Safari on iOS",
        ]
        for number in range(20):
            await service.create_session(
                username,
                client_ip=f"192.0.2.{number + 1}",
                user_agent=browsers[number % len(browsers)],
            )

        sessions = await service.list_user_sessions(username)
        print(f"Created {len(sessions)} fictitious active sessions for '{username}'.")
        print("Open the web app and log in using the username: demo_user")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
