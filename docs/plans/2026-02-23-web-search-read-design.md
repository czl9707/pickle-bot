# Web Search & Web Read Design

**Date**: 2026-02-23
**Status**: Approved
**Author**: Design session

## Overview

Add web search and web read capabilities to pickle-bot agents as built-in tools. The implementation follows the existing provider abstraction pattern (similar to LLM) to allow swapping providers in the future.

## Goals

- Provide `websearch(query)` and `webread(url)` tools to all agents
- Abstract providers to allow future alternatives (Tavily, Serper, etc.)
- Normalize output format regardless of provider
- Configure via `config.user.yaml`

## Non-Goals

- Multiple providers in v1 (only Brave + crawl4ai)
- Combined search-and-read tool
- Retry logic or fallback providers

## Architecture

### Directory Structure

```
src/picklebot/
├── provider/
│   ├── llm/                    # Existing
│   ├── web_search/
│   │   ├── __init__.py         # Exports
│   │   ├── base.py             # WebSearchProvider ABC + SearchResult + factory
│   │   └── brave.py            # BraveSearchProvider
│   └── web_read/
│       ├── __init__.py         # Exports
│       ├── base.py             # WebReadProvider ABC + ReadResult + factory
│       └── crawl4ai.py         # Crawl4AIProvider
├── tools/
│   ├── websearch_tool.py       # create_websearch_tool factory
│   └── webread_tool.py         # create_webread_tool factory
└── utils/
    └── config.py               # WebSearchConfig, WebReadConfig
```

### Configuration

```yaml
# config.user.yaml
websearch:
  provider: brave
  api_key: ${BRAVE_API_KEY}

webread:
  provider: crawl4ai
```

```python
# Pydantic models
class WebSearchConfig(BaseModel):
    provider: str = "brave"
    api_key: str  # Required when websearch is configured

class WebReadConfig(BaseModel):
    provider: str = "crawl4ai"
```

### Provider Interfaces

```python
# provider/web_search/base.py
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str

class WebSearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[SearchResult]:
        pass

    @staticmethod
    def from_config(config: Config) -> "WebSearchProvider":
        # Factory: returns correct provider based on config
```

```python
# provider/web_read/base.py
class ReadResult(BaseModel):
    url: str
    title: str
    content: str  # Markdown
    error: str | None = None

class WebReadProvider(ABC):
    @abstractmethod
    async def read(self, url: str) -> ReadResult:
        pass

    @staticmethod
    def from_config(config: Config) -> "WebReadProvider":
        # Factory: returns correct provider based on config
```

### Tool Design

Tools use the factory pattern (like `subagent_tool`), capturing context in closure:

```python
# tools/websearch_tool.py
def create_websearch_tool(context: "SharedContext") -> BaseTool:
    @tool(
        name="websearch",
        description="Search the web for information...",
        parameters={...},
    )
    async def websearch(query: str) -> str:
        provider = WebSearchProvider.from_config(context.config)
        results = await provider.search(query)
        # Format as markdown list
        ...

    return websearch
```

```python
# tools/webread_tool.py
def create_webread_tool(context: "SharedContext") -> BaseTool:
    @tool(
        name="webread",
        description="Read and extract content from a web page...",
        parameters={...},
    )
    async def webread(url: str) -> str:
        provider = WebReadProvider.from_config(context.config)
        result = await provider.read(url)
        # Return markdown or error
        ...

    return webread
```

### Tool Registration

In `core/agent.py`, `_build_tools()` method:

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

### Provider Implementations

#### BraveSearchProvider

```python
class BraveSearchProvider(WebSearchProvider):
    BASE_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def from_config(config: Config) -> "BraveSearchProvider":
        return BraveSearchProvider(api_key=config.websearch.api_key)

    async def search(self, query: str) -> list[SearchResult]:
        # httpx call to Brave API
        # Normalize response to list[SearchResult]
```

#### Crawl4AIProvider

```python
class Crawl4AIProvider(WebReadProvider):
    @staticmethod
    def from_config(config: Config) -> "Crawl4AIProvider":
        return Crawl4AIProvider()

    async def read(self, url: str) -> ReadResult:
        # AsyncWebCrawler.arun(url)
        # Return ReadResult with markdown content
        # Handle errors gracefully
```

## Error Handling

- **Fail fast**: Return clear error message to agent immediately
- **Agent decides**: Let agent handle errors (retry, report to user, etc.)
- **No retry logic**: Keep implementation simple

## Data Flow

```
Agent calls websearch("query")
    → create_websearch_tool closure captured context
    → WebSearchProvider.from_config(config)
    → BraveSearchProvider.search(query)
    → httpx call to Brave API
    → Normalize to list[SearchResult]
    → Format as markdown string
    → Return to agent
```

```
Agent calls webread(url)
    → create_webread_tool closure captured context
    → WebReadProvider.from_config(config)
    → Crawl4AIProvider.read(url)
    → AsyncWebCrawler.arun(url)
    → Return ReadResult with markdown
    → Format as markdown string
    → Return to agent
```

## Dependencies

```toml
# pyproject.toml additions
dependencies = [
    # ... existing ...
    "httpx>=0.27.0",
    "crawl4ai>=0.4.0",
]
```

## Testing

### Unit Tests

```
tests/
├── provider/
│   ├── test_web_search.py
│   │   ├── test_search_result_model()
│   │   ├── test_brave_provider_search()
│   │   ├── test_brave_provider_from_config()
│   │   └── test_brave_provider_handles_error()
│   └── test_web_read.py
│       ├── test_read_result_model()
│       ├── test_crawl4ai_provider_read()
│       ├── test_crawl4ai_provider_from_config()
│       └── test_crawl4ai_provider_handles_error()
└── tools/
    ├── test_websearch_tool.py
    │   ├── test_create_websearch_tool()
    │   ├── test_websearch_returns_formatted_results()
    │   └── test_websearch_returns_no_results_message()
    └── test_webread_tool.py
        ├── test_create_webread_tool()
        ├── test_webread_returns_markdown()
        └── test_webread_returns_error_message()
```

### Mocking Strategy

- Mock `httpx.AsyncClient` for Brave API tests
- Mock `AsyncWebCrawler.arun()` for Crawl4AI tests
- Optional real API tests with `pytest.mark.skipif` when no API key

## Extensibility

Adding a new provider:

1. Create new file in `provider/web_search/` or `provider/web_read/`
2. Inherit from base class
3. Implement abstract method
4. Add to factory `from_config()` match statement
5. Add any new config fields if needed

Example - adding Tavily:

```python
# provider/web_search/tavily.py
class TavilySearchProvider(WebSearchProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @staticmethod
    def from_config(config: Config) -> "TavilySearchProvider":
        return TavilySearchProvider(api_key=config.websearch.api_key)

    async def search(self, query: str) -> list[SearchResult]:
        # Tavily API call + normalization
```

Update factory:

```python
@staticmethod
def from_config(config: Config) -> "WebSearchProvider":
    match config.websearch.provider:
        case "brave":
            from .brave import BraveSearchProvider
            return BraveSearchProvider.from_config(config)
        case "tavily":
            from .tavily import TavilySearchProvider
            return TavilySearchProvider.from_config(config)
        case _:
            raise ValueError(f"Unknown websearch provider: {config.websearch.provider}")
```

## Open Questions

None - design approved.

## References

- [Brave Search API Docs](https://brave.com/search/api/)
- [Crawl4AI Docs](https://github.com/unclecode/crawl4ai)
