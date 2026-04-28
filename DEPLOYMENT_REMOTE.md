# Remote Deployment: Router + Room Workers

This deployment keeps the current architecture:
- public router process
- router spawns per-match room worker processes on dynamic ports
- frontend uses router APIs for auth/matchmaking and switches to room `endpoint_url` for protocol traffic

## 1. Capacity and Port Range

Each active match uses one room port.

Sizing rule:
- required room ports = max concurrent matches + buffer
- suggested buffer = 20 percent

Example:
- target 150 concurrent matches
- room range size about 180

Configure:
- `ROOM_BASE_PORT`
- `ROOM_PORT_RANGE_SIZE`

Open firewall ports:
- router port (`ROUTER_PORT`)
- room port range (`ROOM_BASE_PORT` to `ROOM_BASE_PORT + ROOM_PORT_RANGE_SIZE - 1`)

## 2. Required Backend Environment

Use [deploy/env/router.env.example](deploy/env/router.env.example).

Required controls:
- router bind: `ROUTER_HOST`, `ROUTER_PORT`
- room endpoint host and allocation: `ROOM_HOST`, `ROOM_BASE_PORT`, `ROOM_PORT_RANGE_SIZE`
- room bind host: `ROOM_BIND_HOST`
- router sqlite path: `ROUTER_DB_PATH`
- room callback URL: `ROUTER_BASE_URL`

Notes:
- Set `ROOM_HOST` to the public host/IP clients should connect to.
- Set `ROOM_BIND_HOST` to local bind interface (`0.0.0.0` is common).

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

Fallback controls (optional):
- `window.AVGE_BACKEND_BASE_URL`
- `window.AVGE_BACKEND_PROTOCOL_URL`

Runtime behavior:
- router calls go to `AVGE_ROUTER_BASE_URL`
- match protocol goes to assigned room `endpoint_url`
- fallback backend URLs are used only if no assigned room endpoint is stored

## 5. Validation Checklist

Router API checks from browser network:
- `POST /session/bootstrap`
- `POST /api/v1/auth/login`
- `POST /matchmaking/queue`
- `GET /matchmaking/status`

Matchmaking and room assignment:
- queue response includes `room.endpoint_url`
- `endpoint_url` is not localhost for remote clients

Protocol connectivity:
- browser connects to room socket via polling
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

## 7. Follow-up Architecture (Optional)

Single-domain room routing is not implemented in this iteration.
Current deployment assumes exposing a controlled room port range.
