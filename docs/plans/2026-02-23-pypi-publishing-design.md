# PyPI Publishing Design

## Overview

Set up automated PyPI publishing for pickle-bot using Trusted Publishing (OIDC) with integrated version bumping.

## Approach

Hybrid approach combining:
- **OIDC Trusted Publishing** - secure, no API tokens to manage
- **Integrated version bumping** - single workflow dispatch to bump + publish

## Components

### 1. pyproject.toml Updates

Add metadata for PyPI discoverability and bumpversion configuration:

```toml
# Add to [project] section:
authors = [
    { name = "zane", email = "czl970721@gmail.com" }
]
license = { text = "MIT" }
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.13",
]
keywords = ["ai", "assistant", "llm", "chatbot"]

# Add new sections:
[project.urls]
Homepage = "https://github.com/zane-chen/pickle-bot"
Repository = "https://github.com/zane-chen/pickle-bot"
Issues = "https://github.com/zane-chen/pickle-bot/issues"

[tool.bumpversion]
current_version = "0.1.0"
parse = "(?x)\n  (?P<major>0|[1-9]\\d*)\\.\n  (?P<minor>0|[1-9]\\d*)\\.\n  (?P<patch>0|[1-9]\\d*)\n"
serialize = ["{major}.{minor}.{patch}"]
search = "{current_version}"
replace = "{new_version}"
regex = false
tag = false
allow_dirty = false
commit = true
message = "Bump version: {current_version} → {new_version}"

[[tool.bumpversion.files]]
filename = "pyproject.toml"
search = 'version = "{current_version}"'
replace = 'version = "{new_version}"'
```

### 2. GitHub Workflow

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  workflow_dispatch:
    inputs:
      release_type:
        description: "Release Type"
        required: true
        type: choice
        default: "patch"
        options:
          - major
          - minor
          - patch

permissions:
  contents: write  # For pushing commits/tags and creating releases
  id-token: write  # For OIDC authentication with PyPI

env:
  PYTHON_VERSION: "3.13"

jobs:
  publish:
    name: Build and Publish
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install Python
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Bump version
        id: bump
        uses: callowayproject/bump-my-version@master
        env:
          BUMPVERSION_TAG: "false"
        with:
          args: ${{ inputs.release_type }}
          github-token: ${{ secrets.GH_TOKEN }}

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1

      - name: Create GitHub Release
        uses: ncipollo/release-action@v1
        with:
          name: pickle-bot v${{ steps.bump.outputs.current-version }}
          tag: v${{ steps.bump.outputs.current-version }}
          body: "Release v${{ steps.bump.outputs.current-version }}"
          artifacts: dist/*
          token: ${{ secrets.GH_TOKEN }}
          generateReleaseNotes: true
```

### 3. One-Time Setup Requirements

**PyPI Trusted Publisher Configuration:**
1. Go to PyPI → Manage project → Publishing
2. Add GitHub as a trusted publisher:
   - Owner: your GitHub username/org
   - Repository: `pickle-bot`
   - Workflow: `.github/workflows/publish.yml`
   - Environment: (leave empty)

**GitHub Secret:**
- Create Personal Access Token (Classic) with `repo` scope
- Add as repository secret named `GH_TOKEN`

## Workflow Flow

```
workflow_dispatch (major/minor/patch)
  ↓
bump-my-version updates pyproject.toml + commits
  ↓
uv build creates dist/*
  ↓
pypa/gh-action-pypi-publish (OIDC) uploads to PyPI
  ↓
release-action creates GitHub Release with artifacts
```

## Usage

To publish a new version:
1. Go to Actions → "Publish to PyPI" → Run workflow
2. Select release type (major/minor/patch)
3. Workflow automatically: bumps version → builds → publishes → creates release
