"""Account registration and password verification."""
from __future__ import annotations

import time

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from redis.asyncio import Redis


class AccountAlreadyExists(Exception):
    """Raised when a username is already registered."""


class AccountService:
    """Stores account records in Redis and hashes passwords with Argon2id."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis
        self.password_hasher = PasswordHasher()

    @staticmethod
    def _account_key(username: str) -> str:
        return f"account:{username.strip().lower()}"

    async def register(self, username: str, password: str) -> dict:
        username = username.strip().lower()
        key = self._account_key(username)
        password_hash = self.password_hasher.hash(password)
        created_at = int(time.time())

        # HSETNX makes username reservation atomic if registrations race.
        pipeline = self.redis.pipeline(transaction=True)
        pipeline.hsetnx(key, "password_hash", password_hash)
        pipeline.hset(
            key,
            mapping={
                "username": username,
                "created_at": str(created_at),
            },
        )
        result = await pipeline.execute()
        if not result[0]:
            raise AccountAlreadyExists(username)

        return {"username": username, "created_at": created_at}

    async def authenticate(self, username: str, password: str) -> dict | None:
        username = username.strip().lower()
        account = await self.redis.hgetall(self._account_key(username))
        password_hash = account.get("password_hash")
        if not password_hash:
            return None

        try:
            valid = self.password_hasher.verify(password_hash, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return None

        if not valid:
            return None
        return {
            "username": account["username"],
            "created_at": int(account["created_at"]),
        }
