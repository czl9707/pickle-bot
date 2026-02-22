"""Memory resource router."""

from pathlib import Path
from typing import Optional

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


def _list_memory_files(memories_path: Path, base: Optional[Path] = None) -> list[str]:
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


@router.post(
    "/{path:path}", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED
)
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
