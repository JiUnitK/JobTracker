# JobTracker v1 Roadmap

## Goal

Translate the v1 architecture into a concrete implementation plan with milestones, task-level deliverables, and an early testing strategy that reduces regression risk as the project grows.

## Current Status

Overall progress:

- Milestone 0 is complete
- Milestone 1 is complete
- Milestone 2 is complete
- Milestone 3 is complete
- Milestone 4 is complete
- Milestone 5 is complete
- Milestone 6 is complete
- Milestone 7 is complete
- Milestone 8A is complete
- Milestone 8B is next
- Company Discovery Track is planned
- Workflow boundary refactor for discovery is complete
- Milestone D1 is complete
- Milestone D2 is complete
- Milestone D3 is complete
- Milestone D4 is complete

Completed so far:

- Python project scaffold under `src/jobtracker`
- Packaging metadata and editable install support
- Base CLI entry point with `version` and `config validate`
- Typed YAML config models and loader
- Seed config files under `config/`
- Logging bootstrap
- Initial `pytest` setup and smoke/config tests
- Testing guide and repo hygiene files for Windows-friendly development
- Canonical domain models for search, company, and job records
- SQLAlchemy ORM models, repositories, and DB session helpers
- Alembic migration scaffolding and initial schema migration
- SQLite-backed persistence tests and migration smoke coverage
- Source adapter contract, registry, and query planning
- Greenhouse adapter and run coordinator
- Adapter fixture tests and end-to-end collection pipeline tests
- Lever and Ashby adapters
- Shared source parsing helpers and cross-source integration coverage
- Source status inspection from the CLI
- Expanded normalization helpers for company, title, workplace, location, and salary handling
- Primary and secondary deduplication rules with regression coverage
- Repeated-run lifecycle tracking and status inference
- Company activity rollups in run summaries
- Persisted job scoring with fit, hiring, and priority scores
- Score explanation payloads and scoring-focused regression coverage
- Reporting CLI for jobs, companies, CSV, and Markdown exports
- Daily/weekly workflow documentation and workflow-oriented reporting refinements
- A stable foundation that can support a separate company discovery workflow without reworking the current job-tracking pipeline
- Workflow-specific job collection code reorganized under `src/jobtracker/job_tracking` to make room for a sibling `company_discovery` package
- Company discovery foundation with config, schema, repositories, runner skeleton, and CLI command
- Two config-driven company discovery adapters with fixture coverage and end-to-end persistence tests
- Discovery scoring, resolution-state handling, and CLI review commands for discovered companies
- Promotion, ignore, and resolution acceptance workflow wired into tracked monitoring

Current verification baseline:

- `python -m pytest` passes
- `python -m jobtracker config validate` passes
- `python -m jobtracker version` passes
- `python -m jobtracker db upgrade` passes
- `python -m jobtracker run` passes
- `python -m jobtracker sources list` passes

## Roadmap Principles

- Build the core data model before adding many sources
- Put test infrastructure in place early
- Keep each milestone vertically useful where possible
- Prefer a small number of reliable sources before broader source coverage
- Add scoring only after normalized storage and repeated-run tracking are stable
- Treat regressions in parsing and scoring as first-class risks

## Delivery Strategy

The implementation should proceed in ordered milestones. Each milestone should end in a usable and testable checkpoint.

Recommended sequencing:

1. Project foundation and test harness
2. Data models and persistence
3. Collection pipeline and first adapter
4. Additional structured adapters
5. Deduplication, history, and status tracking
6. Scoring
7. Reporting and exports
8. Hardening and expansion
9. Company discovery

## Milestone 0: Project Foundation

Objective:

Set up the repository, packaging, configuration loading, CLI skeleton, and testing framework before business logic becomes large.

Status:

- Complete

Deliverables:

- [x] Python project scaffold under `src/jobtracker`
- [x] Dependency management and project metadata
- [x] Base CLI entry point
- [x] Config directory and initial config file structure
- [x] Logging setup
- [x] Test framework and test layout
- [x] CI-ready test command

Concrete tasks:

- [x] Create package structure:
  - `src/jobtracker/cli`
  - `src/jobtracker/config`
  - `src/jobtracker/models`
  - `src/jobtracker/storage`
  - `src/jobtracker/sources`
  - `src/jobtracker/normalize`
  - `src/jobtracker/scoring`
  - `src/jobtracker/reporting`
- [x] Add project metadata and dependencies
- [x] Add `jobtracker --help` CLI command
- [x] Add config loader with typed config models
- [x] Add baseline logging configuration
- [x] Add `pytest` setup
- [x] Add shared test fixtures
- [x] Add test command documentation

Testing tasks:

- [x] Configure `pytest`
- [x] Add a basic smoke test for the CLI
- [x] Add config loader unit tests
- [x] Add a repository-level testing guide

Exit criteria:

- [x] The project installs and runs locally
- [x] `pytest` runs successfully
- [x] The CLI boots successfully
- [x] Config files load into typed models

## Milestone 1: Canonical Models and Persistence

Objective:

Define the normalized data model and persist jobs, companies, sources, and run history.

Status:

- Complete

Deliverables:

- [x] Pydantic domain models
- [x] SQLAlchemy ORM models
- [x] Database session management
- [x] Initial Alembic migration
- [x] Repository/data access layer

Concrete tasks:

- [x] Define canonical domain models:
  - `SearchQuery`
  - `RawJobPosting`
  - `NormalizedJobPosting`
  - `CompanyRecord`
- [x] Define ORM tables:
  - `companies`
  - `jobs`
  - `job_observations`
  - `search_runs`
  - `sources`
- [x] Add database initialization flow
- [x] Create initial migration
- [x] Add repository methods for upsert/read operations
- [x] Add environment/config support for SQLite and PostgreSQL

Testing tasks:

- [x] Unit tests for model validation
- [x] Database integration tests against SQLite
- [x] Migration smoke test
- [x] Repository tests for insert and update behavior

Exit criteria:

- [x] Database schema can be created from migrations
- [x] Core entities can be inserted and queried
- [x] Repositories work for the basic persistence paths

## Milestone 2: Collection Pipeline Skeleton

Objective:

Create the end-to-end ingest flow with one adapter, even if source coverage is still minimal.

Status:

- Complete

Deliverables:

- [x] Source adapter base interface
- [x] Source registry
- [x] Search run orchestration
- [x] Raw fetch to normalized ingest pipeline
- [x] One working Tier 1 adapter

Concrete tasks:

- [x] Define `SourceAdapter` interface
- [x] Implement source enablement from config
- [x] Create run coordinator:
  - start `search_run`
  - execute enabled source queries
  - collect errors
  - persist results
  - close `search_run`
- [x] Implement first adapter:
  - recommended first source: Greenhouse
- [x] Add raw payload capture for observations
- [x] Add per-source logging and error reporting

Testing tasks:

- [x] Adapter fixture-based parser tests
- [x] Pipeline integration test from mocked adapter output to database rows
- [x] Run summary test for successful and partial-failure cases

Exit criteria:

- [x] `jobtracker run` executes one real source
- [x] A run creates jobs, companies, observations, and run metadata
- [x] Parser fixtures protect the first adapter from regressions

## Milestone 3: Structured Source Expansion

Objective:

Add a few reliable sources while keeping adapters isolated and thoroughly tested.

Status:

- Complete

Deliverables:

- [x] Lever adapter
- [x] Ashby adapter
- [x] Shared parsing helpers where appropriate
- [x] Source-level metrics and health visibility

Concrete tasks:

- [x] Implement Lever adapter
- [x] Implement Ashby adapter
- [x] Factor reusable parsing helpers without over-coupling adapters
- [x] Add source metadata updates:
  - `last_success_at`
  - `last_error_at`
- [x] Add command to list source health/status

Testing tasks:

- [x] Fixture suites for Lever and Ashby
- [x] Cross-source normalization tests
- [x] Source health/status tests

Exit criteria:

- [x] At least three structured sources run end-to-end
- [x] Adapter tests cover expected extraction behavior
- [x] Source health is visible in the CLI

## Milestone 4: Normalization and Deduplication

Objective:

Stabilize the model by merging repeated observations into durable job/company entities without over-merging.

Status:

- Complete

Deliverables:

- [x] Company name normalization
- [x] Canonical job fingerprinting
- [x] Conservative deduplication rules
- [x] Best-source URL selection

Concrete tasks:

- [x] Add normalization helpers for:
  - company names
  - job titles
  - workplace type
  - dates
  - salary fields
- [x] Implement canonical key generation
- [x] Implement primary dedupe on `source + source_job_id`
- [x] Implement secondary dedupe heuristics
- [x] Add logic for selecting a preferred URL and preferred source

Testing tasks:

- [x] Unit tests for normalization helpers
- [x] Unit tests for deduplication rules
- [x] Regression fixtures for near-duplicate and non-duplicate cases

Exit criteria:

- [x] Repeated runs do not create unnecessary duplicate jobs
- [x] Similar jobs from multiple sources can be merged conservatively
- [x] Normalization rules are covered by targeted tests

## Milestone 5: History and Status Tracking

Objective:

Make the system genuinely track hiring activity across time rather than only storing current rows.

Status:

- Complete

Deliverables:

- [x] First seen / last seen logic
- [x] Job observation history
- [x] Status inference for job lifecycle
- [x] Company activity rollups

Concrete tasks:

- [x] Update `first_seen_at` and `last_seen_at` consistently
- [x] Implement status inference:
  - `active`
  - `stale`
  - `closed`
  - `unknown`
- [x] Add configurable thresholds for staleness/closure
- [x] Add company-level aggregates:
  - active relevant jobs
  - recent relevant jobs
  - latest relevant opening

Testing tasks:

- [x] Repeated-run integration tests
- [x] Status transition tests across multiple runs
- [x] Company rollup tests

Exit criteria:

- [x] The same job behaves correctly across repeated runs
- [x] Job lifecycle status changes are reproducible and test-covered
- [x] Company activity summaries can be queried

## Milestone 6: Scoring Engine

Objective:

Rank jobs and companies using transparent, configurable scoring.

Status:

- Complete

Deliverables:

- [x] Fit scoring
- [x] Hiring scoring
- [x] Combined priority scoring
- [x] Score explanation payloads

Concrete tasks:

- [x] Define profile-driven scoring inputs
- [x] Implement fit score signals:
  - title match
  - skill match
  - location/workplace fit
  - seniority fit
- [x] Implement hiring score signals:
  - freshness
  - repeated observations
  - number of related openings
  - source confidence
- [x] Implement configurable weights
- [x] Persist score values and explanations

Testing tasks:

- [x] Unit tests for each score component
- [x] Golden tests for representative job profiles
- [x] Config-driven scoring tests to ensure weight changes behave predictably

Exit criteria:

- [x] Jobs can be ranked by explainable scores
- [x] Score outputs are stable under test
- [x] Explanations make the ranking understandable

## Milestone 7: CLI Reporting and Export

Objective:

Make the collected and scored data useful from the command line.

Status:

- Complete

Deliverables:

- [x] Job listing commands
- [x] Top-ranked report commands
- [x] Company activity reports
- [x] CSV and Markdown exports

Concrete tasks:

- [x] Add CLI commands:
  - `jobtracker jobs list`
  - `jobtracker jobs top`
  - `jobtracker companies list`
  - `jobtracker sources list`
  - `jobtracker export csv`
- [x] Add useful filters:
  - Austin
  - Remote
  - recent only
  - minimum score
- [x] Add Markdown report output for weekly review

Testing tasks:

- [x] CLI output tests
- [x] Export file tests
- [x] Query/filter behavior tests

Exit criteria:

- [x] The CLI produces useful ranked outputs
- [x] Exported reports can be used without manual cleanup

## Milestone 8A: Workflow and Usability

Objective:

Make JobTracker easy to use in a real daily or weekly workflow for tracking companies and jobs.

Status:

- Complete

Deliverables:

- [x] Clear daily workflow documentation
- [x] Clear weekly review workflow documentation
- [x] Practical CLI/report usage guidance
- [x] Workflow-oriented usability improvements
- [x] Documentation for recurring usage and score interpretation

Concrete tasks:

- [x] Document a recommended daily workflow
- [x] Document a recommended weekly workflow
- [x] Define how to review:
  - newly discovered jobs
  - rising-priority jobs
  - companies with sustained hiring activity
  - jobs that went stale or closed
- [x] Add or refine CLI/report commands where the workflow exposes friction
- [x] Document how to run recurring collection locally
- [x] Document how to interpret fit, hiring, and priority scores
- [x] Document how to update source identifiers and profile settings during regular use

Testing tasks:

- [x] CLI output tests for workflow-oriented commands
- [x] Export/report tests for recurring review artifacts
- [x] Documentation review checklist against the real workflow

Exit criteria:

- [x] A user can follow the documented workflow to review jobs and companies on a daily or weekly cadence
- [x] The workflow is supported by the current CLI and export outputs without awkward manual steps
- [x] The documentation is concrete enough to use the tool consistently in practice

## Milestone 8B: Hardening and Operational Quality

Objective:

Improve maintainability, resilience, and operational robustness after using the workflow in practice and surfacing the real friction points.

Deliverables:

- Better failure handling
- Retry and timeout policy
- Source-level diagnostics
- Performance tuning for repeated runs
- Documentation for operations and development

Concrete tasks:

- Add timeout and retry settings per source
- Improve structured logging around failures
- Add rate-limit friendly fetch behavior where needed
- Add data cleanup utilities if necessary
- Document how to schedule recurring runs in a more production-ready way
- Document how to add a new adapter

Testing tasks:

- Error-path integration tests
- Timeout/retry behavior tests where practical
- Documentation review checklist

Exit criteria:

- The tool is reliable enough for unattended periodic runs
- Developers can add or debug sources with reasonable effort

## Company Discovery Track

Objective:

Extend JobTracker so it can discover promising companies in Austin and remote markets, not just monitor companies that are already known.

Design reference:

- See [company-discovery-design.md](/abs/path/F:/Projects/JobTracker/docs/company-discovery-design.md)

Prerequisite status:

- [x] Job-tracking workflow code has been separated behind `job_tracking` package boundaries before discovery implementation begins

Guiding principles:

- Keep discovery and tracked-job collection as separate but connected workflows
- Preserve the current ATS-first tracking path
- Make promotion from discovered company to tracked company explicit
- Keep discovery evidence and scoring transparent

### Milestone D1: Discovery Foundation

Objective:

Create the data model, configuration, and run orchestration for company discovery.

Status:

- Complete

Deliverables:

- [x] Discovery config model and file
- [x] Company discovery domain models
- [x] Discovery persistence schema
- [x] Discovery adapter base interface and registry
- [x] Discovery run coordinator

Concrete tasks:

- [x] Add `config/company_discovery.yaml`
- [x] Add typed config models for discovery settings
- [x] Define domain models:
  - `CompanyDiscoveryQuery`
  - `RawCompanyDiscovery`
  - `NormalizedCompanyDiscovery`
- [x] Add ORM tables:
  - `company_discoveries`
  - `company_discovery_observations`
  - `company_resolutions`
- [x] Add migration for discovery tables
- [x] Add discovery repository methods
- [x] Add discovery runner and registry wiring
- [x] Add initial CLI entry point:
  - `jobtracker discover companies run`

Testing tasks:

- [x] Config loader tests for discovery config
- [x] Model validation tests for discovery entities
- [x] Repository integration tests for discovery inserts and updates
- [x] Discovery run smoke test
- [x] CLI smoke test for discovery run wiring

Exit criteria:

- [x] The schema supports discovered companies and discovery evidence
- [x] A discovery run can start, persist data, and complete cleanly
- [x] Discovery config loads through the existing config system

### Milestone D2: First Discovery Sources

Objective:

Collect initial company candidates from sources meant for discovery rather than durable job tracking.

Status:

- Complete

Deliverables:

- [x] One search-driven discovery adapter
- [x] One ecosystem or ATS-pattern discovery adapter
- [x] Basic normalization for discovered company evidence

Concrete tasks:

- [x] Implement the first search-driven discovery adapter
- [x] Implement one additional discovery source:
  - ecosystem-list source, or
  - ATS-pattern source
- [x] Add shared parsing helpers where useful
- [x] Normalize company name, source URL, and careers URL fields
- [x] Persist raw discovery evidence

Testing tasks:

- [x] Fixture tests for each discovery adapter
- [x] Integration test from adapter output to discovery tables
- [x] Repeated-evidence merge test for the same discovered company

Exit criteria:

- [x] At least two discovery sources can run end-to-end
- [x] Discovery evidence is persisted and queryable
- [x] Adapter fixtures protect extraction behavior

### Milestone D3: Resolution and Company Discovery Scoring

Objective:

Resolve promising companies into careers surfaces and rank them for review.

Status:

- Complete

Deliverables:

- [x] Resolution logic for ATS or direct careers surfaces
- [x] Discovery-specific scoring model
- [x] Discovery review outputs

Concrete tasks:

- [x] Implement company resolution states:
  - unresolved
  - partial
  - resolved
  - conflicted
- [x] Add resolution persistence and selection rules
- [x] Implement company discovery score signals:
  - fit relevance
  - hiring momentum
  - repeated appearance
  - ATS confidence
- [x] Persist score payloads and reasons
- [x] Add CLI commands:
  - `jobtracker discover companies list`
  - `jobtracker discover companies top`

Testing tasks:

- [x] Resolution heuristic unit tests
- [x] Discovery scoring unit tests
- [x] CLI tests for discovery review commands
- [x] Integration test for discovery score persistence

Exit criteria:

- [x] High-priority discovered companies can be reviewed from the CLI
- [x] Resolution state is visible and test-covered
- [x] Discovery scores are explainable and stable under test

### Milestone D4: Promotion Workflow

Objective:

Turn discovered companies into tracked companies with minimal manual friction and clear traceability.

Status:

- Complete

Deliverables:

- [x] Promotion and ignore workflow
- [x] Resolution acceptance workflow
- [x] Documentation for using discovery in the weekly routine

Concrete tasks:

- [x] Add CLI commands:
  - `jobtracker discover companies promote`
  - `jobtracker discover companies ignore`
  - `jobtracker discover companies resolve`
- [x] Attach promoted discoveries to canonical companies
- [x] Create or update tracked source configuration or DB-backed source records
- [x] Mark promoted companies as tracked
- [x] Update workflow docs with discovery review and promotion steps

Testing tasks:

- [x] Promotion workflow integration tests
- [x] CLI tests for promote/ignore actions
- [x] Documentation checklist for the discovery workflow

Exit criteria:

- [x] A discovered company can be promoted into tracked monitoring
- [x] Promotion preserves evidence and selected resolution data
- [x] The documented workflow covers discovery review through promotion

## Cross-Cutting Testing Plan

Testing needs to exist from the beginning and grow with each milestone.

### Testing goals

- Catch parser regressions before they hit multi-source runs
- Catch scoring drift when rules change
- Catch persistence bugs in repeated-run workflows
- Keep refactors safe as adapters and normalization logic grow

### Testing layers

Unit tests:

- config parsing
- normalization helpers
- score calculations
- status inference
- deduplication logic

Fixture-based adapter tests:

- one fixture set per source
- parse known input into expected fields
- pin important extraction behavior

Integration tests:

- end-to-end run execution with mocked adapters
- multi-run lifecycle behavior
- persistence and query behavior
- end-to-end discovery run behavior
- promotion from discovered company to tracked company

CLI tests:

- command wiring
- filtering options
- export behavior

### Testing timing

Testing should not be deferred.

Recommended order:

1. Add `pytest` and smoke tests in Milestone 0
2. Add DB integration tests in Milestone 1
3. Add parser fixture tests with the first adapter in Milestone 2
4. Add repeated-run integration tests before scoring in Milestone 5
5. Add golden tests when scoring is introduced in Milestone 6
6. Add discovery integration and promotion tests with the first discovery milestone

### Suggested quality gates

Before merging a milestone:

- All unit tests pass
- Relevant integration tests pass
- New adapters include parser fixtures
- New scoring logic includes explanation assertions
- New commands include CLI coverage

## Suggested Initial Task Breakdown

The first implementation sprint should focus on foundation work that unlocks safe iteration.

### Sprint 1

- [x] Create project scaffold
- [x] Add dependency and packaging setup
- [x] Add CLI skeleton
- [x] Add config models and loader
- [x] Add `pytest` setup and smoke tests
- [x] Add test documentation

### Sprint 2

- [x] Add canonical domain models
- [x] Add SQLAlchemy models
- [x] Add initial migration
- [x] Add database session/repository layer
- [x] Add DB integration tests

### Sprint 3

- [x] Add source adapter interface and registry
- [x] Add run coordinator
- [x] Implement Greenhouse adapter
- [x] Add fixture-based parser tests
- [x] Add end-to-end ingest test

## Definition of Done for Each Task

To reduce churn, each implementation task should be considered done only when:

- Code is implemented
- Relevant tests are added or updated
- The CLI or API path is wired if applicable
- Basic documentation is updated if behavior changed
- The task does not leave the system in a half-integrated state

## Risks and Mitigations

### Risk: Adapter fragility

Mitigation:

- Start with structured ATS sources
- Require parser fixtures for each adapter
- Keep source logic isolated

### Risk: Deduplication errors

Mitigation:

- Prefer conservative merging
- Add near-duplicate regression fixtures
- Track raw observations for recovery and analysis

### Risk: Scoring churn

Mitigation:

- Keep scoring config-driven
- Store explanation payloads
- Add golden tests for representative roles

### Risk: Foundation drift

Mitigation:

- Put test harness in Milestone 0
- Add migrations early
- Keep milestones narrow and vertical

### Risk: Noisy company discovery

Mitigation:

- Keep discovery sources separate from tracked ATS sources
- Score discovery candidates conservatively
- Require explicit promotion into tracked monitoring
- Preserve source evidence for review

### Risk: Incorrect company resolution

Mitigation:

- Add explicit resolution states and confidence
- Prefer unresolved over incorrect automatic attachment
- Test promotion and resolution flows with realistic fixtures

## Recommended Immediate Next Steps

The best next implementation steps are:

1. Review and confirm the company discovery design in [company-discovery-design.md](/abs/path/F:/Projects/JobTracker/docs/company-discovery-design.md)
2. Use the discovery workflow in practice and capture the friction points it exposes
3. Decide whether the next priority is broader discovery coverage or Milestone 8B hardening
4. Keep new source breadth behind actual workflow value rather than speculative coverage

This order gives the project a stable base so future source and scoring work can be added without repeatedly backtracking to fix structural issues.
