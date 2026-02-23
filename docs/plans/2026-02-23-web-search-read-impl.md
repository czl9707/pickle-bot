# Web Search & Web Read Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add websearch and webread built-in tools with provider abstraction pattern.

**Architecture:** Provider abstraction similar to LLM provider pattern. WebSearchProvider and WebReadProvider base classes with from_config factory. Brave Search API for search, Crawl4AI for reading. Tools use factory pattern capturing context in closure.

**Tech Stack:** httpx (Brave API), crawl4ai (web crawling), Pydantic (config)

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add httpx and crawl4ai dependencies**

Add to dependencies list in `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...
    "httpx>=0.27.0",
    "crawl4ai>=0.4.0",
]
```

**Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add httpx and crawl4ai dependencies"
```

---

## Task 2: Add Config Models

**Files:**
- Modify: `src/picklebot/utils/config.py`
- Create: `tests/test_config_web.py`

**Step 1: Write the failing test**

Create `tests/test_config_web.py`:

```python
"""Tests for websearch and webread config models."""

import pytest
from pydantic import ValidationError

from picklebot.utils.config import Config, WebSearchConfig, WebReadConfig


class TestWebSearchConfig:
    """Tests for WebSearchConfig model."""

    def test_websearch_config_with_api_key(self):
        """WebSearchConfig should accept api_key."""
        config = WebSearchConfig(provider="brave", api_key="test-key")
        assert config.provider == "brave"
        assert config.api_key == "test-key"

    def test_websearch_config_requires_api_key(self):
        """WebSearchConfig should require api_key."""
        with pytest.raises(ValidationError):
            WebSearchConfig(provider="brave")

    def test_websearch_config_default_provider(self):
        """WebSearchConfig should default provider to brave."""
        config = WebSearchConfig(api_key="test-key")
        assert config.provider == "brave"


class TestWebReadConfig:
    """Tests for WebReadConfig model."""

    def test_webread_config_defaults(self):
        """WebReadConfig should default provider to crawl4ai."""
        config = WebReadConfig()
        assert config.provider == "crawl4ai"


class TestConfigWithWeb:
    """Tests for Config with websearch/webread fields."""

    def test_config_with_websearch(self, test_config):
        """Config should accept websearch field."""
        assert test_config.websearch is None

    def test_config_with_webread(self, test_config):
        """Config should accept webread field."""
        assert test_config.webread is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_web.py -v`
Expected: FAIL - cannot import WebSearchConfig, WebReadConfig

**Step 3: Add config models**

In `src/picklebot/utils/config.py`, add imports and models:

```python
# Add to imports section
from pydantic import BaseModel

# Add new model classes (before Config class)
class WebSearchConfig(BaseModel):
    """Configuration for web search provider."""

    provider: str = "brave"
    api_key: str


class WebReadConfig(BaseModel):
    """Configuration for web read provider."""

    provider: str = "crawl4ai"
```

Then add fields to `Config` class:

```python
# In Config class, add fields:
class Config(BaseModel):
    # ... existing fields ...

    # Web capabilities (optional)
    websearch: WebSearchConfig | None = None
    webread: WebReadConfig | None = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_web.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/utils/config.py tests/test_config_web.py
git commit -m "feat(config): add WebSearchConfig and WebReadConfig models"
```

---

## Task 3: Create WebSearchProvider Base

**Files:**
- Create: `src/picklebot/provider/web_search/__init__.py`
- Create: `src/picklebot/provider/web_search/base.py`
- Create: `tests/provider/test_web_search_base.py`

**Step 1: Write the failing test**

Create `tests/provider/test_web_search_base.py`:

```python
"""Tests for WebSearchProvider base class."""

import pytest

from picklebot.provider.web_search.base import SearchResult, WebSearchProvider
from picklebot.utils.config import Config


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_search_result_creation(self):
        """SearchResult should create with all fields."""
        result = SearchResult(
            title="Example",
            url="https://example.com",
            snippet="A description",
        )
        assert result.title == "Example"
        assert result.url == "https://example.com"
        assert result.snippet == "A description"


class TestWebSearchProvider:
    """Tests for WebSearchProvider abstract class."""

    def test_cannot_instantiate_abstract(self):
        """WebSearchProvider should not be instantiable directly."""
        with pytest.raises(TypeError):
            WebSearchProvider()

    def test_from_config_raises_for_unknown_provider(self, test_config):
        """from_config should raise ValueError for unknown provider."""
        test_config.websearch = type("obj", (object,), {"provider": "unknown"})()
        with pytest.raises(ValueError, match="Unknown websearch provider"):
            WebSearchProvider.from_config(test_config)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/provider/test_web_search_base.py -v`
Expected: FAIL - module not found

**Step 3: Create provider directory and base class**

Create `src/picklebot/provider/web_search/__init__.py`:

```python
"""Web search provider module."""

from .base import SearchResult, WebSearchProvider

__all__ = ["SearchResult", "WebSearchProvider"]
```

Create `src/picklebot/provider/web_search/base.py`:

```python
"""Base class for web search providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class SearchResult(BaseModel):
    """Normalized search result from any provider."""

    title: str
    url: str
    snippet: str


class WebSearchProvider(ABC):
    """Abstract base class for web search providers."""

    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        """Search the web and return normalized results.

        Args:
            query: The search query string

        Returns:
            List of normalized SearchResult objects
        """
        pass

    @staticmethod
    def from_config(config: "Config") -> "WebSearchProvider":
        """Factory method to create provider from config.

        Args:
            config: Application config with websearch settings

        Returns:
            Configured WebSearchProvider instance

        Raises:
            ValueError: If provider is unknown
        """
        if config.websearch is None:
            raise ValueError("Websearch not configured")

        match config.websearch.provider:
            case "brave":
                from .brave import BraveSearchProvider

                return BraveSearchProvider.from_config(config)
            case _:
                raise ValueError(
                    f"Unknown websearch provider: {config.websearch.provider}"
                )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/provider/test_web_search_base.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/provider/web_search/ tests/provider/test_web_search_base.py
git commit -m "feat(provider): add WebSearchProvider base class"
```

---

## Task 4: Create BraveSearchProvider

**Files:**
- Create: `src/picklebot/provider/web_search/brave.py`
- Create: `tests/provider/test_brave_search.py`

**Step 1: Write the failing test**

Create `tests/provider/test_brave_search.py`:

```python
"""Tests for BraveSearchProvider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from picklebot.provider.web_search.brave import BraveSearchProvider
from picklebot.provider.web_search.base import SearchResult
from picklebot.utils.config import Config, WebSearchConfig


class TestBraveSearchProvider:
    """Tests for BraveSearchProvider."""

    def test_init(self):
        """BraveSearchProvider should store api_key."""
        provider = BraveSearchProvider(api_key="test-key")
        assert provider.api_key == "test-key"

    def test_from_config(self, test_config):
        """from_config should create provider from config."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        provider = BraveSearchProvider.from_config(test_config)
        assert isinstance(provider, BraveSearchProvider)
        assert provider.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_search_returns_normalized_results(self):
        """search should return list of SearchResult."""
        provider = BraveSearchProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "web": {
                "results": [
                    {
                        "title": "Example Title",
                        "url": "https://example.com",
                        "description": "Example description",
                    },
                    {
                        "title": "Another Title",
                        "url": "https://another.com",
                        "description": "Another description",
                    },
                ]
            }
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            results = await provider.search("test query")

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].title == "Example Title"
        assert results[0].url == "https://example.com"
        assert results[0].snippet == "Example description"

    @pytest.mark.asyncio
    async def test_search_handles_empty_results(self):
        """search should return empty list when no results."""
        provider = BraveSearchProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.json.return_value = {"web": {"results": []}}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            results = await provider.search("test query")

        assert results == []
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/provider/test_brave_search.py -v`
Expected: FAIL - module not found

**Step 3: Implement BraveSearchProvider**

Create `src/picklebot/provider/web_search/brave.py`:

```python
"""Brave Search API provider."""

from typing import TYPE_CHECKING
import httpx

from .base import WebSearchProvider, SearchResult

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class BraveSearchProvider(WebSearchProvider):
    """Web search provider using Brave Search API."""

    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        """Initialize Brave Search provider.

        Args:
            api_key: Brave Search API key
        """
        self.api_key = api_key

    @staticmethod
    def from_config(config: "Config") -> "BraveSearchProvider":
        """Create provider from config.

        Args:
            config: Application config

        Returns:
            Configured BraveSearchProvider
        """
        return BraveSearchProvider(api_key=config.websearch.api_key)

    async def search(self, query: str) -> list[SearchResult]:
        """Search the web using Brave Search API.

        Args:
            query: Search query string

        Returns:
            List of normalized search results

        Raises:
            httpx.HTTPStatusError: If API request fails
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.BASE_URL,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self.api_key,
                },
                params={
                    "q": query,
                    "count": 10,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        results = []
        for item in data.get("web", {}).get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                )
            )

        return results
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/provider/test_brave_search.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/provider/web_search/brave.py tests/provider/test_brave_search.py
git commit -m "feat(provider): add BraveSearchProvider implementation"
```

---

## Task 5: Create WebReadProvider Base

**Files:**
- Create: `src/picklebot/provider/web_read/__init__.py`
- Create: `src/picklebot/provider/web_read/base.py`
- Create: `tests/provider/test_web_read_base.py`

**Step 1: Write the failing test**

Create `tests/provider/test_web_read_base.py`:

```python
"""Tests for WebReadProvider base class."""

import pytest

from picklebot.provider.web_read.base import ReadResult, WebReadProvider


class TestReadResult:
    """Tests for ReadResult model."""

    def test_read_result_creation(self):
        """ReadResult should create with all fields."""
        result = ReadResult(
            url="https://example.com",
            title="Example",
            content="# Content\n\nSome text",
        )
        assert result.url == "https://example.com"
        assert result.title == "Example"
        assert result.content == "# Content\n\nSome text"
        assert result.error is None

    def test_read_result_with_error(self):
        """ReadResult should accept error field."""
        result = ReadResult(
            url="https://example.com",
            title="",
            content="",
            error="Failed to fetch",
        )
        assert result.error == "Failed to fetch"


class TestWebReadProvider:
    """Tests for WebReadProvider abstract class."""

    def test_cannot_instantiate_abstract(self):
        """WebReadProvider should not be instantiable directly."""
        with pytest.raises(TypeError):
            WebReadProvider()

    def test_from_config_raises_for_unknown_provider(self, test_config):
        """from_config should raise ValueError for unknown provider."""
        test_config.webread = type("obj", (object,), {"provider": "unknown"})()
        with pytest.raises(ValueError, match="Unknown webread provider"):
            WebReadProvider.from_config(test_config)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/provider/test_web_read_base.py -v`
Expected: FAIL - module not found

**Step 3: Create provider directory and base class**

Create `src/picklebot/provider/web_read/__init__.py`:

```python
"""Web read provider module."""

from .base import ReadResult, WebReadProvider

__all__ = ["ReadResult", "WebReadProvider"]
```

Create `src/picklebot/provider/web_read/base.py`:

```python
"""Base class for web read providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class ReadResult(BaseModel):
    """Normalized result from reading a web page."""

    url: str
    title: str
    content: str  # Markdown content
    error: str | None = None


class WebReadProvider(ABC):
    """Abstract base class for web page reading providers."""

    @abstractmethod
    async def read(self, url: str) -> ReadResult:
        """Read a web page and return normalized content.

        Args:
            url: The URL to read

        Returns:
            ReadResult with markdown content or error
        """
        pass

    @staticmethod
    def from_config(config: "Config") -> "WebReadProvider":
        """Factory method to create provider from config.

        Args:
            config: Application config with webread settings

        Returns:
            Configured WebReadProvider instance

        Raises:
            ValueError: If provider is unknown
        """
        if config.webread is None:
            raise ValueError("Webread not configured")

        match config.webread.provider:
            case "crawl4ai":
                from .crawl4ai import Crawl4AIProvider

                return Crawl4AIProvider.from_config(config)
            case _:
                raise ValueError(
                    f"Unknown webread provider: {config.webread.provider}"
                )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/provider/test_web_read_base.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/provider/web_read/ tests/provider/test_web_read_base.py
git commit -m "feat(provider): add WebReadProvider base class"
```

---

## Task 6: Create Crawl4AIProvider

**Files:**
- Create: `src/picklebot/provider/web_read/crawl4ai.py`
- Create: `tests/provider/test_crawl4ai.py`

**Step 1: Write the failing test**

Create `tests/provider/test_crawl4ai.py`:

```python
"""Tests for Crawl4AIProvider."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from picklebot.provider.web_read.crawl4ai import Crawl4AIProvider
from picklebot.provider.web_read.base import ReadResult


class TestCrawl4AIProvider:
    """Tests for Crawl4AIProvider."""

    def test_init(self):
        """Crawl4AIProvider should initialize without args."""
        provider = Crawl4AIProvider()
        assert provider is not None

    def test_from_config(self, test_config):
        """from_config should create provider from config."""
        provider = Crawl4AIProvider.from_config(test_config)
        assert isinstance(provider, Crawl4AIProvider)

    @pytest.mark.asyncio
    async def test_read_returns_markdown(self):
        """read should return ReadResult with markdown content."""
        provider = Crawl4AIProvider()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.markdown = "# Example Page\n\nThis is content."
        mock_result.metadata = {"title": "Example Page"}
        mock_result.error_message = None

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert isinstance(result, ReadResult)
        assert result.url == "https://example.com"
        assert result.title == "Example Page"
        assert result.content == "# Example Page\n\nThis is content."
        assert result.error is None

    @pytest.mark.asyncio
    async def test_read_handles_failure(self):
        """read should return error on failure."""
        provider = Crawl4AIProvider()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Failed to load page"

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(return_value=mock_result)
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert result.error == "Failed to load page"
        assert result.content == ""

    @pytest.mark.asyncio
    async def test_read_handles_exception(self):
        """read should catch and return exceptions."""
        provider = Crawl4AIProvider()

        mock_crawler = AsyncMock()
        mock_crawler.arun = AsyncMock(side_effect=Exception("Network error"))
        mock_crawler.__aenter__ = AsyncMock(return_value=mock_crawler)
        mock_crawler.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "picklebot.provider.web_read.crawl4ai.AsyncWebCrawler",
            return_value=mock_crawler,
        ):
            result = await provider.read("https://example.com")

        assert "Network error" in result.error
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/provider/test_crawl4ai.py -v`
Expected: FAIL - module not found

**Step 3: Implement Crawl4AIProvider**

Create `src/picklebot/provider/web_read/crawl4ai.py`:

```python
"""Crawl4AI provider for web page reading."""

from typing import TYPE_CHECKING
from crawl4ai import AsyncWebCrawler

from .base import WebReadProvider, ReadResult

if TYPE_CHECKING:
    from picklebot.utils.config import Config


class Crawl4AIProvider(WebReadProvider):
    """Web read provider using Crawl4AI."""

    def __init__(self):
        """Initialize Crawl4AI provider."""
        pass

    @staticmethod
    def from_config(config: "Config") -> "Crawl4AIProvider":
        """Create provider from config.

        Args:
            config: Application config

        Returns:
            Crawl4AIProvider instance
        """
        return Crawl4AIProvider()

    async def read(self, url: str) -> ReadResult:
        """Read a web page using Crawl4AI.

        Args:
            url: URL to read

        Returns:
            ReadResult with markdown content or error
        """
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url)

                if not result.success:
                    return ReadResult(
                        url=url,
                        title="",
                        content="",
                        error=result.error_message or "Failed to crawl page",
                    )

                return ReadResult(
                    url=url,
                    title=(
                        result.metadata.get("title", "")
                        if result.metadata
                        else ""
                    ),
                    content=result.markdown or "",
                    error=None,
                )
        except Exception as e:
            return ReadResult(
                url=url,
                title="",
                content="",
                error=str(e),
            )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/provider/test_crawl4ai.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/provider/web_read/crawl4ai.py tests/provider/test_crawl4ai.py
git commit -m "feat(provider): add Crawl4AIProvider implementation"
```

---

## Task 7: Create Websearch Tool

**Files:**
- Create: `src/picklebot/tools/websearch_tool.py`
- Create: `tests/tools/test_websearch_tool.py`

**Step 1: Write the failing test**

Create `tests/tools/test_websearch_tool.py`:

```python
"""Tests for websearch tool."""

import pytest
from unittest.mock import AsyncMock, patch

from picklebot.tools.websearch_tool import create_websearch_tool
from picklebot.provider.web_search.base import SearchResult
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, WebSearchConfig


class TestCreateWebsearchTool:
    """Tests for create_websearch_tool factory."""

    def test_creates_tool(self, test_config):
        """Factory should create a tool."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        context = SharedContext(config=test_config)

        tool = create_websearch_tool(context)

        assert tool is not None
        assert tool.__name__ == "websearch"

    def test_tool_has_correct_schema(self, test_config):
        """Tool should have correct name and parameters."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        context = SharedContext(config=test_config)

        tool = create_websearch_tool(context)

        # Check tool is registered correctly
        assert hasattr(tool, "__tool_name__")
        assert tool.__tool_name__ == "websearch"


class TestWebsearchToolExecution:
    """Tests for websearch tool execution."""

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self, test_config):
        """Tool should return formatted markdown results."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        context = SharedContext(config=test_config)

        mock_results = [
            SearchResult(
                title="Example",
                url="https://example.com",
                snippet="A description",
            ),
            SearchResult(
                title="Another",
                url="https://another.com",
                snippet="Another description",
            ),
        ]

        with patch(
            "picklebot.tools.websearch_tool.WebSearchProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.search = AsyncMock(return_value=mock_results)
            mock_from_config.return_value = mock_provider

            tool = create_websearch_tool(context)
            result = await tool("test query")

        assert "Example" in result
        assert "https://example.com" in result
        assert "Another" in result
        assert "https://another.com" in result

    @pytest.mark.asyncio
    async def test_returns_no_results_message(self, test_config):
        """Tool should return message when no results found."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        context = SharedContext(config=test_config)

        with patch(
            "picklebot.tools.websearch_tool.WebSearchProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.search = AsyncMock(return_value=[])
            mock_from_config.return_value = mock_provider

            tool = create_websearch_tool(context)
            result = await tool("test query")

        assert result == "No results found."
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_websearch_tool.py -v`
Expected: FAIL - module not found

**Step 3: Implement websearch tool**

Create `src/picklebot/tools/websearch_tool.py`:

```python
"""Websearch tool factory."""

from typing import TYPE_CHECKING

from picklebot.tools.base import BaseTool, tool

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


def create_websearch_tool(context: "SharedContext") -> BaseTool:
    """Factory to create websearch tool with injected context.

    Args:
        context: SharedContext for accessing config

    Returns:
        Tool function for web search
    """

    @tool(
        name="websearch",
        description=(
            "Search the web for information. "
            "Returns a list of results with titles, URLs, and snippets."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    )
    async def websearch(query: str) -> str:
        """Search the web and return formatted results.

        Args:
            query: The search query string

        Returns:
            Formatted markdown string with search results
        """
        from picklebot.provider.web_search import WebSearchProvider

        provider = WebSearchProvider.from_config(context.config)
        results = await provider.search(query)

        if not results:
            return "No results found."

        output = []
        for i, r in enumerate(results, 1):
            output.append(
                f"{i}. **{r.title}**\n   {r.url}\n   {r.snippet}"
            )
        return "\n\n".join(output)

    return websearch
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_websearch_tool.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/websearch_tool.py tests/tools/test_websearch_tool.py
git commit -m "feat(tools): add websearch tool"
```

---

## Task 8: Create Webread Tool

**Files:**
- Create: `src/picklebot/tools/webread_tool.py`
- Create: `tests/tools/test_webread_tool.py`

**Step 1: Write the failing test**

Create `tests/tools/test_webread_tool.py`:

```python
"""Tests for webread tool."""

import pytest
from unittest.mock import AsyncMock, patch

from picklebot.tools.webread_tool import create_webread_tool
from picklebot.provider.web_read.base import ReadResult
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, WebReadConfig


class TestCreateWebreadTool:
    """Tests for create_webread_tool factory."""

    def test_creates_tool(self, test_config):
        """Factory should create a tool."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        tool = create_webread_tool(context)

        assert tool is not None
        assert tool.__name__ == "webread"

    def test_tool_has_correct_schema(self, test_config):
        """Tool should have correct name and parameters."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        tool = create_webread_tool(context)

        assert hasattr(tool, "__tool_name__")
        assert tool.__tool_name__ == "webread"


class TestWebreadToolExecution:
    """Tests for webread tool execution."""

    @pytest.mark.asyncio
    async def test_returns_markdown_content(self, test_config):
        """Tool should return markdown content."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        mock_result = ReadResult(
            url="https://example.com",
            title="Example Page",
            content="# Example\n\nThis is content.",
        )

        with patch(
            "picklebot.tools.webread_tool.WebReadProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.read = AsyncMock(return_value=mock_result)
            mock_from_config.return_value = mock_provider

            tool = create_webread_tool(context)
            result = await tool("https://example.com")

        assert "Example Page" in result
        assert "# Example" in result
        assert "This is content." in result

    @pytest.mark.asyncio
    async def test_returns_error_message(self, test_config):
        """Tool should return error message on failure."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        mock_result = ReadResult(
            url="https://example.com",
            title="",
            content="",
            error="Failed to load page",
        )

        with patch(
            "picklebot.tools.webread_tool.WebReadProvider.from_config"
        ) as mock_from_config:
            mock_provider = AsyncMock()
            mock_provider.read = AsyncMock(return_value=mock_result)
            mock_from_config.return_value = mock_provider

            tool = create_webread_tool(context)
            result = await tool("https://example.com")

        assert "Error reading" in result
        assert "Failed to load page" in result
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/tools/test_webread_tool.py -v`
Expected: FAIL - module not found

**Step 3: Implement webread tool**

Create `src/picklebot/tools/webread_tool.py`:

```python
"""Webread tool factory."""

from typing import TYPE_CHECKING

from picklebot.tools.base import BaseTool, tool

if TYPE_CHECKING:
    from picklebot.core.context import SharedContext


def create_webread_tool(context: "SharedContext") -> BaseTool:
    """Factory to create webread tool with injected context.

    Args:
        context: SharedContext for accessing config

    Returns:
        Tool function for web page reading
    """

    @tool(
        name="webread",
        description=(
            "Read and extract content from a web page. "
            "Returns the page content as markdown."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to read",
                }
            },
            "required": ["url"],
        },
    )
    async def webread(url: str) -> str:
        """Read a web page and return markdown content.

        Args:
            url: The URL to read

        Returns:
            Markdown content of the page or error message
        """
        from picklebot.provider.web_read import WebReadProvider

        provider = WebReadProvider.from_config(context.config)
        result = await provider.read(url)

        if result.error:
            return f"Error reading {url}: {result.error}"

        return f"**{result.title}**\n\n{result.content}"

    return webread
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/tools/test_webread_tool.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/tools/webread_tool.py tests/tools/test_webread_tool.py
git commit -m "feat(tools): add webread tool"
```

---

## Task 9: Register Tools in Agent

**Files:**
- Modify: `src/picklebot/core/agent.py`
- Create: `tests/test_agent_web_tools.py`

**Step 1: Write the failing test**

Create `tests/test_agent_web_tools.py`:

```python
"""Tests for agent loading web tools."""

import pytest

from picklebot.core.agent import Agent
from picklebot.core.context import SharedContext
from picklebot.utils.config import Config, WebSearchConfig, WebReadConfig


class TestAgentWebTools:
    """Tests for agent loading web tools when configured."""

    def test_agent_loads_websearch_when_configured(self, test_config):
        """Agent should load websearch tool when config.websearch is set."""
        test_config.websearch = WebSearchConfig(
            provider="brave", api_key="test-key"
        )
        context = SharedContext(config=test_config)

        agent_def = context.agent_loader.load("pickle")
        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=agent_def.default_mode)
        tool_names = [t.__tool_name__ for t in registry._tools.values()]

        assert "websearch" in tool_names

    def test_agent_loads_webread_when_configured(self, test_config):
        """Agent should load webread tool when config.webread is set."""
        test_config.webread = WebReadConfig()
        context = SharedContext(config=test_config)

        agent_def = context.agent_loader.load("pickle")
        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=agent_def.default_mode)
        tool_names = [t.__tool_name__ for t in registry._tools.values()]

        assert "webread" in tool_names

    def test_agent_skips_websearch_when_not_configured(self, test_config):
        """Agent should not load websearch tool when not configured."""
        test_config.websearch = None
        context = SharedContext(config=test_config)

        agent_def = context.agent_loader.load("pickle")
        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=agent_def.default_mode)
        tool_names = [t.__tool_name__ for t in registry._tools.values()]

        assert "websearch" not in tool_names

    def test_agent_skips_webread_when_not_configured(self, test_config):
        """Agent should not load webread tool when not configured."""
        test_config.webread = None
        context = SharedContext(config=test_config)

        agent_def = context.agent_loader.load("pickle")
        agent = Agent(agent_def, context)

        registry = agent._build_tools(mode=agent_def.default_mode)
        tool_names = [t.__tool_name__ for t in registry._tools.values()]

        assert "webread" not in tool_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_web_tools.py -v`
Expected: FAIL - "websearch" not in tool_names

**Step 3: Register tools in agent**

In `src/picklebot/core/agent.py`:

Add imports at top:

```python
from picklebot.tools.websearch_tool import create_websearch_tool
from picklebot.tools.webread_tool import create_webread_tool
```

In `_build_tools()` method, add after subagent_tool registration (around line 71):

```python
        # Register websearch tool if configured
        if self.context.config.websearch:
            websearch_tool = create_websearch_tool(self.context)
            if websearch_tool:
                registry.register(websearch_tool)

        # Register webread tool if configured
        if self.context.config.webread:
            webread_tool = create_webread_tool(self.context)
            if webread_tool:
                registry.register(webread_tool)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_web_tools.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/picklebot/core/agent.py tests/test_agent_web_tools.py
git commit -m "feat(agent): register websearch and webread tools"
```

---

## Task 10: Run Full Test Suite

**Step 1: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS (including new tests)

**Step 2: Format and lint**

Run: `uv run black . && uv run ruff check .`
Expected: No errors

**Step 3: Final commit (if any formatting changes)**

```bash
git add -A
git commit -m "style: format and lint after web tools implementation"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Add dependencies | `pyproject.toml` |
| 2 | Add config models | `config.py`, `test_config_web.py` |
| 3 | WebSearchProvider base | `web_search/base.py`, `test_web_search_base.py` |
| 4 | BraveSearchProvider | `web_search/brave.py`, `test_brave_search.py` |
| 5 | WebReadProvider base | `web_read/base.py`, `test_web_read_base.py` |
| 6 | Crawl4AIProvider | `web_read/crawl4ai.py`, `test_crawl4ai.py` |
| 7 | websearch tool | `websearch_tool.py`, `test_websearch_tool.py` |
| 8 | webread tool | `webread_tool.py`, `test_webread_tool.py` |
| 9 | Register in agent | `agent.py`, `test_agent_web_tools.py` |
| 10 | Full test suite | - |
