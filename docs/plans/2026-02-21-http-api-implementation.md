# HTTP API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add FastAPI-based HTTP interface with CRUD operations for all pickle-bot resources.

**Architecture:** New `api/` module with FastAPI routers that use existing `SharedContext` for dependency injection. API runs as part of `picklebot server` when enabled in config.

**Tech Stack:** FastAPI, uvicorn, Pydantic

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add fastapi and uvicorn to dependencies**

Add to `pyproject.toml` dependencies:
```toml
"fastapi>=0.115.0",
"uvicorn[standard]>=0.32.0",
```

**Step 2: Install dependencies**

Run: `uv sync`
Expected: Packages installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add fastapi and uvicorn dependencies"
```

---

## Task 2: Add ApiConfig to Config Schema

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Test: `tests/utils/test_config.py`

**Step 1: Write the failing test**

Add to `tests/utils/test_config.py`:
```python
def test_config_has_api_config():
    """Config should include api configuration."""
    from picklebot.utils.config import ApiConfig

    config = Config(
        workspace=Path("/tmp/test-workspace"),
        llm=LLMConfig(provider="openai", model="gpt-4", api_key="test"),
        default_agent="pickle",
        api=ApiConfig(enabled=True, host="0.0.0.0", port=3000),
    )

    assert config.api.enabled is True
    assert config.api.host == "0.0.0.0"
    assert config.api.port == 3000
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/utils/test_config.py::test_config_has_api_config -v`
Expected: FAIL with "ApiConfig not defined" or similar

**Step 3: Add ApiConfig model**

Add to `src/picklebot/utils/config.py` after `DiscordConfig`:
```python
class ApiConfig(BaseModel):
    """HTTP API configuration."""

    enabled: bool = False
    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, lt=65536)
```

**Step 4: Add api field to Config class**

Add to `Config` class fields:
```python
api: ApiConfig = Field(default_factory=ApiConfig)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/utils/test_config.py::test_config_has_api_config -v`
Expected: PASS

**Step 6: Commit**

```bash
git add src/picklebot/utils/config.py tests/utils/test_config.py
git commit -m "feat(config): add ApiConfig for HTTP API settings"
```

---

## Task 3: Create API Module Structure

**Files:**
- Create: `src/picklebot/api/__init__.py`
- Create: `src/picklebot/api/app.py`
- Create: `src/picklebot/api/deps.py`
- Create: `src/picklebot/api/schemas.py`
- Create: `src/picklebot/api/routers/__init__.py`

**Step 1: Create api module init**

Create `src/picklebot/api/__init__.py`:
```python
"""HTTP API module for pickle-bot."""

from picklebot.api.app import create_app

__all__ = ["create_app"]
```

**Step 2: Create deps.py with get_context dependency**

Create `src/picklebot/api/deps.py`:
```python
"""FastAPI dependencies for API routers."""

from fastapi import Request

from picklebot.core.context import SharedContext


def get_context(request: Request) -> SharedContext:
    """Get SharedContext from app state."""
    return request.app.state.context
```

**Step 3: Create empty routers init**

Create `src/picklebot/api/routers/__init__.py`:
```python
"""API routers for pickle-bot resources."""
```

**Step 4: Create schemas with make_create_model utility**

Create `src/picklebot/api/schemas.py`:
```python
"""Pydantic schemas for API request/response models."""

from pydantic import BaseModel, create_model

from picklebot.core.cron_loader import CronDef
from picklebot.core.history import HistoryMessage
from picklebot.core.skill_loader import SkillDef


def make_create_model(
    model_cls: type[BaseModel], exclude: set[str] | None = None
) -> type[BaseModel]:
    """Derive a Create model from existing model, excluding specified fields."""
    if exclude is None:
        exclude = {"id"}

    fields = {}
    for name, field in model_cls.model_fields.items():
        if name in exclude:
            continue
        fields[name] = (
            field.annotation,
            field.default if field.has_default else ...,
        )

    return create_model(f"{model_cls.__name__}Create", **fields)


# Derived models - reuse existing definitions
SkillCreate = make_create_model(SkillDef)
CronCreate = make_create_model(CronDef)
MemoryCreate = make_create_model(
    HistoryMessage, exclude={"timestamp", "tool_calls", "tool_call_id"}
)


# Hand-written models (need special handling)

class AgentCreate(BaseModel):
    """Request body for creating/updating an agent."""

    name: str
    description: str = ""
    system_prompt: str
    provider: str | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    allow_skills: bool = False


class ConfigUpdate(BaseModel):
    """Request body for updating config (partial updates)."""

    default_agent: str | None = None
    chat_max_history: int | None = None
    job_max_history: int | None = None
```

**Step 5: Create app.py with factory**

Create `src/picklebot/api/app.py`:
```python
"""FastAPI application factory."""

from fastapi import FastAPI

from picklebot.core.context import SharedContext


def create_app(context: SharedContext) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    # Routers will be added here as they are created
    # app.include_router(agents.router, prefix="/agents", tags=["agents"])
    # ...

    return app
```

**Step 6: Run tests to verify nothing is broken**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 7: Commit**

```bash
git add src/picklebot/api/
git commit -m "feat(api): create API module structure with schemas and deps"
```

---

## Task 4: Implement Agents Router

**Files:**
- Create: `src/picklebot/api/routers/agents.py`
- Test: `tests/api/test_agents.py`

**Step 1: Write the failing tests**

Create `tests/api/test_agents.py`:
```python
"""Tests for agents API router."""

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        agents_path = workspace / "agents"
        agents_path.mkdir()

        # Create a test agent
        test_agent_dir = agents_path / "test-agent"
        test_agent_dir.mkdir()
        (test_agent_dir / "AGENT.md").write_text("""---
name: Test Agent
description: A test agent
---
You are a test agent.
""")

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListAgents:
    def test_list_agents_returns_empty_list_when_no_agents(self):
        """GET /agents returns empty list when no agents exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir)
            (workspace / "agents").mkdir()

            config = Config(
                workspace=workspace,
                llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
                default_agent="pickle",
            )
            context = SharedContext(config)
            app = create_app(context)

            with TestClient(app) as client:
                response = client.get("/agents")

        assert response.status_code == 200
        assert response.json() == []

    def test_list_agents_returns_agents(self, client):
        """GET /agents returns list of agents."""
        response = client.get("/agents")

        assert response.status_code == 200
        agents = response.json()
        assert len(agents) == 1
        assert agents[0]["id"] == "test-agent"
        assert agents[0]["name"] == "Test Agent"


class TestGetAgent:
    def test_get_agent_returns_agent(self, client):
        """GET /agents/{id} returns agent definition."""
        response = client.get("/agents/test-agent")

        assert response.status_code == 200
        agent = response.json()
        assert agent["id"] == "test-agent"
        assert agent["name"] == "Test Agent"
        assert agent["description"] == "A test agent"
        assert "You are a test agent" in agent["system_prompt"]

    def test_get_agent_not_found(self, client):
        """GET /agents/{id} returns 404 for non-existent agent."""
        response = client.get("/agents/nonexistent")

        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_agents.py -v`
Expected: FAIL with 404 errors (routers not registered)

**Step 3: Create agents router**

Create `src/picklebot/api/routers/agents.py`:
```python
"""Agent resource router."""

from fastapi import APIRouter, Depends, HTTPException

from picklebot.api.deps import get_context
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext

router = APIRouter()


@router.get("", response_model=list[AgentDef])
def list_agents(ctx: SharedContext = Depends(get_context)) -> list[AgentDef]:
    """List all agents."""
    return ctx.agent_loader.discover_agents()


@router.get("/{agent_id}", response_model=AgentDef)
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> AgentDef:
    """Get agent by ID."""
    try:
        return ctx.agent_loader.load(agent_id)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
"""FastAPI application factory."""

from fastapi import FastAPI

from picklebot.api.routers import agents
from picklebot.core.context import SharedContext


def create_app(context: SharedContext) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Pickle Bot API",
        description="HTTP API for pickle-bot SDK",
        version="0.1.0",
    )
    app.state.context = context

    app.include_router(agents.router, prefix="/agents", tags=["agents"])

    return app
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_agents.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add agents router with list and get endpoints"
```

---

## Task 5: Add Agents POST/PUT/DELETE

**Files:**
- Modify: `src/picklebot/api/routers/agents.py`
- Modify: `tests/api/test_agents.py`

**Step 1: Write the failing tests**

Add to `tests/api/test_agents.py`:
```python
from picklebot.api.schemas import AgentCreate


class TestCreateAgent:
    def test_create_agent(self, client):
        """POST /agents/{id} creates a new agent."""
        agent_data = AgentCreate(
            name="New Agent",
            description="A new agent",
            system_prompt="You are a new agent.",
        )

        response = client.post(
            "/agents/new-agent",
            json=agent_data.model_dump(),
        )

        assert response.status_code == 201
        agent = response.json()
        assert agent["id"] == "new-agent"
        assert agent["name"] == "New Agent"

        # Verify it was created
        get_response = client.get("/agents/new-agent")
        assert get_response.status_code == 200


class TestUpdateAgent:
    def test_update_agent(self, client):
        """PUT /agents/{id} updates an existing agent."""
        agent_data = AgentCreate(
            name="Updated Agent",
            description="Updated description",
            system_prompt="You are updated.",
        )

        response = client.put(
            "/agents/test-agent",
            json=agent_data.model_dump(),
        )

        assert response.status_code == 200
        agent = response.json()
        assert agent["name"] == "Updated Agent"


class TestDeleteAgent:
    def test_delete_agent(self, client):
        """DELETE /agents/{id} deletes an agent."""
        response = client.delete("/agents/test-agent")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/agents/test-agent")
        assert get_response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_agents.py -v`
Expected: FAIL with 405 Method Not Allowed or 404

**Step 3: Add POST/PUT/DELETE to agents router**

Update `src/picklebot/api/routers/agents.py`:
```python
"""Agent resource router."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.api.schemas import AgentCreate
from picklebot.core.agent_loader import AgentDef
from picklebot.core.context import SharedContext
from picklebot.utils.def_loader import DefNotFoundError

router = APIRouter()


def _write_agent_file(
    agent_id: str, data: AgentCreate, agents_path
) -> AgentDef:
    """Write agent definition to file."""
    agent_dir = agents_path / agent_id
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Build frontmatter
    frontmatter = f"""---
name: {data.name}
description: {data.description}
"""
    if data.provider:
        frontmatter += f"provider: {data.provider}\n"
    if data.model:
        frontmatter += f"model: {data.model}\n"
    frontmatter += f"""temperature: {data.temperature}
max_tokens: {data.max_tokens}
allow_skills: {data.allow_skills}
---

{data.system_prompt}
"""

    (agent_dir / "AGENT.md").write_text(frontmatter)


@router.get("", response_model=list[AgentDef])
def list_agents(ctx: SharedContext = Depends(get_context)) -> list[AgentDef]:
    """List all agents."""
    return ctx.agent_loader.discover_agents()


@router.get("/{agent_id}", response_model=AgentDef)
def get_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> AgentDef:
    """Get agent by ID."""
    try:
        return ctx.agent_loader.load(agent_id)
    except DefNotFoundError:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")


@router.post("/{agent_id}", response_model=AgentDef, status_code=status.HTTP_201_CREATED)
def create_agent(
    agent_id: str, data: AgentCreate, ctx: SharedContext = Depends(get_context)
) -> AgentDef:
    """Create a new agent."""
    agents_path = ctx.config.agents_path
    agent_file = agents_path / agent_id / "AGENT.md"

    if agent_file.exists():
        raise HTTPException(status_code=409, detail=f"Agent already exists: {agent_id}")

    _write_agent_file(agent_id, data, agents_path)
    return ctx.agent_loader.load(agent_id)


@router.put("/{agent_id}", response_model=AgentDef)
def update_agent(
    agent_id: str, data: AgentCreate, ctx: SharedContext = Depends(get_context)
) -> AgentDef:
    """Update an existing agent."""
    agents_path = ctx.config.agents_path
    agent_file = agents_path / agent_id / "AGENT.md"

    if not agent_file.exists():
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    _write_agent_file(agent_id, data, agents_path)
    return ctx.agent_loader.load(agent_id)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete an agent."""
    import shutil

    agents_path = ctx.config.agents_path
    agent_dir = agents_path / agent_id

    if not agent_dir.exists():
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    shutil.rmtree(agent_dir)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_agents.py -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add src/picklebot/api/routers/agents.py tests/api/test_agents.py
git commit -m "feat(api): add POST/PUT/DELETE endpoints for agents"
```

---

## Task 6: Implement Skills Router

**Files:**
- Create: `src/picklebot/api/routers/skills.py`
- Test: `tests/api/test_skills.py`

**Step 1: Write the failing tests**

Create `tests/api/test_skills.py` (similar structure to agents tests):
```python
"""Tests for skills API router."""

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        skills_path = workspace / "skills"
        skills_path.mkdir()

        # Create a test skill
        test_skill_dir = skills_path / "test-skill"
        test_skill_dir.mkdir()
        (test_skill_dir / "SKILL.md").write_text("""---
name: Test Skill
description: A test skill
---
# Test Skill

This is a test skill.
""")

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListSkills:
    def test_list_skills_returns_skills(self, client):
        """GET /skills returns list of skills."""
        response = client.get("/skills")

        assert response.status_code == 200
        skills = response.json()
        assert len(skills) == 1
        assert skills[0]["id"] == "test-skill"


class TestGetSkill:
    def test_get_skill_returns_skill(self, client):
        """GET /skills/{id} returns skill definition."""
        response = client.get("/skills/test-skill")

        assert response.status_code == 200
        skill = response.json()
        assert skill["id"] == "test-skill"
        assert skill["name"] == "Test Skill"

    def test_get_skill_not_found(self, client):
        """GET /skills/{id} returns 404 for non-existent skill."""
        response = client.get("/skills/nonexistent")

        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_skills.py -v`
Expected: FAIL with 404 errors

**Step 3: Create skills router**

Create `src/picklebot/api/routers/skills.py`:
```python
"""Skill resource router."""

import shutil

from fastapi import APIRouter, Depends, HTTPException, status

from picklebot.api.deps import get_context
from picklebot.api.schemas import SkillCreate
from picklebot.core.context import SharedContext
from picklebot.core.skill_loader import SkillDef
from picklebot.utils.def_loader import DefNotFoundError

router = APIRouter()


def _write_skill_file(skill_id: str, data: SkillCreate, skills_path) -> None:
    """Write skill definition to file."""
    skill_dir = skills_path / skill_id
    skill_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
name: {data.name}
description: {data.description}
---

{data.content}
"""

    (skill_dir / "SKILL.md").write_text(content)


@router.get("", response_model=list[SkillDef])
def list_skills(ctx: SharedContext = Depends(get_context)) -> list[SkillDef]:
    """List all skills."""
    return ctx.skill_loader.discover_skills()


@router.get("/{skill_id}", response_model=SkillDef)
def get_skill(skill_id: str, ctx: SharedContext = Depends(get_context)) -> SkillDef:
    """Get skill by ID."""
    try:
        return ctx.skill_loader.load_skill(skill_id)
    except DefNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")


@router.post("/{skill_id}", response_model=SkillDef, status_code=status.HTTP_201_CREATED)
def create_skill(
    skill_id: str, data: SkillCreate, ctx: SharedContext = Depends(get_context)
) -> SkillDef:
    """Create a new skill."""
    skills_path = ctx.config.skills_path
    skill_file = skills_path / skill_id / "SKILL.md"

    if skill_file.exists():
        raise HTTPException(status_code=409, detail=f"Skill already exists: {skill_id}")

    _write_skill_file(skill_id, data, skills_path)
    return ctx.skill_loader.load_skill(skill_id)


@router.put("/{skill_id}", response_model=SkillDef)
def update_skill(
    skill_id: str, data: SkillCreate, ctx: SharedContext = Depends(get_context)
) -> SkillDef:
    """Update an existing skill."""
    skills_path = ctx.config.skills_path
    skill_file = skills_path / skill_id / "SKILL.md"

    if not skill_file.exists():
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    _write_skill_file(skill_id, data, skills_path)
    return ctx.skill_loader.load_skill(skill_id)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete a skill."""
    skills_path = ctx.config.skills_path
    skill_dir = skills_path / skill_id

    if not skill_dir.exists():
        raise HTTPException(status_code=404, detail=f"Skill not found: {skill_id}")

    shutil.rmtree(skill_dir)
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
from picklebot.api.routers import agents, skills
# ...
app.include_router(skills.router, prefix="/skills", tags=["skills"])
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_skills.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add skills router with full CRUD"
```

---

## Task 7: Implement Crons Router

**Files:**
- Create: `src/picklebot/api/routers/crons.py`
- Test: `tests/api/test_crons.py`

**Step 1: Write the failing tests**

Create `tests/api/test_crons.py`:
```python
"""Tests for crons API router."""

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        crons_path = workspace / "crons"
        crons_path.mkdir()

        # Create a test cron
        test_cron_dir = crons_path / "test-cron"
        test_cron_dir.mkdir()
        (test_cron_dir / "CRON.md").write_text("""---
name: Test Cron
agent: pickle
schedule: "0 * * * *"
---
Check for updates.
""")

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListCrons:
    def test_list_crons_returns_crons(self, client):
        """GET /crons returns list of crons."""
        response = client.get("/crons")

        assert response.status_code == 200
        crons = response.json()
        assert len(crons) == 1
        assert crons[0]["id"] == "test-cron"


class TestGetCron:
    def test_get_cron_returns_cron(self, client):
        """GET /crons/{id} returns cron definition."""
        response = client.get("/crons/test-cron")

        assert response.status_code == 200
        cron = response.json()
        assert cron["id"] == "test-cron"
        assert cron["name"] == "Test Cron"
        assert cron["agent"] == "pickle"

    def test_get_cron_not_found(self, client):
        """GET /crons/{id} returns 404 for non-existent cron."""
        response = client.get("/crons/nonexistent")

        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_crons.py -v`
Expected: FAIL with 404 errors

**Step 3: Create crons router**

Create `src/picklebot/api/routers/crons.py`:
```python
"""Cron resource router."""

import shutil

from fastapi import APIRouter, Depends, HTTPException, status

from picklebot.api.deps import get_context
from picklebot.api.schemas import CronCreate
from picklebot.core.context import SharedContext
from picklebot.core.cron_loader import CronDef
from picklebot.utils.def_loader import DefNotFoundError

router = APIRouter()


def _write_cron_file(cron_id: str, data: CronCreate, crons_path) -> None:
    """Write cron definition to file."""
    cron_dir = crons_path / cron_id
    cron_dir.mkdir(parents=True, exist_ok=True)

    content = f"""---
name: {data.name}
agent: {data.agent}
schedule: "{data.schedule}"
one_off: {data.one_off}
---

{data.prompt}
"""

    (cron_dir / "CRON.md").write_text(content)


@router.get("", response_model=list[CronDef])
def list_crons(ctx: SharedContext = Depends(get_context)) -> list[CronDef]:
    """List all crons."""
    return ctx.cron_loader.discover_crons()


@router.get("/{cron_id}", response_model=CronDef)
def get_cron(cron_id: str, ctx: SharedContext = Depends(get_context)) -> CronDef:
    """Get cron by ID."""
    try:
        return ctx.cron_loader.load(cron_id)
    except DefNotFoundError:
        raise HTTPException(status_code=404, detail=f"Cron not found: {cron_id}")


@router.post("/{cron_id}", response_model=CronDef, status_code=status.HTTP_201_CREATED)
def create_cron(
    cron_id: str, data: CronCreate, ctx: SharedContext = Depends(get_context)
) -> CronDef:
    """Create a new cron."""
    crons_path = ctx.config.crons_path
    cron_file = crons_path / cron_id / "CRON.md"

    if cron_file.exists():
        raise HTTPException(status_code=409, detail=f"Cron already exists: {cron_id}")

    _write_cron_file(cron_id, data, crons_path)
    return ctx.cron_loader.load(cron_id)


@router.put("/{cron_id}", response_model=CronDef)
def update_cron(
    cron_id: str, data: CronCreate, ctx: SharedContext = Depends(get_context)
) -> CronDef:
    """Update an existing cron."""
    crons_path = ctx.config.crons_path
    cron_file = crons_path / cron_id / "CRON.md"

    if not cron_file.exists():
        raise HTTPException(status_code=404, detail=f"Cron not found: {cron_id}")

    _write_cron_file(cron_id, data, crons_path)
    return ctx.cron_loader.load(cron_id)


@router.delete("/{cron_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cron(cron_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete a cron."""
    crons_path = ctx.config.crons_path
    cron_dir = crons_path / cron_id

    if not cron_dir.exists():
        raise HTTPException(status_code=404, detail=f"Cron not found: {cron_id}")

    shutil.rmtree(cron_dir)
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
from picklebot.api.routers import agents, crons, skills
# ...
app.include_router(crons.router, prefix="/crons", tags=["crons"])
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_crons.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add crons router with full CRUD"
```

---

## Task 8: Implement Sessions Router

**Files:**
- Create: `src/picklebot/api/routers/sessions.py`
- Test: `tests/api/test_sessions.py`

**Step 1: Write the failing tests**

Create `tests/api/test_sessions.py`:
```python
"""Tests for sessions API router."""

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryMessage
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        history_path = workspace / ".history"
        history_path.mkdir()

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)

        # Create a test session
        context.history_store.create_session("pickle", "test-session")
        context.history_store.save_message(
            "test-session",
            HistoryMessage(role="user", content="Hello"),
        )

        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListSessions:
    def test_list_sessions_returns_sessions(self, client):
        """GET /sessions returns list of sessions."""
        response = client.get("/sessions")

        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["id"] == "test-session"


class TestGetSession:
    def test_get_session_returns_session_with_messages(self, client):
        """GET /sessions/{id} returns session with messages."""
        response = client.get("/sessions/test-session")

        assert response.status_code == 200
        session = response.json()
        assert session["id"] == "test-session"
        assert session["agent_id"] == "pickle"
        assert len(session["messages"]) == 1
        assert session["messages"][0]["content"] == "Hello"

    def test_get_session_not_found(self, client):
        """GET /sessions/{id} returns 404 for non-existent session."""
        response = client.get("/sessions/nonexistent")

        assert response.status_code == 404


class TestDeleteSession:
    def test_delete_session(self, client):
        """DELETE /sessions/{id} deletes a session."""
        response = client.delete("/sessions/test-session")

        assert response.status_code == 204

        # Verify it was deleted
        get_response = client.get("/sessions/test-session")
        assert get_response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_sessions.py -v`
Expected: FAIL with 404 errors

**Step 3: Create sessions router**

Create `src/picklebot/api/routers/sessions.py`:
```python
"""Session resource router."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.core.context import SharedContext
from picklebot.core.history import HistoryMessage, HistorySession

router = APIRouter()


class SessionResponse(BaseModel):
    """Response model for session with messages."""

    id: str
    agent_id: str
    title: str | None
    message_count: int
    created_at: str
    updated_at: str
    messages: list[HistoryMessage]


@router.get("", response_model=list[HistorySession])
def list_sessions(ctx: SharedContext = Depends(get_context)) -> list[HistorySession]:
    """List all sessions."""
    return ctx.history_store.list_sessions()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, ctx: SharedContext = Depends(get_context)) -> dict:
    """Get session by ID with messages."""
    sessions = ctx.history_store.list_sessions()
    session = next((s for s in sessions if s.id == session_id), None)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    messages = ctx.history_store.get_messages(session_id)

    return {
        "id": session.id,
        "agent_id": session.agent_id,
        "title": session.title,
        "message_count": session.message_count,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
        "messages": messages,
    }


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete a session."""
    session_file = ctx.history_store._session_file_path(session_id)

    if not session_file.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    # Remove session file
    session_file.unlink()

    # Remove from index
    sessions = ctx.history_store._read_index()
    sessions = [s for s in sessions if s.id != session_id]
    ctx.history_store._write_index(sessions)
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
from picklebot.api.routers import agents, crons, sessions, skills
# ...
app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_sessions.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add sessions router with list/get/delete"
```

---

## Task 9: Implement Memories Router

**Files:**
- Create: `src/picklebot/api/routers/memories.py`
- Test: `tests/api/test_memories.py`

**Step 1: Write the failing tests**

Create `tests/api/test_memories.py`:
```python
"""Tests for memories API router."""

import pytest
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        memories_path = workspace / "memories"
        topics_path = memories_path / "topics"
        topics_path.mkdir(parents=True)

        # Create a test memory
        (topics_path / "preferences.md").write_text("# User Preferences\n\nLikes: Python")

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client


class TestListMemories:
    def test_list_memories_returns_files(self, client):
        """GET /memories returns list of memory files."""
        response = client.get("/memories")

        assert response.status_code == 200
        memories = response.json()
        assert "topics/preferences.md" in memories


class TestGetMemory:
    def test_get_memory_returns_content(self, client):
        """GET /memories/{path} returns memory content."""
        response = client.get("/memories/topics/preferences.md")

        assert response.status_code == 200
        memory = response.json()
        assert memory["path"] == "topics/preferences.md"
        assert "Likes: Python" in memory["content"]

    def test_get_memory_not_found(self, client):
        """GET /memories/{path} returns 404 for non-existent memory."""
        response = client.get("/memories/nonexistent.md")

        assert response.status_code == 404
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_memories.py -v`
Expected: FAIL with 404 errors

**Step 3: Create memories router**

Create `src/picklebot/api/routers/memories.py`:
```python
"""Memory resource router."""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.api.schemas import MemoryCreate
from picklebot.core.context import SharedContext

router = APIRouter()


class MemoryResponse(BaseModel):
    """Response model for memory."""

    path: str
    content: str


def _list_memory_files(memories_path: Path, base: Path = None) -> list[str]:
    """Recursively list all memory files."""
    if base is None:
        base = memories_path

    files = []
    for item in memories_path.iterdir():
        if item.is_dir():
            files.extend(_list_memory_files(item, base))
        elif item.suffix == ".md":
            files.append(str(item.relative_to(base)))

    return sorted(files)


@router.get("", response_model=list[str])
def list_memories(ctx: SharedContext = Depends(get_context)) -> list[str]:
    """List all memory files."""
    return _list_memory_files(ctx.config.memories_path)


@router.get("/{path:path}", response_model=MemoryResponse)
def get_memory(path: str, ctx: SharedContext = Depends(get_context)) -> dict:
    """Get memory content by path."""
    full_path = ctx.config.memories_path / path

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"Memory not found: {path}")

    content = full_path.read_text()
    return {"path": path, "content": content}


@router.post("/{path:path}", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(
    path: str, data: MemoryCreate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Create a new memory."""
    full_path = ctx.config.memories_path / path

    if full_path.exists():
        raise HTTPException(status_code=409, detail=f"Memory already exists: {path}")

    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(data.content)

    return {"path": path, "content": data.content}


@router.put("/{path:path}", response_model=MemoryResponse)
def update_memory(
    path: str, data: MemoryCreate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Update an existing memory."""
    full_path = ctx.config.memories_path / path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Memory not found: {path}")

    full_path.write_text(data.content)

    return {"path": path, "content": data.content}


@router.delete("/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(path: str, ctx: SharedContext = Depends(get_context)) -> None:
    """Delete a memory."""
    full_path = ctx.config.memories_path / path

    if not full_path.exists():
        raise HTTPException(status_code=404, detail=f"Memory not found: {path}")

    full_path.unlink()
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
from picklebot.api.routers import agents, crons, memories, sessions, skills
# ...
app.include_router(memories.router, prefix="/memories", tags=["memories"])
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_memories.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add memories router with full CRUD"
```

---

## Task 10: Implement Config Router

**Files:**
- Create: `src/picklebot/api/routers/config.py`
- Test: `tests/api/test_config.py`

**Step 1: Write the failing tests**

Create `tests/api/test_config.py`:
```python
"""Tests for config API router."""

import pytest
import yaml
from fastapi.testclient import TestClient

from picklebot.api import create_app
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, LLMConfig
from pathlib import Path
import tempfile


@pytest.fixture
def client():
    """Create test client with temporary workspace."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        config = Config(
            workspace=workspace,
            llm=LLMConfig(provider="openai", model="gpt-4", api_key="test-key"),
            default_agent="pickle",
        )
        context = SharedContext(config)
        app = create_app(context)

        with TestClient(app) as client:
            yield client, workspace


class TestGetConfig:
    def test_get_config_returns_config(self, client):
        """GET /config returns current config."""
        client, workspace = client
        response = client.get("/config")

        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "pickle"


class TestUpdateConfig:
    def test_update_config_updates_config(self, client):
        """PATCH /config updates config fields."""
        client, workspace = client

        response = client.patch(
            "/config",
            json={"default_agent": "cookie"},
        )

        assert response.status_code == 200
        config = response.json()
        assert config["default_agent"] == "cookie"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/api/test_config.py -v`
Expected: FAIL with 404 errors

**Step 3: Create config router**

Create `src/picklebot/api/routers/config.py`:
```python
"""Config resource router."""

import yaml
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from picklebot.api.deps import get_context
from picklebot.api.schemas import ConfigUpdate
from picklebot.core.context import SharedContext

router = APIRouter()


class ConfigResponse(BaseModel):
    """Response model for config (excludes sensitive fields)."""

    default_agent: str
    chat_max_history: int
    job_max_history: int


@router.get("", response_model=ConfigResponse)
def get_config(ctx: SharedContext = Depends(get_context)) -> dict:
    """Get current config."""
    return {
        "default_agent": ctx.config.default_agent,
        "chat_max_history": ctx.config.chat_max_history,
        "job_max_history": ctx.config.job_max_history,
    }


@router.patch("", response_model=ConfigResponse)
def update_config(
    data: ConfigUpdate, ctx: SharedContext = Depends(get_context)
) -> dict:
    """Update config fields."""
    user_config_path = ctx.config.workspace / "config.user.yaml"

    # Load existing user config or start fresh
    if user_config_path.exists():
        with open(user_config_path) as f:
            user_config = yaml.safe_load(f) or {}
    else:
        user_config = {}

    # Apply updates
    if data.default_agent is not None:
        user_config["default_agent"] = data.default_agent
    if data.chat_max_history is not None:
        user_config["chat_max_history"] = data.chat_max_history
    if data.job_max_history is not None:
        user_config["job_max_history"] = data.job_max_history

    # Write back
    with open(user_config_path, "w") as f:
        yaml.dump(user_config, f)

    return {
        "default_agent": data.default_agent or ctx.config.default_agent,
        "chat_max_history": data.chat_max_history or ctx.config.chat_max_history,
        "job_max_history": data.job_max_history or ctx.config.job_max_history,
    }
```

**Step 4: Register router in app.py**

Update `src/picklebot/api/app.py`:
```python
from picklebot.api.routers import agents, config, crons, memories, sessions, skills
# ...
app.include_router(config.router, prefix="/config", tags=["config"])
```

**Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/api/test_config.py -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add src/picklebot/api/ tests/api/
git commit -m "feat(api): add config router with get/patch"
```

---

## Task 11: Integrate API with Server

**Files:**
- Modify: `src/picklebot/server/server.py`
- Test: `tests/server/test_server.py`

**Step 1: Add imports to server.py**

Add to imports in `src/picklebot/server/server.py`:
```python
import uvicorn
```

**Step 2: Add API task to Server class**

Add to `Server.__init__`:
```python
self._api_task: asyncio.Task | None = None
```

Add method to `Server` class:
```python
async def _run_api(self) -> None:
    """Run the HTTP API server."""
    from picklebot.api import create_app

    app = create_app(self.context)
    config = uvicorn.Config(
        app,
        host=self.config.api.host,
        port=self.config.api.port,
    )
    server = uvicorn.Server(config)
    await server.serve()
```

Modify `run()` method to start API:
```python
async def run(self) -> None:
    """Start all workers and API if enabled."""
    # Start workers (existing code)
    for worker in self.workers:
        worker.start()
        self.logger.info(f"Started {worker.__class__.__name__}")

    # Start API if enabled
    if self.config.api.enabled:
        self._api_task = asyncio.create_task(self._run_api())
        self.logger.info(
            f"API server started on {self.config.api.host}:{self.config.api.port}"
        )

    # Monitor workers (existing code continues...)
```

**Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add src/picklebot/server/server.py
git commit -m "feat(server): integrate HTTP API with server"
```

---

## Task 12: Run Full Test Suite and Final Verification

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests pass

**Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors

**Step 3: Run type checker**

Run: `uv run mypy .`
Expected: No errors

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat(api): complete HTTP API implementation"
```

---

## Summary

This plan implements:
- API module structure with FastAPI
- CRUD routers for agents, skills, crons, sessions, memories, config
- Config-driven API enablement
- Server integration
