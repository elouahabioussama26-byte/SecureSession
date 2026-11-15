"""Business logic for secure Redis-backed user sessions."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from typing import Any
from uuid import uuid4

from redis.asyncio import Redis


SESSION_EVENTS_CHANNEL = "secure_session:events"
CONNECTED_USERS_KEY = "secure_session:connected_users"


class SessionService:
    """Create, validate, list and revoke sessions stored in Redis.

    The browser receives a random opaque token. Redis stores only its SHA-256
    digest, so a Redis data dump does not reveal reusable session credentials.
    """

    def __init__(self, redis: Redis, ttl_seconds: int = 3600) -> None:
        self.redis = redis
        self.ttl_seconds = max(60, int(ttl_seconds))

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _session_key(token_digest: str) -> str:
        return f"session:{token_digest}"

    @staticmethod
    def _session_id_key(session_id: str) -> str:
        return f"session-id:{session_id}"

    @staticmethod
    def _user_sessions_key(user_id: str) -> str:
        return f"user:{user_id}:sessions"

    async def _publish(self, event_type: str, session: dict[str, Any]) -> None:
        event = {
            "type": event_type,
            "user_id": session.get("user_id"),
            "session_id": session.get("session_id"),
            "timestamp": int(time.time()),
        }
        await self.redis.publish(SESSION_EVENTS_CHANNEL, json.dumps(event))

    async def create_session(
        self,
        username: str,
        client_ip: str = "unknown",
        user_agent: str = "",
    ) -> tuple[str, dict[str, Any]]:
        """Create a session and return its raw token once plus safe metadata."""
        normalized_username = username.strip().lower()
        user_id = normalized_username
        token = secrets.token_urlsafe(32)
        token_digest = self._token_digest(token)
        session_id = str(uuid4())
        now = int(time.time())
        expires_at = now + self.ttl_seconds

        data = {
            "session_id": session_id,
            "user_id": user_id,
            "username": normalized_username,
            "created_at": str(now),
            "expires_at": str(expires_at),
            "client_ip": client_ip[:64],
            "user_agent": user_agent[:250],
        }

        user_index = self._user_sessions_key(user_id)
        pipeline = self.redis.pipeline(transaction=True)
        pipeline.hset(self._session_key(token_digest), mapping=data)
        pipeline.expire(self._session_key(token_digest), self.ttl_seconds)
        pipeline.set(self._session_id_key(session_id), token_digest, ex=self.ttl_seconds)
        pipeline.zadd(user_index, {session_id: expires_at})
        pipeline.expire(user_index, self.ttl_seconds + 60)
        pipeline.sadd(CONNECTED_USERS_KEY, user_id)
        await pipeline.execute()

        safe_session = self._to_summary(data, self.ttl_seconds)
        await self._publish("session.created", safe_session)
        return token, safe_session

    async def get_session(self, token: str | None) -> dict[str, Any] | None:
        """Validate a raw token against its digest-keyed Redis Hash."""
        if not token:
            return None

        token_digest = self._token_digest(token)
        key = self._session_key(token_digest)
        data = await self.redis.hgetall(key)
        if not data:
            return None

        remaining_ttl = await self.redis.ttl(key)
        if remaining_ttl <= 0:
            return None

        return self._to_summary(data, remaining_ttl)

    async def list_user_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Return active sessions and prune expired members from the Sorted Set."""
        user_index = self._user_sessions_key(user_id)
        now = int(time.time())

        expired_ids = await self.redis.zrangebyscore(user_index, "-inf", now)
        for session_id in expired_ids:
            digest = await self.redis.get(self._session_id_key(session_id))
            if digest:
                old_data = await self.redis.hgetall(self._session_key(digest))
                if old_data:
                    await self.redis.delete(self._session_key(digest))
            await self.redis.delete(self._session_id_key(session_id))
            await self.redis.zrem(user_index, session_id)
            await self._publish(
                "session.expired",
                {"user_id": user_id, "session_id": session_id},
            )

        active_ids = await self.redis.zrangebyscore(user_index, now + 1, "+inf")
        sessions: list[dict[str, Any]] = []

        for session_id in reversed(active_ids):
            digest = await self.redis.get(self._session_id_key(session_id))
            if not digest:
                await self.redis.zrem(user_index, session_id)
                continue

            data = await self.redis.hgetall(self._session_key(digest))
            if not data:
                await self.redis.delete(self._session_id_key(session_id))
                await self.redis.zrem(user_index, session_id)
                continue

            ttl = await self.redis.ttl(self._session_key(digest))
            if ttl <= 0:
                await self.redis.zrem(user_index, session_id)
                continue
            sessions.append(self._to_summary(data, ttl))

        if not sessions:
            await self.redis.srem(CONNECTED_USERS_KEY, user_id)
            await self.redis.delete(user_index)

        return sessions

    async def revoke_session(self, user_id: str, session_id: str) -> bool:
        """Revoke one of the specified user's sessions; other users are isolated."""
        id_key = self._session_id_key(session_id)
        digest = await self.redis.get(id_key)
        if not digest:
            await self.redis.zrem(self._user_sessions_key(user_id), session_id)
            return False

        session_key = self._session_key(digest)
        data = await self.redis.hgetall(session_key)
        if not data or data.get("user_id") != user_id:
            return False

        pipeline = self.redis.pipeline(transaction=True)
        pipeline.delete(session_key)
        pipeline.delete(id_key)
        pipeline.zrem(self._user_sessions_key(user_id), session_id)
        await pipeline.execute()

        if await self.redis.zcard(self._user_sessions_key(user_id)) == 0:
            await self.redis.srem(CONNECTED_USERS_KEY, user_id)

        await self._publish(
            "session.revoked",
            {"user_id": user_id, "session_id": session_id},
        )
        return True

    async def revoke_token(self, token: str | None) -> bool:
        """Revoke the session represented by a raw token."""
        session = await self.get_session(token)
        if not session:
            return False
        return await self.revoke_session(session["user_id"], session["session_id"])

    @staticmethod
    def _to_summary(data: dict[str, Any], ttl_seconds: int) -> dict[str, Any]:
        return {
            "session_id": data["session_id"],
            "user_id": data["user_id"],
            "username": data["username"],
            "created_at": int(data["created_at"]),
            "expires_at": int(data["expires_at"]),
            "ttl_seconds": max(0, int(ttl_seconds)),
            "client_ip": data.get("client_ip", "unknown"),
            "user_agent": data.get("user_agent", ""),
        }
