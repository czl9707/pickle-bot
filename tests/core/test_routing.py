# tests/core/test_routing.py

from picklebot.core.routing import Binding


def test_binding_compiles_pattern():
    """Binding should compile value into regex pattern."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.pattern.match("telegram:123456")
    assert not binding.pattern.match("telegram:789")


def test_binding_tier_literal():
    """Literal strings should be tier 0 (most specific)."""
    binding = Binding(agent="pickle", value="telegram:123456")

    assert binding.tier == 0


def test_binding_tier_specific_regex():
    """Specific regex patterns should be tier 1."""
    binding = Binding(agent="pickle", value="telegram:[0-9]+")

    assert binding.tier == 1


def test_binding_tier_wildcard():
    """Wildcard patterns (.*) should be tier 2 (least specific)."""
    binding = Binding(agent="pickle", value="telegram:.*")

    assert binding.tier == 2


def test_binding_tier_catch_all():
    """Catch-all pattern should be tier 2."""
    binding = Binding(agent="pickle", value=".*")

    assert binding.tier == 2


def test_binding_matches_full_string():
    """Pattern should match full string (anchored)."""
    binding = Binding(agent="pickle", value="telegram:123")

    assert binding.pattern.match("telegram:123")
    assert not binding.pattern.match("telegram:123456")  # extra chars
