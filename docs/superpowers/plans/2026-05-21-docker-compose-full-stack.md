# Full Stack Docker Compose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a fresh clone run the frontend, backend API, and Postgres with one root-level `docker compose up -d --build` command.

**Architecture:** Add a root Docker Compose file that reuses the existing backend Dockerfile and adds a frontend image. The frontend image builds the Vite app and serves the static output with nginx, while the browser connects to the API at `http://localhost:8000`.

**Tech Stack:** Docker Compose, nginx, Vite, FastAPI, Postgres pgvector.

---

### Task 1: Frontend Image

**Files:**
- Create: `frontend.Dockerfile`
- Create: `nginx.conf`
- Create: `.dockerignore`

- [x] Build the React app in a Node stage with `npm ci` and `npm run build`.
- [x] Serve `/dist` from nginx with SPA fallback to `index.html`.
- [x] Keep the Docker context small by excluding backend, node_modules, and local artifacts.

### Task 2: Root Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `backend/.dockerignore`

- [x] Add `frontend`, `api`, and `postgres` services.
- [x] Map frontend to `http://localhost:5173`.
- [x] Map backend API to `http://localhost:8000`.
- [x] Keep existing backend compose unchanged.

### Task 3: Verification

**Files:**
- No production code changes expected.

- [x] Run `npm run build`.
- [x] Run `docker compose config` from the repo root.
