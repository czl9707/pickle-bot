"""Tests for definition loader utilities."""

import pytest

from picklebot.utils.def_loader import parse_frontmatter


class TestParseFrontmatter:
    def test_parse_basic_frontmatter(self):
        """Parse simple YAML frontmatter and body."""
        content = "---\nname: Test\n---\nBody content here."
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == "Body content here."

    def test_parse_with_multiple_fields(self):
        """Parse frontmatter with multiple YAML fields."""
        content = "---\nname: Test\nversion: 1.0\nenabled: true\n---\nBody"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test", "version": 1.0, "enabled": True}
        assert body == "Body"

    def test_parse_preserves_delimiter_in_body(self):
        """Preserve --- delimiters that appear in body."""
        content = "---\nname: Test\n---\nHere is --- a separator\n---\nmore content"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == "Here is --- a separator\n---\nmore content"

    def test_parse_empty_frontmatter(self):
        """Handle empty frontmatter."""
        content = "---\n---\nBody content"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Body content"

    def test_parse_no_frontmatter_returns_empty_dict(self):
        """Return empty dict and full content when no frontmatter."""
        content = "Just body content\nno frontmatter"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {}
        assert body == "Just body content\nno frontmatter"

    def test_parse_empty_body(self):
        """Handle empty body after frontmatter."""
        content = "---\nname: Test\n---\n"
        frontmatter, body = parse_frontmatter(content)

        assert frontmatter == {"name": "Test"}
        assert body == ""
