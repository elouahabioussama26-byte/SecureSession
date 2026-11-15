# Test plan

| ID | Scenario | Expected result |
|---|---|---|
| T01 | Redis health check | API reports Redis connected |
| T02 | Create session with valid username | 201 response and HttpOnly cookie |
| T03 | Submit invalid username | 422 validation error |
| T04 | Validate session with cookie | 200 and safe session metadata |
| T05 | Validate without/after revocation | 401 |
| T06 | List current user's sessions | Only that user's active sessions |
| T07 | Revoke another session owned by current user | 204; token becomes invalid |
| T08 | Revoke another user's session | Rejected; other user's session remains active |
| T09 | Wait for TTL expiration | Session key disappears automatically |
| T10 | Seed 20 simultaneous sessions | Dashboard displays 20 active sessions |
| T11 | Subscribe to events, then create/revoke a session | Subscriber receives Pub/Sub event |

Run automated service tests with `pytest -v`. Complete API/UI scenarios against the running Redis instance and record screenshots and results for the technical report.
