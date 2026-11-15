"""FastAPI application for the SecureSession university project."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.models import LoginRequest
from app.redis_client import get_redis
from app.session_service import SESSION_EVENTS_CHANNEL, SessionService

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"


def get_service(redis: Redis = Depends(get_redis)) -> SessionService:
    return SessionService(redis, settings.session_ttl_seconds)


async def require_session(
    request: Request,
    service: SessionService = Depends(get_service),
) -> dict:
    token = request.cookies.get(settings.session_cookie_name)
    session = await service.get_session(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid session is required. Please log in.",
        )
    return session


def create_app(redis_client: Redis | None = None) -> FastAPI:
    owns_redis_client = redis_client is None

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        client = redis_client or Redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        application.state.redis = client
        try:
            await client.ping()
        except RedisError as exc:
            if owns_redis_client:
                await client.aclose()
            raise RuntimeError(
                f"Cannot connect to Redis at {settings.redis_url}. "
                "Check that your Redis container is running."
            ) from exc
        yield
        if owns_redis_client:
            await client.aclose()

    application = FastAPI(
        title="SecureSession API",
        description="Centralized Redis-backed user session management.",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        return response

    @application.get("/", include_in_schema=False)
    async def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/api/health")
    async def health(redis: Redis = Depends(get_redis)):
        try:
            await redis.ping()
        except RedisError:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "unavailable", "redis": "disconnected"},
            )
        return {"status": "ok", "redis": "connected"}

    @application.post("/api/sessions", status_code=status.HTTP_201_CREATED)
    async def create_session(
        payload: LoginRequest,
        request: Request,
        response: Response,
        service: SessionService = Depends(get_service),
    ):
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        token, session = await service.create_session(
            payload.username,
            client_ip=client_ip,
            user_agent=user_agent,
        )
        response.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            path="/",
        )
        return {"message": "Session created", "session": session}

    @application.get("/api/sessions/me")
    async def current_session(session: dict = Depends(require_session)):
        return {"session": session}

    @application.get("/api/sessions")
    async def list_sessions(
        session: dict = Depends(require_session),
        service: SessionService = Depends(get_service),
    ):
        sessions = await service.list_user_sessions(session["user_id"])
        for item in sessions:
            item["is_current"] = item["session_id"] == session["session_id"]
        return {"total": len(sessions), "sessions": sessions}

    @application.delete("/api/sessions/me", status_code=status.HTTP_204_NO_CONTENT)
    async def logout(
        session: dict = Depends(require_session),
        service: SessionService = Depends(get_service),
    ):
        await service.revoke_session(session["user_id"], session["session_id"])
        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(
            key=settings.session_cookie_name,
            path="/",
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
        )
        return response

    @application.delete("/api/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def revoke_session(
        session_id: str,
        session: dict = Depends(require_session),
        service: SessionService = Depends(get_service),
    ):
        revoked = await service.revoke_session(session["user_id"], session_id)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or it does not belong to the current user.",
            )

        response = Response(status_code=status.HTTP_204_NO_CONTENT)
        if session_id == session["session_id"]:
            response.delete_cookie(
                key=settings.session_cookie_name,
                path="/",
                httponly=True,
                secure=settings.session_cookie_secure,
                samesite=settings.session_cookie_samesite,
            )
        return response

    @application.get("/api/events")
    async def session_events(
        request: Request,
        session: dict = Depends(require_session),
        redis: Redis = Depends(get_redis),
    ):
        async def event_generator() -> AsyncIterator[str]:
            pubsub = redis.pubsub()
            await pubsub.subscribe(SESSION_EVENTS_CHANNEL)
            try:
                yield "retry: 3000\n\n"
                while not await request.is_disconnected():
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message and message.get("data"):
                        try:
                            event = json.loads(message["data"])
                        except (TypeError, json.JSONDecodeError):
                            continue
                        if event.get("user_id") == session["user_id"]:
                            yield f"data: {json.dumps(event)}\n\n"
                    else:
                        yield ": keep-alive\n\n"
                        await asyncio.sleep(0.2)
            finally:
                await pubsub.aclose()

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return application


app = create_app()
