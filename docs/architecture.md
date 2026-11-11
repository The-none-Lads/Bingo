# Architecture assessment

## Current architecture

Bingo is a modular monolith with a FastAPI backend and a React/Vite frontend. The backend uses SQLAlchemy and Alembic for account and access-link data, while persistent bingo cards are stored in SQLite through a small standard-library repository. Live game state and WebSocket connections are held in process memory. The frontend is served separately by Nginx and reads deployment URLs from runtime-generated `config.js`.

This design is appropriate for a single-instance deployment: it avoids unnecessary infrastructure and keeps card persistence simple. It is not a horizontally scalable or restart-resilient game engine.

## Prioritized findings

### High

- Production bootstrap previously allowed privileged operations when there were no accounts or shared key. Production now fails closed; the initial administrator must present `X-Bootstrap-Token`, and subsequent public registration defaults off.
- Production CORS previously inherited localhost defaults and allowed `"*"`. Production now requires explicit origins and rejects wildcard configuration.
- Operators could replace a game owned by another operator by starting it under the same ID. Game creation now checks ownership while holding the per-game lock.
- `backend/.env` was tracked despite the repository ignore rules. It is now untracked; rotate any credentials that may have appeared in its history.

### Medium

- Active games, draw locks, WebSocket membership, and broadcasts are process-local. Run one backend replica; games and draws are lost on restart and are not shared across workers or replicas. Persistent cards survive only when the SQLite volume is retained.
- SQLite card storage uses one local file and in-process locking. This is appropriate for a single backend instance, but not a shared multi-host storage system.
- Backend routes and the WebSocket manager remain concentrated in `backend/app.py`; route/domain separation can be introduced incrementally.
- The frontend still groups much application state and API behavior in large feature components. Runtime API/WebSocket URLs are configurable without rebuilding the image.
- Python dependencies are specified by ranges without a generated lockfile. The frontend has a lockfile and uses `npm ci` in its image build.
- Existing backend tests cover core game, persistence, auth, and integration flows; frontend automated coverage is limited to utility tests, with no browser-level end-to-end suite.

### Low

- Several repository workflows previously repeated tests and allowed lint failures to pass. They have been consolidated into blocking backend and frontend checks; Docker publishing remains a separate tag-only workflow.
- Game eviction at the configured in-memory capacity removes the oldest game. Operators should keep `MAX_GAMES` appropriate for the deployment until game lifecycle/persistence requirements are defined.

## Deployment and operating constraints

- Keep one backend replica and one persistent volume mounted at `/app/data` for persistent cards.
- Use `ENVIRONMENT=production`, explicit `CORS_ORIGINS`, and a strong `INITIAL_ADMIN_TOKEN` for initial account creation. See the production bootstrap section in the [README](../README.md).
- Set frontend `API_BASE_URL` and `WS_BASE_URL` to URLs reachable by the user's browser; behind HTTPS termination, configure HTTPS/WSS URLs.
- Docker and Kubernetes health checks use `/health` on the backend and `/` on the frontend.
- GHCR image names and the separate frontend/backend publishing model remain unchanged. Version tags publish versioned and `latest` tags; the explicit `dev` tag does not update `latest`.

## Recommended next steps

1. Generate and check in a reproducible Python dependency lockfile, then validate dependency updates in CI.
2. Split game, card, and WebSocket routes from `app.py` while retaining the existing API contracts.
3. Add frontend component and browser-level tests for admin, player, printing, reconnect, and display flows.
4. Define game recovery and multi-instance requirements before choosing durable game storage or distributed messaging.
5. Add bounded observability and review SQLite write concurrency under the expected deployment load.
