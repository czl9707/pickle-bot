"""Tests for definition loader utilities."""

import logging
import tempfile
from pathlib import Path

import pytest

from picklebot.utils.def_loader import (
    DefNotFoundError,
    InvalidDefError,
    discover_definitions,
    parse_definition,
    substitute_template,
)


class TestSubstituteTemplate:
    def test_substitute_single_variable(self):
        """Replace a single {{variable}} placeholder."""
        body = "Path is: {{memories_path}}"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "Path is: /home/user/.pickle-bot/memories"

    def test_substitute_multiple_variables(self):
        """Replace multiple different placeholders."""
        body = "Workspace: {{workspace}}, Memories: {{memories_path}}"
        variables = {
            "workspace": "/home/user/.pickle-bot",
            "memories_path": "/home/user/.pickle-bot/memories",
        }

        result = substitute_template(body, variables)

        assert result == "Workspace: /home/user/.pickle-bot, Memories: /home/user/.pickle-bot/memories"

    def test_substitute_same_variable_multiple_times(self):
        """Replace same placeholder appearing multiple times."""
        body = "{{memories_path}}/topics and {{memories_path}}/projects"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "/home/user/.pickle-bot/memories/topics and /home/user/.pickle-bot/memories/projects"

    def test_missing_variable_passes_through_unchanged(self):
        """Leave unknown placeholders unchanged."""
        body = "Path: {{unknown_var}}"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "Path: {{unknown_var}}"

    def test_no_variables_returns_body_unchanged(self):
        """Return body as-is when no placeholders present."""
        body = "No templates here!"
        variables = {"memories_path": "/home/user/.pickle-bot/memories"}

        result = substitute_template(body, variables)

        assert result == "No templates here!"

    def test_empty_variables_dict(self):
        """Handle empty variables dict."""
        body = "Path: {{memories_path}}"

        result = substitute_template(body, {})

        assert result == "Path: {{memories_path}}"

    def test_substitute_overlapping_variable_names(self):
        """Handle overlapping variable names correctly (longer names first)."""
        body = "{{path}} and {{path_extra}}"
        variables = {"path": "/home", "path_extra": "/extra"}

        result = substitute_template(body, variables)

        assert result == "/home and /extra"


class TestParseDefinition:
    def test_parse_basic_frontmatter(self):
        """Parse simple YAML frontmatter and body."""
        content = "---\nname: Test\n---\nBody content here."
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {"name": "Test"}
        assert body == "Body content here."

    def test_parse_with_multiple_fields(self):
        """Parse frontmatter with multiple YAML fields."""
        content = "---\nname: Test\nversion: 1.0\nenabled: true\n---\nBody"
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {"name": "Test", "version": 1.0, "enabled": True}
        assert body == "Body"

    def test_parse_preserves_delimiter_in_body(self):
        """Preserve --- delimiters that appear in body."""
        content = "---\nname: Test\n---\nHere is --- a separator\n---\nmore content"
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {"name": "Test"}
        assert body == "Here is --- a separator\n---\nmore content"

    def test_parse_empty_frontmatter(self):
        """Handle empty frontmatter with proper delimiters."""
        content = "---\n\n---\nBody content"
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {}
        assert body == "Body content"

    def test_parse_no_frontmatter_returns_empty_dict(self):
        """Return empty dict and full content when no frontmatter."""
        content = "Just body content\nno frontmatter"
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {}
        assert body == "Just body content\nno frontmatter"

    def test_parse_empty_body(self):
        """Handle empty body after frontmatter."""
        content = "---\nname: Test\n---\n"
        frontmatter, body = parse_definition(
            content, "test-id", lambda def_id, fm, body: (fm, body)
        )

        assert frontmatter == {"name": "Test"}
        assert body == ""

    def test_def_id_passed_to_callback(self):
        """Verify def_id is passed to callback."""
        content = "---\nname: Test\n---\nBody"
        received_id = None

        def capture_id(def_id, fm, body):
            nonlocal received_id
            received_id = def_id
            return (fm, body)

        parse_definition(content, "my-custom-id", capture_id)
        assert received_id == "my-custom-id"

    def test_returns_typed_object(self):
        """Callback can return any typed object."""
        content = "---\nname: Test\nvalue: 42\n---\nBody"

        class Result:
            def __init__(self, def_id, fm, body):
                self.id = def_id
                self.name = fm.get("name")
                self.value = fm.get("value")
                self.content = body

        result = parse_definition(content, "test-id", Result)
        assert result.id == "test-id"
        assert result.name == "Test"
        assert result.value == 42
        assert result.content == "Body"


class TestDefNotFoundError:
    def test_error_message_format(self):
        """Error message uses capitalized kind."""
        error = DefNotFoundError("agent", "my-agent")

        assert str(error) == "Agent not found: my-agent"
        assert error.kind == "agent"
        assert error.def_id == "my-agent"

    def test_error_message_with_cron_kind(self):
        """Error message works with cron kind."""
        error = DefNotFoundError("cron", "daily-task")

        assert str(error) == "Cron not found: daily-task"


class TestInvalidDefError:
    def test_error_message_format(self):
        """Error message includes reason."""
        error = InvalidDefError("skill", "my-skill", "missing required field: name")

        assert str(error) == "Invalid skill 'my-skill': missing required field: name"
        assert error.kind == "skill"
        assert error.def_id == "my-skill"
        assert error.reason == "missing required field: name"


class TestDiscoverDefinitions:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def logger(self):
        return logging.getLogger("test")

    def test_discovers_valid_definitions(self, temp_dir):
        """Discover definitions from valid files."""
        # Create skill1/SKILL.md
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent 1")

        # Create skill2/SKILL.md
        skill2 = temp_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("---\nname: Skill Two\n---\nContent 2")

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill)

        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"Skill One", "Skill Two"}

    def test_skips_directories_without_definition_file(self, temp_dir):
        """Skip directories that don't have the definition file."""
        # Valid definition
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        # Directory without SKILL.md
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"

    def test_skips_invalid_definitions_via_callback_returning_none(self, temp_dir):
        """Skip definitions when parse callback returns None."""
        # Valid definition
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        # Invalid definition (missing name)
        skill2 = temp_dir / "skill2"
        skill2.mkdir()
        (skill2 / "SKILL.md").write_text("---\n---\nContent")

        def parse_skill(def_id, fm, body):
            if "name" not in fm:
                return None
            return {"id": def_id, "name": fm["name"]}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"

    def test_returns_empty_list_for_nonexistent_path(self, temp_dir):
        """Return empty list when path doesn't exist."""
        nonexistent = temp_dir / "nonexistent"

        def parse(def_id, fm, body):
            return {"id": def_id}

        results = discover_definitions(nonexistent, "SKILL.md", parse)

        assert results == []

    def test_ignores_files_in_root_directory(self, temp_dir):
        """Only process subdirectories, not files in root."""
        # File in root (should be ignored)
        (temp_dir / "SKILL.md").write_text("---\nname: Root\n---\nContent")

        # Valid definition in subdirectory
        skill1 = temp_dir / "skill1"
        skill1.mkdir()
        (skill1 / "SKILL.md").write_text("---\nname: Skill One\n---\nContent")

        def parse_skill(def_id, fm, body):
            return {"id": def_id, "name": fm.get("name")}

        results = discover_definitions(temp_dir, "SKILL.md", parse_skill)

        assert len(results) == 1
        assert results[0]["id"] == "skill1"
