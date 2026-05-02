# Remote Deployment: Router + Room Workers

This deployment now uses single-port router architecture:
- public router process
- router spawns per-match room worker processes
- frontend uses router APIs for auth/matchmaking and uses the same router base for gameplay socket + `/protocol` traffic

Transport mode note:
- backend runtime is fixed to strict pipe IPC room workers behind the router.

## 1. Capacity and Port Range

Room workers do not listen on network ports.
Open firewall port only for `ROUTER_PORT`.

## 2. Required Backend Environment

Use [deploy/env/router.env.example](deploy/env/router.env.example).

Required controls:
- router bind: `ROUTER_HOST`, `ROUTER_PORT`
- router sqlite path: `ROUTER_DB_PATH`

Notes:
- Room workers use the same bind interface as `ROUTER_HOST`.
- Clients should reach the router origin configured in frontend runtime (`AVGE_ROUTER_BASE_URL`).

## 3. Service Supervision

Use [deploy/systemd/avge-router.service](deploy/systemd/avge-router.service) as a base:

1. Copy service file to `/etc/systemd/system/avge-router.service`.
2. Copy env file to `/etc/avge/router.env`.
3. Create runtime dirs:
   - `/var/lib/avge`
   - `/var/log/avge`
4. Enable and start:
   - `sudo systemctl daemon-reload`
   - `sudo systemctl enable --now avge-router`

Room workers remain child processes managed by router.

## 4. Frontend Runtime Wiring

In frontend deploy assets, edit `runtime-config.js` and set:
- `window.AVGE_ROUTER_BASE_URL`

Runtime behavior:
- auth/matchmaking calls go to `AVGE_ROUTER_BASE_URL`
- gameplay socket and HTTP `/protocol` fallback also go to `AVGE_ROUTER_BASE_URL`

## 5. Validation Checklist

Router API checks from browser network:
- `POST /session/bootstrap`
- `POST /api/v1/auth/login`
- `POST /matchmaking/queue`
- `GET /matchmaking/status`

Matchmaking and room assignment:
- queue response includes room identity and status

Pipe-mode routing checks:
- router `/health` is reachable via `AVGE_ROUTER_BASE_URL`
- socket registration and HTTP `/protocol` fallback both succeed against router origin

Protocol connectivity:
- browser connects to router socket endpoint via polling
- HTTP `/protocol` fallback works if socket connect fails

Lifecycle:
- full match completes
- room reports `/rooms/finish`
- reconnect path works with session + reconnect token

## 6. Production Hardening

- place router behind TLS reverse proxy
- set `ROUTER_COOKIE_SECURE=true` and `ROUTER_COOKIE_SAMESITE=None` for cross-site HTTPS frontend
- restrict CORS/socket origins:
  - `ROUTER_ALLOWED_ORIGINS`
  - `SERVER_ALLOWED_ORIGINS`
- backup `ROUTER_DB_PATH` sqlite file
- rotate router and room logs

## 7. Runtime Notes

Legacy room-port and callback compatibility knobs were removed from active deployment configuration.
