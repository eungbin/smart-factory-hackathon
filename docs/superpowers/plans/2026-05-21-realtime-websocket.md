# Realtime WebSocket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the dashboard/detail 5-second polling experience with backend-driven WebSocket updates using automatic simulator ticks every 2 seconds and AI predictions every 10 seconds.

**Architecture:** FastAPI owns a lightweight realtime manager, a WebSocket endpoint, and a startup background loop. The loop reuses the existing simulator service, broadcasts equipment/dashboard updates after each sensor tick, and throttles AI predictions to the requested 10-second cadence without overlapping runs.

**Tech Stack:** FastAPI WebSocket, asyncio background task, SQLAlchemy sessions, existing React state, browser WebSocket API.

---

### Task 1: Backend Realtime Event Boundary

**Files:**
- Create: `backend/app/realtime/manager.py`
- Test: `backend/tests/test_realtime_manager.py`

- [x] Write tests proving the manager broadcasts JSON to connected sockets and removes disconnected sockets.
- [x] Implement a small `RealtimeManager` with `connect`, `disconnect`, and `broadcast`.
- [x] Run `backend/.venv/Scripts/python.exe -m unittest tests.test_realtime_manager`.

### Task 2: Simulation Service Realtime Payload

**Files:**
- Modify: `backend/app/services/simulation.py`
- Test: `backend/tests/test_realtime_loop.py`

- [x] Write tests proving a sensor-only tick inserts readings without predictions and a prediction tick creates predictions.
- [x] Add an `include_predictions` flag to `create_sensor_tick`.
- [x] Keep the existing `/simulation/tick` REST endpoint behavior unchanged by default.
- [x] Run `backend/.venv/Scripts/python.exe -m unittest tests.test_simulation_api tests.test_realtime_loop`.

### Task 3: Backend WebSocket Endpoint And Loop

**Files:**
- Create: `backend/app/api/realtime.py`
- Create: `backend/app/services/realtime_loop.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_realtime_app.py`

- [x] Write tests proving `/api/v1/realtime` is registered and the app starts with realtime enabled by default.
- [x] Add WebSocket endpoint that accepts clients and keeps the socket alive.
- [x] Add startup/shutdown hooks for the automatic loop.
- [x] Run `backend/.venv/Scripts/python.exe -m unittest tests.test_realtime_app tests.test_cors`.

### Task 4: Frontend WebSocket Client

**Files:**
- Create: `src/api/realtime.ts`
- Modify: `src/pages/Dashboard.tsx`
- Modify: `src/pages/EquipmentDetail.tsx`
- Run: `npm run build`

- [x] Add typed realtime events for equipment state and dashboard summary updates.
- [x] Replace periodic dashboard/detail polling with WebSocket updates after initial REST load.
- [x] Keep a reconnect loop so temporary disconnects recover without a page refresh.
- [x] Run `npm run build`.

### Task 5: Verification

**Files:**
- No code changes expected.

- [x] Run `backend/.venv/Scripts/python.exe -m unittest discover -s tests`.
- [x] Run `npm run build`.
- [x] Verify realtime route, manager behavior, and 2-second/10-second cadence constants with backend tests.
