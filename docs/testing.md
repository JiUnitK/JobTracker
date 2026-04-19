# Testing Guide

## Goals

The test suite should grow alongside the codebase so parsing, normalization, scoring, and persistence regressions are caught close to where they are introduced.

## Current Commands

Run the full suite:

```powershell
python -m pip install -e .[dev]
python -m pytest
```

Run one test module:

```powershell
python -m pytest tests\test_cli.py
```

## Current Coverage

The initial scaffold includes:

- CLI smoke coverage
- Default config validation coverage
- YAML loader error handling coverage
- Domain model validation coverage
- SQLite-backed repository integration coverage
- Alembic migration smoke coverage
- Fixture-based Greenhouse adapter parsing coverage
- Fixture-based Lever adapter parsing coverage
- Fixture-based Ashby adapter parsing coverage
- End-to-end run coordinator coverage for success and partial-success paths
- Cross-source end-to-end coverage across Greenhouse, Lever, and Ashby

## Expectations for New Work

Each new feature should ship with matching tests:

- new CLI behavior: CLI tests
- new config behavior: config/model tests
- new adapters: fixture-based parser tests
- new persistence logic: database integration tests
- new scoring rules: unit and golden tests

This follows the v1 roadmap so the project does not accumulate untested logic that becomes expensive to stabilize later.
