# API and Redis implementation notes

## Session lifecycle

1. The browser submits a demo username to `POST /api/sessions`.
2. FastAPI validates the input, generates a cryptographically random token and passes it to SessionService.
3. SessionService hashes the token with SHA-256 and stores session data in a Redis Hash.
4. The raw token is set in an HttpOnly cookie. It is not returned in JSON.
5. Protected endpoints hash the cookie token and retrieve the corresponding Redis Hash.
6. Logout/revocation deletes the session Hash, lookup key and Sorted Set member.
7. Redis expires the session Hash and lookup key automatically after the configured TTL.

## Redis key schema

For one session, let `digest = SHA256(raw_cookie_token)`.

- `session:<digest>`: Hash with `session_id`, `user_id`, `username`, `created_at`, `expires_at`, `client_ip`, `user_agent`.
- `session-id:<session_id>`: String containing digest, with same TTL.
- `user:<user_id>:sessions`: Sorted Set where member is session ID and score is Unix expiration time.
- `secure_session:connected_users`: Set of user IDs.
- `secure_session:events`: Pub/Sub channel.

## Significant operations

| Operation | Redis commands |
|---|---|
| Create a session | HSET, EXPIRE, SET EX, ZADD, SADD, PUBLISH |
| Validate a session | HGETALL, TTL |
| List a user's active sessions | ZRANGEBYSCORE, GET, HGETALL, TTL |
| Revoke a session | GET, HGETALL, DEL, ZREM, ZCARD, SREM, PUBLISH |
| Cleanup expired index entries | ZRANGEBYSCORE, ZREM, DEL |
| Notify connected dashboard | SUBSCRIBE / PUBLISH |

## API examples

Create a session:

```bash
curl -i -c cookies.txt -X POST http://127.0.0.1:8000/api/sessions \
  -H 'Content-Type: application/json' \
  -d '{"username":"oussama"}'
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
