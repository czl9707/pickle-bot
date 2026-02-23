# Web Tools Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add web search and web read configuration to the onboarding wizard with checkbox selection.

**Architecture:** Insert a new `configure_web_tools()` method into the onboarding flow after LLM config. Uses questionary checkbox for tool selection, with a helper method for websearch API key collection.

**Tech Stack:** Python, questionary, pytest, existing onboarding patterns

---

### Task 1: Test `configure_web_tools` with no selection

**Files:**
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

Add to `tests/cli/test_onboarding.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from picklebot.cli.onboarding import OnboardingWizard


class TestConfigureWebTools:
    """Tests for web tools onboarding configuration."""

    def test_configure_web_tools_none(self, tmp_path: Path, monkeypatch):
        """User selects nothing - no web tools in state."""
        wizard = OnboardingWizard(workspace=tmp_path)

        # Mock checkbox to return empty selection
        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=[])))
        )

        wizard.configure_web_tools()

        assert "websearch" not in wizard.state
        assert "webread" not in wizard.state
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools::test_configure_web_tools_none -v`
Expected: FAIL with "AttributeError: 'OnboardingWizard' object has no attribute 'configure_web_tools'"

---

### Task 2: Implement `configure_web_tools` empty selection case

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`

**Step 1: Write minimal implementation**

Add to `src/picklebot/cli/onboarding.py` after the `configure_llm` method:

```python
    def configure_web_tools(self) -> None:
        """Prompt user for web search and web read configuration."""
        selected = (
            questionary.checkbox(
                "Select web tools to enable:",
                choices=[
                    questionary.Choice(
                        "websearch (Brave Search API)", value="websearch"
                    ),
                    questionary.Choice("webread (local web scraping)", value="webread"),
                ],
            ).ask()
            or []
        )

        if "websearch" in selected:
            config = self._configure_websearch()
            if config:
                self.state["websearch"] = config

        if "webread" in selected:
            self.state["webread"] = {"provider": "crawl4ai"}
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools::test_configure_web_tools_none -v`
Expected: PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat(onboarding): add configure_web_tools method skeleton"
```

---

### Task 3: Test websearch only with valid API key

**Files:**
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the failing test**

Add to `TestConfigureWebTools` class:

```python
    def test_configure_web_tools_websearch_only(self, tmp_path: Path, monkeypatch):
        """User selects websearch with valid API key."""
        wizard = OnboardingWizard(workspace=tmp_path)

        # Mock checkbox to return websearch only
        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=["websearch"])))
        )
        # Mock text input for API key
        monkeypatch.setattr(
            "questionary.text",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value="test-api-key")))
        )

        wizard.configure_web_tools()

        assert wizard.state["websearch"] == {
            "provider": "brave",
            "api_key": "test-api-key",
        }
        assert "webread" not in wizard.state
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools::test_configure_web_tools_websearch_only -v`
Expected: FAIL with "AttributeError: 'OnboardingWizard' object has no attribute '_configure_websearch'"

---

### Task 4: Implement `_configure_websearch` helper method

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`

**Step 1: Write the implementation**

Add to `src/picklebot/cli/onboarding.py` after `configure_web_tools`:

```python
    def _configure_websearch(self) -> dict | None:
        """Prompt for web search configuration."""
        api_key = questionary.text("Brave Search API key:").ask()

        if not api_key:
            console = Console()
            console.print(
                "[yellow]API key is required for web search. Skipping websearch config.[/yellow]"
            )
            return None

        return {
            "provider": "brave",
            "api_key": api_key,
        }
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding.py tests/cli/test_onboarding.py
git commit -m "feat(onboarding): add _configure_websearch helper"
```

---

### Task 5: Test websearch with empty API key

**Files:**
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the test**

Add to `TestConfigureWebTools` class:

```python
    def test_configure_web_tools_websearch_empty_key(self, tmp_path: Path, monkeypatch, capsys):
        """User selects websearch but provides empty key - should skip."""
        wizard = OnboardingWizard(workspace=tmp_path)

        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=["websearch"])))
        )
        monkeypatch.setattr(
            "questionary.text",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value="")))
        )

        wizard.configure_web_tools()

        assert "websearch" not in wizard.state
        # Check warning was printed
        captured = capsys.readouterr()
        assert "Skipping websearch config" in captured.out
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools::test_configure_web_tools_websearch_empty_key -v`
Expected: PASS (already handled by implementation)

---

### Task 6: Test webread only

**Files:**
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the test**

Add to `TestConfigureWebTools` class:

```python
    def test_configure_web_tools_webread_only(self, tmp_path: Path, monkeypatch):
        """User selects webread only - no additional prompts needed."""
        wizard = OnboardingWizard(workspace=tmp_path)

        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=["webread"])))
        )

        wizard.configure_web_tools()

        assert wizard.state["webread"] == {"provider": "crawl4ai"}
        assert "websearch" not in wizard.state
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools::test_configure_web_tools_webread_only -v`
Expected: PASS

---

### Task 7: Test both tools selected

**Files:**
- Modify: `tests/cli/test_onboarding.py`

**Step 1: Write the test**

Add to `TestConfigureWebTools` class:

```python
    def test_configure_web_tools_both(self, tmp_path: Path, monkeypatch):
        """User selects both tools - configure both."""
        wizard = OnboardingWizard(workspace=tmp_path)

        monkeypatch.setattr(
            "questionary.checkbox",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value=["websearch", "webread"])))
        )
        monkeypatch.setattr(
            "questionary.text",
            MagicMock(return_value=MagicMock(ask=MagicMock(return_value="test-api-key")))
        )

        wizard.configure_web_tools()

        assert wizard.state["websearch"] == {
            "provider": "brave",
            "api_key": "test-api-key",
        }
        assert wizard.state["webread"] == {"provider": "crawl4ai"}
```

**Step 2: Run all web tools tests**

Run: `uv run pytest tests/cli/test_onboarding.py::TestConfigureWebTools -v`
Expected: All 5 PASS

**Step 3: Commit**

```bash
git add tests/cli/test_onboarding.py
git commit -m "test(onboarding): add comprehensive web tools tests"
```

---

### Task 8: Integrate into main `run()` flow

**Files:**
- Modify: `src/picklebot/cli/onboarding.py`

**Step 1: Update the run() method**

Modify `src/picklebot/cli/onboarding.py` in the `run()` method. Find these lines:

```python
        self.setup_workspace()
        self.configure_llm()
        self.copy_default_assets()
        self.configure_messagebus()
```

Change to:

```python
        self.setup_workspace()
        self.configure_llm()
        self.configure_web_tools()
        self.copy_default_assets()
        self.configure_messagebus()
```

**Step 2: Run all onboarding tests**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add src/picklebot/cli/onboarding.py
git commit -m "feat(onboarding): integrate web tools into onboarding flow"
```

---

### Task 9: Format, lint, and final verification

**Step 1: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 2: Run full test suite**

Run: `uv run pytest tests/cli/test_onboarding.py -v`
Expected: All PASS

**Step 3: Final commit if formatting changed anything**

```bash
git add -A
git commit -m "style: format and lint after web tools onboarding"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Test: no selection |
| 2 | Implement: `configure_web_tools` skeleton |
| 3 | Test: websearch only |
| 4 | Implement: `_configure_websearch` |
| 5 | Test: websearch empty key |
| 6 | Test: webread only |
| 7 | Test: both tools |
| 8 | Integrate into `run()` flow |
| 9 | Format, lint, verify |
