"""Skill resource router."""

import shutil

from fastapi import APIRouter, Depends, HTTPException, status

from picklebot.api.deps import get_context
from picklebot.api.schemas import SkillCreate
from picklebot.core.context import SharedContext
from picklebot.core.skill_loader import SkillDef
from picklebot.utils.def_loader import DefNotFoundError, write_definition

router = APIRouter()


def _write_skill_file(skill_id: str, data: SkillCreate, skills_path) -> None:  # type: ignore[valid-type]
    """Write skill definition to file."""
    # Type ignore: SkillCreate is dynamically created
    frontmatter = {
        "name": data.name,  # type: ignore[attr-defined]
        "description": data.description,  # type: ignore[attr-defined]
    }
    body = data.content  # type: ignore[attr-defined]
    write_definition(skill_id, frontmatter, body, skills_path, "SKILL.md")


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


@router.post(
    "/{skill_id}", response_model=SkillDef, status_code=status.HTTP_201_CREATED
)
def create_skill(
    skill_id: str, data: SkillCreate, ctx: SharedContext = Depends(get_context)  # type: ignore[valid-type]
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
    skill_id: str, data: SkillCreate, ctx: SharedContext = Depends(get_context)  # type: ignore[valid-type]
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
