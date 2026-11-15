"""Inspect SecureSession Redis keys without printing password hashes or token digests."""
import asyncio

from redis.asyncio import Redis

from app.config import settings


async def main() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.ping()
        print("SecureSession Redis data overview")

        print("\nAccounts:")
        async for key in redis.scan_iter(match="account:*", count=100):
            account = await redis.hgetall(key)
            print(
                f"{key}: username={account.get('username', '?')} "
                f"| created_at={account.get('created_at', '?')} "
                "| password_hash=(stored, hidden)"
            )

        print("\nSessions:")
        async for key in redis.scan_iter(match="session:*", count=100):
            if key.startswith("session-id:"):
                continue
            data = await redis.hgetall(key)
            ttl = await redis.ttl(key)
            print(
                f"Hash {key[:18]}… | user={data.get('username', '?')} "
                f"| session_id={data.get('session_id', '?')} | TTL={ttl}s"
            )

        print("\nConnected users Set:")
        users = sorted(await redis.smembers("secure_session:connected_users"))
        print(users or "(empty)")

        print("\nUser session Sorted Sets:")
        async for key in redis.scan_iter(match="user:*:sessions"):
            members = await redis.zrange(key, 0, -1, withscores=True)
            print(f"{key}: {len(members)} indexed session(s)")
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
