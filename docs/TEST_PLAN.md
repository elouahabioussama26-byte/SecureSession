# Test plan

| ID | Scenario | Expected result |
|---|---|---|
| T01 | Redis health check | API reports Redis connected |
| T02 | Register a valid username and password | 201 response, Argon2id hash in Redis and HttpOnly cookie |
| T03 | Register an existing username | 409 duplicate-account response |
| T04 | Register a password shorter than 8 characters | 422 validation response |
| T05 | Sign in with correct credentials | 200 response and new HttpOnly session cookie |
| T06 | Sign in with incorrect password | 401 response; no new session |
| T07 | Validate current session | 200 and safe session metadata |
| T08 | Validate without/after revocation | 401 |
| T09 | List current user's sessions | Only that user's active sessions |
| T10 | Revoke another session owned by current user | 204; revoked token becomes invalid |
| T11 | Revoke another user's session | Rejected; other user's session remains active |
| T12 | Wait for TTL expiration | Session key disappears automatically |
| T13 | Seed 20 simultaneous sessions | Dashboard displays 20 active sessions |
| T14 | Subscribe to events, then create/revoke a session | Subscriber receives Pub/Sub event |

Run automated tests with `python -m pytest -v`. Complete the remaining API/UI scenarios against the running Redis instance and record screenshots and results for the technical report.
