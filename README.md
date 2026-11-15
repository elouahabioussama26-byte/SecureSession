# SecureSession

**Centralized User Session Management System**  
University NoSQL project — P13: Développement d'un système sécurisé de gestion des sessions utilisateurs.

SecureSession is a learning application for account registration, password authentication and centralized session management with Redis. The backend uses FastAPI and Python, while Redis stores account records and session data. A responsive browser dashboard lets users review and revoke active sessions.

> **Educational scope:** this is a university prototype, not a production identity provider. It demonstrates account credentials and session management, but does not include email verification, password reset, MFA, CSRF tokens, or production-grade rate limiting.

## Features

- Create an account with a unique username and password.
- Hash passwords with Argon2id before storing them in Redis.
- Sign in using username and password.
- Store random opaque session tokens in HttpOnly cookies; Redis stores only SHA-256 token digests.
- Validate the current session on protected API routes.
- View account details, active-session count and current-session expiry.
- List active devices and revoke individual sessions.
- Sign out and revoke the current session.
- Expire sessions automatically using Redis TTL.
- Track users and session expiry order with Redis Sets and Sorted Sets.
- Publish session-created, revoked and expired events with Redis Pub/Sub.
- Demonstrate 20 simultaneous sessions for a demo account.
- Responsive dashboard, FastAPI Swagger documentation and automated tests.

## Architecture

```text
Browser (HTML / CSS / JavaScript)
            |
            | HTTPS/HTTP + HttpOnly session cookie
            v
        FastAPI
        /     \
 AccountService  SessionService
        \     /
         redis-py
            |
            v
       Redis 7 (Docker)
```

## Redis data model

| Redis key | Type | Purpose |
|---|---|---|
| `account:<username>` | Hash | Username, Argon2 password hash and account creation time |
| `session:<sha256-token>` | Hash | Session ID, user, creation and expiration time, client metadata |
| `session-id:<session-uuid>` | String with TTL | Maps a session ID to its token digest for revocation |
| `user:<username>:sessions` | Sorted Set | Session IDs scored by expiration timestamp |
| `secure_session:connected_users` | Set | Unique users with active sessions |
| `secure_session:events` | Pub/Sub channel | Live created, revoked and expired events |

The raw password is never stored. Argon2id hashes are stored in the account Hash. The raw session token is never stored in Redis; the browser receives it as an HttpOnly cookie.

### Redis features demonstrated

- **Hashes:** `HSET`, `HGETALL` for account and session metadata.
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

1. Clone or update the repository:

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

4. Install dependencies and configure the environment:

```bash
pip install -r requirements.txt
cp .env.example .env
```

The example configuration uses `redis://localhost:6379/0`, matching the existing container. If `.env` already exists, do not overwrite it; check that its `REDIS_URL` is correct.

5. Start the API:

```bash
uvicorn app.main:app --reload
```

6. Open the dashboard and API documentation:

- Dashboard: http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/api/health

## Account usage

Open the dashboard and select **Create account**. Choose a username and a password of at least 8 characters. Successful registration automatically signs you in.

For an existing account, select **Sign in** and enter the same username and password.

Passwords are hashed with Argon2id. Duplicate usernames are rejected. Usernames are normalized to lowercase.

## Demonstrate 20 simultaneous sessions

With the virtual environment active, execute:

```bash
python scripts/seed_demo.py
```

The script creates the demo account if it does not yet exist and adds 20 fictitious sessions. Sign in using:

- Username: `demo_user`
- Password on first creation: `DemoPass123!`

If that account already exists, the script preserves its existing password rather than resetting it. The script removes older sessions indexed for this demo user, then creates 20 new sessions; it does not delete other users' data.

## Tests

Run:

```bash
python -m pytest -v
```

Tests use fakeredis and do not require a separate Redis server. They cover password hashing, authentication, duplicate account rejection, session validation, listing, revocation, user isolation and 20 simultaneous sessions.

## API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check API and Redis |
| POST | `/api/accounts` | Register an account and create its first session |
| POST | `/api/sessions` | Sign in and create a new session |
| GET | `/api/sessions/me` | Validate and return current session |
| GET | `/api/sessions` | List active sessions of current user |
| DELETE | `/api/sessions/me` | Revoke current session and clear cookie |
| DELETE | `/api/sessions/{session_id}` | Revoke a session belonging to current user |
| GET | `/api/events` | Receive real-time session events (Server-Sent Events) |

Example registration:

```http
POST /api/accounts
Content-Type: application/json

{"username": "oussama", "password": "SecurePass123!"}
```

Example sign-in:

```http
POST /api/sessions
Content-Type: application/json

{"username": "oussama", "password": "SecurePass123!"}
```

Successful registration and sign-in set an HttpOnly session cookie. The JSON response does not expose the raw session token.

## Security and limitations

- Passwords are hashed with Argon2id. They are not encrypted or stored in plaintext.
- Session tokens are generated with a cryptographically secure random generator; Redis stores only their SHA-256 digests.
- Cookies use HttpOnly and SameSite=Lax. Enable `SESSION_COOKIE_SECURE=true` when using HTTPS.
- For production, add HTTPS, CSRF protection appropriate to the deployment, rate limiting, email verification, password reset, MFA, account lockout policy, secure secret management and monitoring.
- Do not expose this demo to the public internet or use it to protect real accounts.
- Keep `.env` out of Git. Do not commit passwords, secrets or production tokens.
- Redis Pub/Sub is ephemeral: subscribers only receive events while connected. It is used for live UI updates, not as a durable audit log.
- The connected-users Set is an index for the demonstration; periodic cleanup or a more robust membership strategy would be needed for long-running production use.

## Project structure

```text
SecureSession/
├── app/
│   ├── auth_service.py
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
│   ├── test_api.py
│   ├── test_auth_service.py
│   └── test_session_service.py
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── pytest.ini
└── requirements.txt
```

## University deliverables

This repository provides the application source, environment configuration, Redis data model, API examples, test/demo scripts and README installation instructions. Add your own screenshots, technical analysis, test evidence, limitations and AI-use declaration to the 8–12 page report, and prepare the oral presentation from the actual application you run.
