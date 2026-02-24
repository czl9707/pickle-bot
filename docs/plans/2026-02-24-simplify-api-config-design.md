# Simplify API Config Design

Remove redundant `enabled` field from API configuration - presence of `api` section enables it.

## Problem

Current config requires explicit `enabled: true` which is redundant:

```yaml
api:
  enabled: true      # Redundant - if section exists, user wants API
  host: "127.0.0.1"
  port: 8000
```

## Solution

Omit section to disable, include section to enable:

```yaml
# Enable API (present = enabled)
api:
  host: "127.0.0.1"
  port: 8000

# Disable API (omit section entirely)
# (no api key)
```

## Changes

| File | Change |
|------|--------|
| `src/picklebot/utils/config.py` | Remove `enabled` field from `ApiConfig`; make `api` optional in `Config` (default `None`) |
| `src/picklebot/server/server.py` | Check `if config.api:` instead of `if config.api.enabled:` |
| `src/picklebot/cli/onboarding/steps.py` | Set `state["api"] = {}` instead of `{"enabled": True}` |
| `docs/features.md` | Update example to remove `enabled` field |
| `docs/configuration.md` | Update API config section |
| `tests/utils/test_config.py` | Update assertions |
| `tests/server/test_server.py` | Update mock setup |
| `tests/cli/onboarding/test_steps.py` | Update assertion |

## Backward Compatibility

- Existing configs with `enabled: true` still work (field ignored, Pydantic allows extra fields)
- Users with `enabled: false` would need to remove the section to disable (breaking, but rare case)
