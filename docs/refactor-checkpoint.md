# Refactor Checkpoint

## Purpose

JobTracker is about to add an instant job-search workflow. Before that work starts,
the codebase should get one cleanup pass so the new workflow lands beside the
existing company-first and tracked-job workflows instead of adding another layer
of drift.

This checkpoint is intentionally scoped to structure, boundaries, and low-risk
cleanup. It should preserve the current behavior while making the next feature
easier to add.

## Current Baseline

Verified on 2026-04-20:

- `python -m pytest` passes with 87 tests.
- `python -m jobtracker config validate` passes.
- The current product has two established workflows:
  - company discovery and promotion
  - tracked ATS job collection and reporting
- The next roadmap item adds a third workflow:
  - instant job search through Brave Search, initially CLI-only

See [package-boundaries.md](package-boundaries.md) for the active package
ownership map and compatibility-shim policy.

## Main Cleanup Themes

### 1. Make Workflow Boundaries Explicit

The current code already points in the right direction:

- `jobtracker.company_discovery` owns company-first discovery.
- `jobtracker.job_tracking` owns tracked ATS collection.
- the roadmap proposes `jobtracker.job_search` for instant search.

Before adding `job_search`, keep new code out of generic legacy namespaces such
as `jobtracker.sources`, `jobtracker.normalize`, and `jobtracker.scoring`.

Recommended outcome:

- active implementation packages are workflow-specific
- shared code stays in clearly shared packages such as `config`, `models`,
  `storage`, and `reporting`
- compatibility shims are either documented as shims or removed after import
  users are migrated

### 2. Split the CLI by Workflow

`src/jobtracker/cli/app.py` has become the main orchestration surface for every
command group. That is workable today, but instant search will add another set
of commands and output modes.

Recommended outcome:

- keep `cli/app.py` as the Typer root and command registration point
- move tracked-job commands into a focused CLI module
- move company-discovery commands into a focused CLI module
- add instant-search commands in their own module when the feature starts
- keep shared CLI helpers small and output-oriented

This should be behavior-preserving and backed by the existing CLI tests.

Status:

- Done. `cli/app.py` is now the Typer root and command registration point.
- Workflow command groups live in focused CLI modules:
  - `cli/company_discovery.py`
  - `cli/tracked_jobs.py`
  - `cli/sources.py`
  - `cli/config.py`
  - `cli/database.py`
  - `cli/common.py`

### 3. Reduce Repository Class Size Before Adding New Persistence

`src/jobtracker/storage/repositories.py` currently holds source, run, job,
company, discovery, resolution, and observation repositories in one file.
Instant search is planned to avoid default database writes in v1, but it will
still need clear decisions about whether results stay ephemeral or are stored
later.

Recommended outcome:

- split repository classes by domain:
  - `storage/source_repository.py`
  - `storage/run_repository.py`
  - `storage/job_repository.py`
  - `storage/company_repository.py`
  - `storage/discovery_repository.py`
- keep `storage/__init__.py` as the public import surface during migration
- do not change schema behavior in this cleanup pass

Status:

- Done. Repository implementations now live in domain modules:
  - `storage/source_repository.py`
  - `storage/run_repository.py`
  - `storage/company_repository.py`
  - `storage/job_repository.py`
  - `storage/discovery_repository.py`
  - `storage/repository_utils.py`
- `storage/repositories.py` remains as a compatibility export module.
- `storage/__init__.py` still preserves the public repository imports.

### 4. Separate Shared Domain Models From Workflow Models

`src/jobtracker/models/domain.py` currently carries cross-cutting records for
raw jobs, normalized jobs, discovery records, source types, and scoring payloads.
That is fine for the current size, but instant search will introduce result
models that should not be forced into tracked-job persistence concepts too early.

Recommended outcome:

- leave stable shared models in `jobtracker.models`
- keep workflow-specific request/result models inside their workflow package
- add `jobtracker.job_search.models` for instant-search results instead of
  stretching tracked-job models to fit web search results

### 5. Tighten Config Without Adding Another Profile System

The roadmap correctly avoids a new top-level profile selector. The cleanup
needed here is mostly about keeping config naming and validation obvious.

Recommended outcome:

- add instant-search config sections to existing config files only
- keep provider-specific settings in `sources.yaml`
- keep search behavior in `search_terms.yaml`
- keep scoring weights in `scoring.yaml` only if v1 scoring diverges from
  tracked-job scoring
- add validation tests before implementing the Brave adapter

### 6. Preserve Tests as the Refactor Harness

The test suite is already broad enough to protect a cleanup pass. The safest
order is to refactor in small slices and run targeted tests after each slice,
then the full suite at the end.

Recommended test cadence:

- CLI split: `python -m pytest tests/test_cli.py tests/test_discovery_cli.py tests/test_reporting_cli.py`
- repository split: `python -m pytest tests/storage`
- import-boundary cleanup: `python -m pytest tests/sources tests/normalize tests/scoring`
- final baseline: `python -m pytest`

## Suggested Sequence

1. Document active package ownership and mark top-level source/normalize/scoring
   packages as compatibility shims. Done in
   [package-boundaries.md](package-boundaries.md).
2. Split CLI command groups into focused modules without changing command names.
   Done with `cli/app.py` preserved as the root registration point.
3. Split storage repositories by domain while preserving existing imports.
   Done with `storage/repositories.py` kept as a compatibility shim.
4. Move or document any remaining legacy imports.
5. Add instant-search config models and tests.
6. Create `jobtracker.job_search` with typed models and no side effects.
7. Implement Brave Search adapter and CLI on top of that cleaned boundary.

## Non-Goals

- No schema redesign before instant search.
- No database migration solely for cleanup.
- No changes to the company-first workflow unless a test exposes drift.
- No GUI work until instant search returns structured results.

## Definition of Done

The cleanup checkpoint is done when:

- all existing commands keep their current names and behavior
- compatibility shims are explicit or removed
- `jobtracker.company_discovery`, `jobtracker.job_tracking`, and future
  `jobtracker.job_search` each have clear ownership
- `python -m pytest` and `python -m jobtracker config validate` pass
