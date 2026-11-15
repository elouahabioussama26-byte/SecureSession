# SecureSession

**Centralized User Session Management System**  
University NoSQL project — P13: Développement d'un système sécurisé de gestion des sessions utilisateurs.

SecureSession is a learning application that demonstrates how Redis can manage user sessions independently from the web application's local process state. The backend is built with FastAPI and Python; Redis is the session store; a lightweight browser dashboard makes the operations visible.

> **Educational scope:** authentication is simulated. A user enters a username to obtain a session; this project does not verify a real password or connect to an identity provider. It is a university prototype, not a production identity system.

## Features

- Create a session with a cryptographically random opaque token.
- Keep the token in an HttpOnly cookie; store only its SHA-256 digest in Redis.
- Validate the current session on protected API routes.
- List a user's active sessions and see the current session.
- Revoke another active session or sign out the current session.
- Expire sessions automatically using Redis TTL.
- Track users and session expiration order with Redis Sets and Sorted Sets.
- Publish session-created, revoked and expired events with Redis Pub/Sub.
- Demonstrate 20 simultaneous fictitious sessions for one user.
- Interactive dashboard, FastAPI Swagger documentation and automated tests.

## Architecture

```text
Browser (HTML / CSS / JavaScript)
            |
            | HTTP + HttpOnly session cookie
            v
        FastAPI
            |
       SessionService
            |
         redis-py
            |
            v
       Redis 7 (Docker)
```

## Redis data model

| Redis key | Type | Purpose |
|---|---|---|
| `session:<sha256-token>` | Hash | Session ID, user, creation and expiration time, client metadata |
| `session-id:<session-uuid>` | String with TTL | Maps a session ID to its token digest for revocation |
| `user:<username>:sessions` | Sorted Set | Session IDs scored by expiration timestamp |
| `secure_session:connected_users` | Set | Unique users with active sessions |
| `secure_session:events` | Pub/Sub channel | Live created, revoked and expired events |

The raw token is never stored in Redis. The browser receives it as a cookie with HttpOnly enabled. The cookie uses SameSite=Lax by default. Set Secure=true when serving the app over HTTPS.

### Redis features demonstrated

- **Hashes:** `HSET`, `HGETALL` for session metadata.
- **Expiration:** `EXPIRE`, `TTL` and key expiration.
- **Sorted Sets:** `ZADD`, `ZRANGEBYSCORE`, `ZREM` for per-user session indexes.
- **Sets:** `SADD`, `SREM`, `SMEMBERS` for connected-user tracking.
- **Strings:** `SET` with expiration for session-ID lookup.
- **Pub/Sub:** `PUBLISH` and `SUBSCRIBE` for session activity events.

## Requirements

- Ubuntu/Linux or another operating system with Python 3.10+.
- Docker Engine.
- Redis 7 (your existing `redis:7-alpine` container is supported).
- Python dependencies from `requirements.txt`.

## Run with your existing Redis container

Your existing Redis container exposes port 6379. Reuse it; do not create another Redis container on that same port.

1. Clone the repository:

```bash
git clone https://github.com/elouahabioussama26-byte/SecureSession.git
cd SecureSession
```

2. Check Redis:

```bash
docker ps
docker exec -it redis redis-cli PING
```

Expected response: `PONG`.

3. Create and activate a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If venv support is missing on Ubuntu:

```bash
sudo apt update
sudo apt install python3-venv
```

4. Install dependencies and configure the environment:

```bash
pip install -r requirements.txt
cp .env.example .env
```

The example configuration uses `redis://localhost:6379/0`, matching the existing container.

5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Open the dashboard and API documentation:

- Dashboard: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health

## Alternative: run the complete stack with Docker Compose

The Compose configuration starts its own Redis container and the API. Its Redis port is mapped to host port **6380**, so it does not conflict with your existing container on port 6379.

```bash
docker compose up --build
```

Open http://127.0.0.1:8000. To stop the stack:

```bash
docker compose down
```

To also delete the Compose Redis data volume (destructive):

```bash
docker compose down -v
```

Do not use the Compose mode and the existing-Redis mode interchangeably without checking which Redis URL the API is using.

## Demonstrate 20 simultaneous sessions

With the virtual environment active and the API stopped or running, execute:

```bash
python scripts/seed_demo.py
```

The script creates exactly 20 fictitious sessions for `demo_user`. Then open the dashboard and sign in using the username `demo_user`. The dashboard lists the seeded sessions; try revoking one. The seeder does not print or expose session tokens.

The script first removes existing sessions indexed for the demo user, then creates 20 new sessions. It does not delete other users' data.

## Tests

Run:

```bash
pytest -v
```

The tests use fakeredis and do not require a separate Redis server. They cover token-digest storage, session validation, listing, revocation, user isolation and 20 simultaneous sessions.

## API endpoints

All session-management endpoints require the HttpOnly cookie except session creation and health check.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check API and Redis |
| POST | `/api/sessions` | Simulate login and create session |
| GET | `/api/sessions/me` | Validate and return current session |
| GET | `/api/sessions` | List active sessions of current user |
| DELETE | `/api/sessions/me` | Revoke current session and clear cookie |
| DELETE | `/api/sessions/{session_id}` | Revoke a session belonging to current user |
| GET | `/api/events` | Receive real-time session events (Server-Sent Events) |

Example session creation request:

```http
POST /api/sessions
Content-Type: application/json

{"username": "oussama"}
```

The response includes safe session metadata. The raw session token is sent only in the HttpOnly cookie.

## Project structure

```text
SecureSession/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   ├── models.py
│   ├── redis_client.py
│   └── session_service.py
├── scripts/
│   ├── redis_inspect.py
│   └── seed_demo.py
├── static/
│   ├── app.js
│   ├── index.html
│   └── style.css
├── tests/
│   └── test_session_service.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── requirements.txt
```

## Security and limitations

- Authentication is deliberately simulated to match the project's simulated authentication scope. A username is not proof of identity.
- Do not expose this demo to the public internet or use it to protect real accounts.
- For a production system, integrate real authentication, enforce HTTPS, set the cookie Secure flag, add CSRF protection appropriate to the deployment, rate-limit authentication, define session and account policies, and monitor Redis access.
- Keep `.env` out of Git. Do not commit passwords, secrets or production tokens.
- Redis Pub/Sub is ephemeral: subscribers only receive events while connected. It is used here for live UI updates, not as a durable audit log.
- The connected-users Set is an index for the demonstration; periodic cleanup or a more robust membership strategy would be needed for long-running production use.

## University deliverables

This repository provides the source code, environment configuration, Redis data model, test/demo scripts and README installation instructions. Add your own screenshots, technical analysis, test evidence, limitations and AI-use declaration to the 8–12 page report, and prepare the oral presentation from the actual application you run.
