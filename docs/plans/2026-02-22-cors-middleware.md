# CORS Middleware Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable CORS support in the FastAPI API to handle browser preflight requests.

**Architecture:** Add Starlette's `CORSMiddleware` to the FastAPI app factory with permissive defaults.

**Tech Stack:** FastAPI, Starlette CORSMiddleware

---

### Task 1: Add CORS Middleware

**Files:**
- Modify: `src/picklebot/api/app.py`

**Step 1: Add import**

Add `CORSMiddleware` to the imports:

```python
from fastapi.middleware.cors import CORSMiddleware
```

**Step 2: Add middleware to create_app**

Add the middleware right after `app.state.context = context`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 3: Verify manually**

Start the server and test OPTIONS:

```bash
curl -X OPTIONS http://localhost:8000/agents -I
```

Expected: Response includes `access-control-allow-origin: *` header.

**Step 4: Commit**

```bash
git add src/picklebot/api/app.py
git commit -m "feat(api): add CORS middleware for browser requests"
```
