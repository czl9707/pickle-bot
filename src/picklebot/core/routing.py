# src/picklebot/core/routing.py

import re
from dataclasses import dataclass, field
from re import Pattern


@dataclass
class Binding:
    """A routing binding that matches sources to agents."""

    agent: str
    value: str
    tier: int = field(init=False)
    pattern: Pattern = field(init=False)

    def __post_init__(self):
        self.pattern = re.compile(f"^{self.value}$")
        self.tier = self._compute_tier()

    def _compute_tier(self) -> int:
        """
        Compute specificity tier.

        0 = exact literal (no regex special chars)
        1 = specific regex (anchors, character classes)
        2 = wildcard (. or .*)
        """
        if not any(c in self.value for c in r".*+?[]()|^$"):
            return 0
        if ".*" in self.value:
            return 2
        return 1
