"""Shared utilities for loading definition files (agents, skills, crons)."""

from typing import Any

import yaml


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
