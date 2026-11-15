# API and Redis implementation notes

## Account lifecycle

1. A user submits a username and password to `POST /api/accounts`.
2. FastAPI validates the input. AccountService hashes the password with Argon2id.
3. The account is stored as a Redis Hash under `account:<username>`.
4. HSETNX reserves each username atomically; duplicate registrations return HTTP 409.
5. Registration creates the first session and sets an HttpOnly cookie.
6. A later sign-in loads the account Hash and verifies the submitted password against the Argon2id hash.

Passwords are not stored in plaintext and are never returned from the API.

## Session lifecycle

1. The browser submits credentials to `POST /api/sessions`.
2. AccountService verifies the password hash.
3. SessionService generates a cryptographically random token and hashes it with SHA-256.
4. Session metadata is stored in a Redis Hash. The raw token is set only in an HttpOnly cookie.
5. Protected endpoints hash the cookie token and retrieve the corresponding Redis Hash.
6. Logout/revocation deletes the session Hash, lookup key and Sorted Set member.
7. Redis expires the session Hash and lookup key automatically after the configured TTL.

## Redis key schema

| Key | Redis type | Stored information |
|---|---|---|
| `account:<username>` | Hash | Username, Argon2id password hash and creation timestamp |
| `session:<digest>` | Hash | Session ID, user, creation/expiry timestamps, client metadata |
| `session-id:<session_id>` | String with TTL | SHA-256 token digest |
| `user:<user_id>:sessions` | Sorted Set | Session IDs scored by expiry timestamp |
| `secure_session:connected_users` | Set | Active user IDs |
| `secure_session:events` | Pub/Sub | Created, revoked and expired event messages |

## Significant operations

| Operation | Redis commands |
|---|---|
| Register account | HSETNX, HSET |
| Authenticate account | HGETALL |
| Create a session | HSET, EXPIRE, SET EX, ZADD, SADD, PUBLISH |
| Validate a session | HGETALL, TTL |
| List a user's active sessions | ZRANGEBYSCORE, GET, HGETALL, TTL |
| Revoke a session | GET, HGETALL, DEL, ZREM, ZCARD, SREM, PUBLISH |
| Cleanup expired index entries | ZRANGEBYSCORE, ZREM, DEL |
| Notify connected dashboard | SUBSCRIBE / PUBLISH |

## API endpoints

- `POST /api/accounts`: register an account and start its first session.
- `POST /api/sessions`: sign in and create a session.
- `GET /api/sessions/me`: return the current validated session.
- `GET /api/sessions`: list the current user's active sessions.
- `DELETE /api/sessions/me`: revoke current session and clear cookie.
- `DELETE /api/sessions/{session_id}`: revoke one of the current user's sessions.
- `GET /api/events`: Server-Sent Events stream for the signed-in user.

## API examples

Register an account:

```bash
curl -i -c cookies.txt -X POST http://127.0.0.1:8000/api/accounts \
  -H 'Content-Type: application/json' \
  -d '{"username":"oussama","password":"SecurePass123!"}'
```

Sign in:

```bash
curl -i -b cookies.txt -c cookies.txt -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"username":"oussama","password":"SecurePass123!"}'
```

Read current session:

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/sessions/me
```

List active sessions:

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/sessions
```

Logout:

```bash
curl -i -b cookies.txt -X DELETE http://127.0.0.1:8000/api/sessions/me
```
