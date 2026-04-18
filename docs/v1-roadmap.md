# JobTracker v1 Roadmap

## Goal

Translate the v1 architecture into a concrete implementation plan with milestones, task-level deliverables, and an early testing strategy that reduces regression risk as the project grows.

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

## Milestone 0: Project Foundation

Objective:

Set up the repository, packaging, configuration loading, CLI skeleton, and testing framework before business logic becomes large.

Deliverables:

- Python project scaffold under `src/jobtracker`
- Dependency management and project metadata
- Base CLI entry point
- Config directory and initial config file structure
- Logging setup
- Test framework and test layout
- CI-ready test command

Concrete tasks:

- Create package structure:
  - `src/jobtracker/cli`
  - `src/jobtracker/config`
  - `src/jobtracker/models`
  - `src/jobtracker/storage`
  - `src/jobtracker/sources`
  - `src/jobtracker/normalize`
  - `src/jobtracker/scoring`
  - `src/jobtracker/reporting`
- Add project metadata and dependencies
- Add `jobtracker --help` CLI command
- Add config loader with typed config models
- Add baseline logging configuration
- Add `pytest` setup
- Add shared test fixtures
- Add test command documentation

Testing tasks:

- Configure `pytest`
- Add a basic smoke test for the CLI
- Add config loader unit tests
- Add a repository-level testing guide

Exit criteria:

- The project installs and runs locally
- `pytest` runs successfully
- The CLI boots successfully
- Config files load into typed models

## Milestone 1: Canonical Models and Persistence

Objective:

Define the normalized data model and persist jobs, companies, sources, and run history.

Deliverables:

- Pydantic domain models
- SQLAlchemy ORM models
- Database session management
- Initial Alembic migration
- Repository/data access layer

Concrete tasks:

- Define canonical domain models:
  - `SearchQuery`
  - `RawJobPosting`
  - `NormalizedJobPosting`
  - `CompanyRecord`
- Define ORM tables:
  - `companies`
  - `jobs`
  - `job_observations`
  - `search_runs`
  - `sources`
- Add database initialization flow
- Create initial migration
- Add repository methods for upsert/read operations
- Add environment/config support for SQLite and PostgreSQL

Testing tasks:

- Unit tests for model validation
- Database integration tests against SQLite
- Migration smoke test
- Repository tests for insert and update behavior

Exit criteria:

- Database schema can be created from migrations
- Core entities can be inserted and queried
- Repositories work for the basic persistence paths

## Milestone 2: Collection Pipeline Skeleton

Objective:

Create the end-to-end ingest flow with one adapter, even if source coverage is still minimal.

Deliverables:

- Source adapter base interface
- Source registry
- Search run orchestration
- Raw fetch to normalized ingest pipeline
- One working Tier 1 adapter

Concrete tasks:

- Define `SourceAdapter` interface
- Implement source enablement from config
- Create run coordinator:
  - start `search_run`
  - execute enabled source queries
  - collect errors
  - persist results
  - close `search_run`
- Implement first adapter:
  - recommended first source: Greenhouse
- Add raw payload capture for observations
- Add per-source logging and error reporting

Testing tasks:

- Adapter fixture-based parser tests
- Pipeline integration test from mocked adapter output to database rows
- Run summary test for successful and partial-failure cases

Exit criteria:

- `jobtracker run` executes one real source
- A run creates jobs, companies, observations, and run metadata
- Parser fixtures protect the first adapter from regressions

## Milestone 3: Structured Source Expansion

Objective:

Add a few reliable sources while keeping adapters isolated and thoroughly tested.

Deliverables:

- Lever adapter
- Ashby adapter
- Shared parsing helpers where appropriate
- Source-level metrics and health visibility

Concrete tasks:

- Implement Lever adapter
- Implement Ashby adapter
- Factor reusable parsing helpers without over-coupling adapters
- Add source metadata updates:
  - `last_success_at`
  - `last_error_at`
- Add command to list source health/status

Testing tasks:

- Fixture suites for Lever and Ashby
- Cross-source normalization tests
- Source health/status tests

Exit criteria:

- At least three structured sources run end-to-end
- Adapter tests cover expected extraction behavior
- Source health is visible in the CLI

## Milestone 4: Normalization and Deduplication

Objective:

Stabilize the model by merging repeated observations into durable job/company entities without over-merging.

Deliverables:

- Company name normalization
- Canonical job fingerprinting
- Conservative deduplication rules
- Best-source URL selection

Concrete tasks:

- Add normalization helpers for:
  - company names
  - job titles
  - workplace type
  - dates
  - salary fields
- Implement canonical key generation
- Implement primary dedupe on `source + source_job_id`
- Implement secondary dedupe heuristics
- Add logic for selecting a preferred URL and preferred source

Testing tasks:

- Unit tests for normalization helpers
- Unit tests for deduplication rules
- Regression fixtures for near-duplicate and non-duplicate cases

Exit criteria:

- Repeated runs do not create unnecessary duplicate jobs
- Similar jobs from multiple sources can be merged conservatively
- Normalization rules are covered by targeted tests

## Milestone 5: History and Status Tracking

Objective:

Make the system genuinely track hiring activity across time rather than only storing current rows.

Deliverables:

- First seen / last seen logic
- Job observation history
- Status inference for job lifecycle
- Company activity rollups

Concrete tasks:

- Update `first_seen_at` and `last_seen_at` consistently
- Implement status inference:
  - `active`
  - `stale`
  - `closed`
  - `unknown`
- Add configurable thresholds for staleness/closure
- Add company-level aggregates:
  - active relevant jobs
  - recent relevant jobs
  - latest relevant opening

Testing tasks:

- Repeated-run integration tests
- Status transition tests across multiple runs
- Company rollup tests

Exit criteria:

- The same job behaves correctly across repeated runs
- Job lifecycle status changes are reproducible and test-covered
- Company activity summaries can be queried

## Milestone 6: Scoring Engine

Objective:

Rank jobs and companies using transparent, configurable scoring.

Deliverables:

- Fit scoring
- Hiring scoring
- Combined priority scoring
- Score explanation payloads

Concrete tasks:

- Define profile-driven scoring inputs
- Implement fit score signals:
  - title match
  - skill match
  - location/workplace fit
  - seniority fit
- Implement hiring score signals:
  - freshness
  - repeated observations
  - number of related openings
  - source confidence
- Implement configurable weights
- Persist score values and explanations

Testing tasks:

- Unit tests for each score component
- Golden tests for representative job profiles
- Config-driven scoring tests to ensure weight changes behave predictably

Exit criteria:

- Jobs can be ranked by explainable scores
- Score outputs are stable under test
- Explanations make the ranking understandable

## Milestone 7: CLI Reporting and Export

Objective:

Make the collected and scored data useful from the command line.

Deliverables:

- Job listing commands
- Top-ranked report commands
- Company activity reports
- CSV and Markdown exports

Concrete tasks:

- Add CLI commands:
  - `jobtracker jobs list`
  - `jobtracker jobs top`
  - `jobtracker companies list`
  - `jobtracker sources list`
  - `jobtracker export csv`
- Add useful filters:
  - Austin
  - Remote
  - recent only
  - minimum score
- Add Markdown report output for weekly review

Testing tasks:

- CLI output tests
- Export file tests
- Query/filter behavior tests

Exit criteria:

- The CLI produces useful ranked outputs
- Exported reports can be used without manual cleanup

## Milestone 8: Hardening and Operational Quality

Objective:

Improve maintainability, resilience, and day-to-day usability once the main workflow exists.

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
- Document how to schedule recurring runs
- Document how to add a new adapter

Testing tasks:

- Error-path integration tests
- Timeout/retry behavior tests where practical
- Documentation review checklist

Exit criteria:

- The tool is reliable enough for unattended periodic runs
- Developers can add or debug sources with reasonable effort

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

- Create project scaffold
- Add dependency and packaging setup
- Add CLI skeleton
- Add config models and loader
- Add `pytest` setup and smoke tests
- Add test documentation

### Sprint 2

- Add canonical domain models
- Add SQLAlchemy models
- Add initial migration
- Add database session/repository layer
- Add DB integration tests

### Sprint 3

- Add source adapter interface and registry
- Add run coordinator
- Implement Greenhouse adapter
- Add fixture-based parser tests
- Add end-to-end ingest test

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

## Recommended Immediate Next Steps

The best next implementation steps are:

1. Scaffold the Python project and package structure
2. Add `pytest`, shared fixtures, and a smoke-test baseline
3. Add the CLI skeleton and config loader
4. Define canonical models and the initial database schema

This order gives the project a stable base so future source and scoring work can be added without repeatedly backtracking to fix structural issues.
