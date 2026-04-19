# JobTracker Roadmap

## Goal

Move JobTracker from a discovery-assisted workflow into a true autonomous company-discovery workflow where users start by running discovery and reviewing company candidates, not by manually finding companies first.

This roadmap is intentionally forward-looking. Completed historical milestones have been removed so the document stays focused on the current project state and the next implementation steps.

## Current State

JobTracker already has a strong foundation in place:

- local-first Python CLI application
- persistent storage, migrations, and test coverage
- tracked job collection from Greenhouse, Lever, and Ashby
- job lifecycle tracking and scoring
- company discovery data model, scoring, and promotion workflow
- discovery inbox, discovery review commands, and company-to-job drill-down
- DB-backed promotion from discovered company into tracked monitoring

Current verification baseline:

- `python -m pytest` passes
- `python -m jobtracker config validate` passes
- `python -m jobtracker db upgrade` passes
- `python -m jobtracker discover companies run` passes
- `python -m jobtracker run` passes

## Current Limitation

The biggest product limitation is still the discovery input model.

Today, company discovery is not yet fully autonomous. The user still needs to seed discovery evidence in [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml), for example:

- `company_search.params.results`
- `austin_ecosystem.params.entries`

That means the workflow is currently:

1. manually seed discovery inputs
2. run discovery
3. review and promote companies
4. run tracked job collection
5. drill down into jobs

The target workflow is:

1. run autonomous company discovery
2. review discovered companies
3. promote the right companies
4. collect jobs from those tracked companies
5. drill down into jobs when needed

## Product Direction

The next phase should make company discovery self-starting.

That means:

- no manual company hunting before first use
- no need to pre-populate company candidates by hand
- discovery sources that fetch candidate companies directly
- a workflow that begins with discovery inbox review

## Roadmap Principles

- Keep the company-first workflow as the product entry point
- Preserve the existing tracked ATS collection path
- Prefer transparent, testable source adapters over brittle one-off scripts
- Add autonomous discovery incrementally, with one source type at a time
- Keep docs honest about what is automated versus manual
- Front-load tests around parsing, persistence, and workflow regressions

## Autonomous Discovery Roadmap

### Milestone A1: Autonomous Discovery Input Layer

Objective:

Replace manual seeding in `config/company_discovery.yaml` with real fetchable discovery sources.

Deliverables:

- fetch-capable discovery adapter interface where needed
- first autonomous discovery source implementation
- config shape for fetch-driven discovery sources
- source-specific fixtures and persistence coverage

Concrete tasks:

- add discovery adapters that can fetch source material directly
- support one real autonomous source type first:
  - search-driven source, or
  - ecosystem directory source
- define config for query terms, pagination, and source-specific parameters
- keep existing config-driven fixture sources available for testing

Testing tasks:

- fixture tests for fetched payload parsing
- integration test from fetched discovery source into discovery tables
- error-path tests for fetch failures

Exit criteria:

- a discovery run can fetch company candidates without hand-entered result objects
- fetched discoveries persist into the existing discovery workflow
- tests protect the first autonomous source from parser regressions

### Milestone A2: Search-Driven Company Discovery

Objective:

Let JobTracker discover companies directly from search-style sources focused on Austin and remote opportunities.

Deliverables:

- one or more search-driven discovery adapters
- normalized extraction of company, job-title, location, and careers hints
- support for query-driven discovery config

Concrete tasks:

- implement query execution for search-driven discovery
- extract company names and job/careers URLs from search results
- support query groups for:
  - Austin software roles
  - Austin backend/platform roles
  - remote software roles
  - remote backend/platform roles
- deduplicate repeated company discoveries across search results

Testing tasks:

- fixture tests for search-result parsing
- integration tests for repeated company evidence
- query-planner tests for discovery search terms

Exit criteria:

- JobTracker can discover companies directly from search-style sources
- repeated search results merge into durable company discoveries
- search-driven discovery is stable under test

### Milestone A3: Ecosystem and Directory Discovery

Objective:

Add company discovery from Austin and remote ecosystem sources that answer “which companies should I care about?” even when they are not job boards.

Deliverables:

- ecosystem directory adapters
- source attribution for company-list discovery
- evidence merge behavior across search and ecosystem inputs

Concrete tasks:

- implement one or more ecosystem-list discovery adapters
- persist company-list evidence alongside job-style discovery evidence
- merge discoveries that point at the same company from different source types
- expose source attribution clearly in discovery review

Testing tasks:

- fixture tests for ecosystem parsing
- cross-source merge tests
- discovery scoring regression tests across mixed evidence

Exit criteria:

- JobTracker can discover companies from non-job-board ecosystem sources
- mixed evidence from multiple source types stays queryable and understandable

### Milestone A4: Resolver and ATS Discovery Expansion

Objective:

Improve the system’s ability to turn discovered companies into durable tracked candidates automatically.

Deliverables:

- stronger careers and ATS resolver layer
- direct ATS-pattern discovery support
- better resolution confidence and conflict handling

Concrete tasks:

- search for likely Greenhouse, Lever, and Ashby surfaces from company candidates
- improve resolution confidence scoring
- detect and expose conflicting ATS candidates more clearly
- enrich discovery review with the best current resolution target

Testing tasks:

- resolver heuristic unit tests
- conflict-resolution tests
- ATS-pattern fixture tests

Exit criteria:

- more discovered companies can be resolved into ATS-backed tracking candidates
- resolution quality improves without hiding conflicts

### Milestone A5: Discovery Workflow Polish

Objective:

Make the autonomous discovery workflow smooth enough to use as the default day-to-day entry point.

Deliverables:

- stronger discovery inbox experience
- workflow documentation centered on autonomous discovery
- usability refinements for company-first review

Concrete tasks:

- refine discovery inbox sorting and actionability views
- add any missing shortcuts for promote, ignore, and company job drill-down
- update README and workflow docs to remove manual-seeding-first assumptions
- capture and address top friction points from real usage

Testing tasks:

- CLI tests for discovery-first workflows
- documentation checklist review
- regression tests for company-to-job drill-down

Exit criteria:

- a user can start with discovery and stay in a company-first workflow naturally
- the docs match the autonomous workflow honestly

## Parallel Track: 8B Hardening

Milestone 8B still matters, but it should follow real workflow needs.

Focus areas:

- better failure handling
- timeout and retry policy
- source diagnostics
- performance tuning for unattended runs
- operations and adapter-development docs

This should be prioritized when real autonomous discovery usage exposes operational pain.

## Testing Expectations

Before a roadmap milestone is considered done:

- relevant unit tests pass
- relevant integration tests pass
- new adapters include fixture coverage
- new CLI surfaces include command coverage
- docs are updated when workflow behavior changes

## Immediate Next Steps

1. Implement `A1` so discovery can fetch candidate companies without hand-seeded results
2. Keep the README and workflow docs explicit that manual seeding is still a temporary limitation until `A1` lands
3. Use the company-first workflow as the product north star for every new discovery feature
