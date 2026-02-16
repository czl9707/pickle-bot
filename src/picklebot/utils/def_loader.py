"""Shared utilities for loading definition files (agents, skills, crons)."""

import logging
from pathlib import Path
from typing import Any, Callable, TypeVar

import yaml

T = TypeVar("T")


class DefNotFoundError(Exception):
    """Definition folder or file doesn't exist."""

    def __init__(self, kind: str, def_id: str):
        super().__init__(f"{kind.capitalize()} not found: {def_id}")
        self.kind = kind
        self.def_id = def_id


class InvalidDefError(Exception):
    """Definition file is malformed."""

    def __init__(self, kind: str, def_id: str, reason: str):
        super().__init__(f"Invalid {kind} '{def_id}': {reason}")
        self.kind = kind
        self.def_id = def_id
        self.reason = reason


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Parse YAML frontmatter + markdown body.

    Args:
        content: Raw file content

    Returns:
        Tuple of (frontmatter dict, body string)
    """
    # Check if content starts with frontmatter delimiter
    if not content.startswith("---\n"):
        return {}, content

    # Split on the first two occurrences of "---\n"
    # We need to find the closing delimiter
    delimiter = "---\n"
    first_delim = len(delimiter)

    # Find the second delimiter
    second_delim_pos = content.find(delimiter, first_delim)

    if second_delim_pos == -1:
        # No closing delimiter found
        return {}, content

    # Extract frontmatter (between first and second delimiter)
    frontmatter_text = content[first_delim:second_delim_pos]

    # Extract body (after second delimiter)
    body_start = second_delim_pos + len(delimiter)
    body = content[body_start:]

    # Parse YAML
    frontmatter = yaml.safe_load(frontmatter_text) or {}

    return frontmatter, body


def discover_definitions(
    path: Path,
    filename: str,
    parse_metadata: Callable[[str, dict[str, Any], str], T | None],
    logger: logging.Logger,
) -> list[T]:
    """
    Scan directory for definition files.

    Args:
        path: Directory containing definition folders
        filename: File to look for (e.g., "AGENT.md", "SKILL.md")
        parse_metadata: Callback(def_id, frontmatter, body) -> Metadata or None
        logger: For warnings on missing/invalid files

    Returns:
        List of metadata objects from successful parses
    """
    if not path.exists():
        logger.warning(f"Definitions directory not found: {path}")
        return []

    results = []
    for def_dir in path.iterdir():
        if not def_dir.is_dir():
            continue

        def_file = def_dir / filename
        if not def_file.exists():
            logger.warning(f"No {filename} found in {def_dir.name}")
            continue

        try:
            content = def_file.read_text()
            frontmatter, body = parse_frontmatter(content)
            metadata = parse_metadata(def_dir.name, frontmatter, body)
            if metadata is not None:
                results.append(metadata)
        except Exception as e:
            logger.warning(f"Failed to parse {def_dir.name}: {e}")
            continue

    return results
