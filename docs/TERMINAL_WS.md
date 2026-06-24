# Terminal WebSocket Operations

FixitLab lab terminals use a long-lived WebSocket at `/ws/terminal/<session_id>/`.

## Architecture

- **Edge (nginx):** TLS termination, `limit_req zone=ws_connect_rate burst=30` on `/ws/` (raised from 10 to avoid reconnect 503 storms).
- **App (Daphne/Channels):** One consumer per connection; sends `shell_ready` after welcome banner and after server-side shell respawn.
- **Labs node (D4):** Docker exec over SSH for container labs; simulation state in Redis + in-process `_SIM_SESSIONS`.

## Multi-worker stickiness

Simulation engine state is registered in-process per worker (`register_sim_session`). If Daphne runs multiple workers **without** sticky routing, a reconnect may land on a different worker and trigger rehydration from `simulation_snapshot` (slower but functional).

**Production recommendation:**

1. Use **ip_hash** (or consistent hash on session id) for `/ws/terminal/` upstream in nginx, **or**
2. Run a **single Daphne worker** for WebSocket traffic on a dedicated port, **or**
3. Ensure `ensure_sim_session()` + Redis snapshot rehydration is always called on connect (already implemented).

## Client reconnect policy

`LabTerminal.jsx`:

- Pauses reconnect while the browser tab is hidden.
- Does not reset `onReady` on every reconnect (prevents parent remount loops).
- Sends `shell_ready` handling before fallback timer (1.5s Docker, 800ms simulation).

## Server respawn

When the exec/simulation stream EOFs, `consumers.py` calls `_respawn_shell()` and immediately sends `shell_ready` so the client does not enter a reconnect loop.

## Vault degradation

If Vault API is unreachable (`http://vault:8200`) but secrets are loaded at startup, labs continue with cached secrets. Terminal provisioning does not require live Vault unless rotating credentials mid-session.
