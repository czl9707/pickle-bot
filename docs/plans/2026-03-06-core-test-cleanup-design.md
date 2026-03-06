# Core Module Test Cleanup Design

**Date:** 2026-03-06
**Status:** Design Approved

## Overview

Consolidate trivial tests in `tests/core/` module using parametrized roundtrip tests and shared patterns, reducing test count from ~57 to ~37 while maintaining full coverage.

## Problem

Several test files in core/ have patterns similar to the events/ tests we cleaned:
- **EventSource pattern:** Individual tests for creation, serialization, and parsing
- **Loader pattern:** Repeated discovery/load/template tests across different loader types
- **Property checks:** Simple creation + property assertion tests
- **Backward compatibility tests:** Multiple tests for parameter variations

## Solution

Apply the same consolidation patterns used in the events/ test cleanup:
- Parametrize similar test cases
- Combine property checks into single tests
- Merge tests that verify related behaviors

## Design

### Phase 1: EventSource Pattern

#### File 1: `test_websocket_event_source.py` (7 → 2 tests)

Consolidate creation, serialization, and parsing tests into parametrized roundtrip tests.

**Before:**
- `test_create_websocket_event_source`
- `test_string_representation`
- `test_from_string_valid`
- `test_from_string_with_colon_in_user_id`
- `test_from_string_invalid_namespace`
- `test_from_string_invalid_format`
- `test_from_string_empty_user_id`

**After:**
- `test_source_roundtrip` (parametrized with 2 cases)
- `test_from_string_rejects_invalid` (parametrized with 3 cases)

#### File 2: `test_commands/test_base.py` (2 → 1 test)

Consolidate property and execution tests.

**Before:**
- `test_command_properties`
- `test_execute_returns_string`

**After:**
- `test_command_creation_and_execution`

### Phase 2: Command Tests

#### File: `test_commands/test_registry.py` (6 → 6 tests)

No changes needed - already well-structured with good parametrization.

### Phase 3: Loader Pattern

#### File 1: `test_skill_loader.py` (6 → 4 tests)

Consolidate template substitution tests.

**Before:**
- `test_discover_skills_valid_skill`
- `test_load_skill_returns_full_content`
- `test_load_skill_raises_not_found`
- `test_substitutes_template_variables`
- `test_substitutes_multiple_variables`
- `test_no_template_variables_unchanged`

**After:**
- `test_discover_skills_valid_skill`
- `test_load_skill_returns_full_content`
- `test_load_skill_raises_not_found`
- `test_template_substitution` (parametrized with 3 cases)

#### File 2: `test_cron_loader.py` (6 → 4 tests)

Consolidate load and discover tests by one_off field.

**Before:**
- `test_cron_def_requires_description`
- `test_load_simple_cron`
- `test_discover_crons`
- `test_substitutes_template_variables`
- `test_load_cron_with_one_off`
- `test_discover_crons_with_one_off`

**After:**
- `test_cron_def_requires_description`
- `test_load_cron_with_optional_fields` (parametrized by one_off)
- `test_discover_crons` (includes one_off variations)
- `test_substitutes_template_variables`

#### File 3: `test_agent_loader.py` (18 → 11 tests)

Multiple consolidations via parametrization.

**Consolidations:**
1. Template tests (3 → 1): `test_template_substitution` parametrized
2. Allow skills tests (2 → 1): `test_allow_skills_field` parametrized
3. Max concurrency tests (2 → 1): `test_max_concurrency_field` parametrized
4. Error tests (3 → 2): `test_raises_not_found` parametrized, `test_raises_invalid_when_missing_name`

### Phase 4: Context and Session

#### File 1: `test_context.py` (7 → 4 tests)

Consolidate initialization and channel parameter tests.

**Consolidations:**
1. Initialization tests (3 → 1): Combine all property checks
2. Channel tests (3 → 2): Parametrize backward-compatibility tests

#### File 2: `test_session_state.py` (3 → 2 tests)

Consolidate message tests.

**Consolidation:**
- Message tests (2 → 1): `test_add_message_persists_and_appends`

#### File 3: `test_session.py` (2 → 2 tests)

No changes needed - already minimal.

## Scope

**In scope:**
- Test consolidation via parametrization
- Combining property checks
- Merging related behavior tests
- Code reduction without coverage loss

**Out of scope:**
- Logic/behavior changes
- Integration test restructuring
- API test cleanup (separate effort)
- Changes to test fixtures

## Testing

All changes will follow TDD:
1. Write new parametrized tests
2. Run to verify they pass
3. Remove old tests
4. Verify no coverage loss

## Migration Path

1. Phase 1: EventSource pattern (2 files)
2. Phase 2: Command tests (no changes)
3. Phase 3: Loader pattern (3 files)
4. Phase 4: Context/Session (3 files)
5. Full test suite verification

## Benefits

- **Test count:** 57 → 37 (35% reduction)
- **Lines of code:** ~400 lines removed
- **Maintainability:** Consistent patterns across core/ tests
- **Coverage:** No reduction - same behaviors tested

## Risks

- Minimal risk - no behavior changes, only test structure
- All changes are reversible
- Full test suite will verify no regressions
