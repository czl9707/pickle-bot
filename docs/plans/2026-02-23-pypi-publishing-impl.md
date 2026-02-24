# PyPI Publishing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up automated PyPI publishing with OIDC Trusted Publishing and integrated version bumping.

**Architecture:** Add PyPI metadata and bumpversion config to pyproject.toml, create GitHub workflow for manual dispatch with version bump → build → publish flow.

**Tech Stack:** uv, bump-my-version, pypa/gh-action-pypi-publish (OIDC), GitHub Actions

---

### Task 1: Update pyproject.toml with PyPI metadata

**Files:**
- Modify: `pyproject.toml:1-45`

**Step 1: Add authors, license, classifiers, and keywords to [project] section**

Add after `readme = "README.md"`:

```toml
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
```

**Step 2: Add project URLs section**

Add after the [project] section (before `[project.scripts]`):

```toml
[project.urls]
Homepage = "https://github.com/zane-chen/pickle-bot"
Repository = "https://github.com/zane-chen/pickle-bot"
Issues = "https://github.com/zane-chen/pickle-bot/issues"
```

**Step 3: Verify pyproject.toml is valid**

Run: `uv pip list`
Expected: No errors (validates TOML syntax)

**Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add PyPI metadata to pyproject.toml"
```

---

### Task 2: Add bumpversion configuration

**Files:**
- Modify: `pyproject.toml` (append at end)

**Step 1: Add [tool.bumpversion] configuration**

Append to end of `pyproject.toml`:

```toml
[tool.bumpversion]
current_version = "0.1.0"
parse = """(?x)
  (?P<major>0|[1-9]\\d*)\\.
  (?P<minor>0|[1-9]\\d*)\\.
  (?P<patch>0|[1-9]\\d*)
"""
serialize = [
  "{major}.{minor}.{patch}",
]
search = "{current_version}"
replace = "{new_version}"
regex = false
ignore_missing_version = false
ignore_missing_files = false
tag = false
allow_dirty = false
commit = true
message = "Bump version: {current_version} → {new_version}"
commit_args = ""

[[tool.bumpversion.files]]
filename = "pyproject.toml"
search = 'version = "{current_version}"'
replace = 'version = "{new_version}"'
```

**Step 2: Verify configuration is valid**

Run: `uv pip list`
Expected: No errors

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add bumpversion configuration"
```

---

### Task 3: Create GitHub workflow directory

**Files:**
- Create: `.github/workflows/`

**Step 1: Create workflow directory**

Run: `mkdir -p .github/workflows`

**Step 2: Verify directory exists**

Run: `ls -la .github/workflows`
Expected: Directory exists (may be empty)

**Step 3: Commit**

```bash
git add .github
git commit -m "chore: create .github/workflows directory"
```

---

### Task 4: Create publish workflow

**Files:**
- Create: `.github/workflows/publish.yml`

**Step 1: Create the workflow file**

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
  contents: write
  id-token: write

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

**Step 2: Validate YAML syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml'))"`
Expected: No output (valid YAML)

**Step 3: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "ci: add PyPI publish workflow with OIDC"
```

---

### Task 5: Verify package builds locally

**Files:**
- None (verification only)

**Step 1: Build the package**

Run: `uv build`
Expected: Creates `dist/` directory with `.tar.gz` and `.whl` files

**Step 2: Verify dist contents**

Run: `ls dist/`
Expected: Two files like `pickle_bot-0.1.0-py3-none-any.whl` and `pickle-bot-0.1.0.tar.gz`

**Step 3: Clean up dist (optional)**

Run: `rm -rf dist/`

---

### Task 6: Final commit and summary

**Step 1: Ensure all changes are committed**

Run: `git status`
Expected: Working tree clean

**Step 2: Push to remote**

Run: `git push origin main`

---

## Setup Checklist (Manual)

After implementing, complete these one-time setup steps:

- [ ] Create PyPI project and configure Trusted Publisher:
  - PyPI → Manage project → Publishing → Add GitHub publisher
  - Owner: your GitHub username
  - Repository: `pickle-bot`
  - Workflow: `.github/workflows/publish.yml`

- [ ] Create GitHub PAT with `repo` scope and add as `GH_TOKEN` secret

## Usage

To publish a new version:
1. Go to GitHub Actions → "Publish to PyPI" → Run workflow
2. Select release type (major/minor/patch)
3. Workflow handles: version bump → build → publish → release
