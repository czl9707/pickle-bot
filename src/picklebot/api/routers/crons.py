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
