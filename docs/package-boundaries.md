# Package Boundaries

JobTracker now has two active workflows and one planned workflow. New code should
land in the workflow package that owns its behavior instead of broad legacy
namespaces.

## Active Workflow Packages

### `jobtracker.company_discovery`

Owns the company-first workflow:

- company discovery adapters
- discovery query planning
- company normalization and scoring
- ATS/careers resolution
- promotion into tracked monitoring

This package should not own tracked ATS job collection or instant open-web job
search.

### `jobtracker.job_tracking`

Owns persisted tracked-job collection:

- Greenhouse, Lever, and Ashby source adapters for tracked companies
- tracked-job query planning
- raw job normalization
- persisted run coordination
- tracked-job scoring

This package is for jobs collected from configured or promoted company hiring
surfaces. It should not become the home for instant search results.

### `jobtracker.job_search`

Owns the instant job-search workflow:

- Brave Search adapter
- instant-search query planning
- freshness and age classification
- relevance scoring for web search results
- structured result models for CLI and future GUI usage

This package starts side-effect-light and should avoid default database writes in
v1. Its typed request and result models live in `jobtracker.job_search.models`.

## Shared Packages

Shared infrastructure belongs in these packages:

- `jobtracker.config`: typed config loading and validation
- `jobtracker.models`: stable cross-workflow domain types
- `jobtracker.storage`: persistence, ORM models, migrations, and repositories
- `jobtracker.reporting`: reporting over persisted tracked and discovery data
- `jobtracker.cli`: CLI command registration and command-specific formatting

Workflow-specific request/result models should stay in their workflow package
unless they are clearly stable across workflows.

## Compatibility Shims

These top-level packages are compatibility shims for older tracked-job imports:

- `jobtracker.sources`
- `jobtracker.normalize`
- `jobtracker.scoring`

New code should import from `jobtracker.job_tracking.sources`,
`jobtracker.job_tracking.normalize`, and `jobtracker.job_tracking.scoring`
instead.

The shims should remain behavior-preserving until callers are migrated or a
deliberate removal decision is made.

First-party code should not import through these shim paths. The compatibility
contract is covered by `tests/test_import_boundaries.py`, and the no-new-legacy
import rule is covered by `tests/test_legacy_imports.py`.
