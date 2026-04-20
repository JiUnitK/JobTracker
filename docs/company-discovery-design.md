# JobTracker Company Discovery Design

## Goal

Add a first-class company discovery layer on top of the existing job-tracking pipeline so the tool can:

1. discover promising companies, not just jobs
2. rank companies by relevance and hiring momentum
3. promote good discovery candidates into the tracked-source workflow
4. keep company discovery and job tracking connected without making either one brittle

## Why This Is a Separate Layer

The current system is strongest when we already know which ATS boards to monitor. That works well for tracking known companies, but it does not solve the earlier question:

"Which companies should I be watching in the first place?"

Company discovery fills that gap.

It should not replace the current ATS-first pipeline. Instead, it should sit above it:

- discovery finds companies worth watching
- resolution tries to find the company's canonical careers surface
- promotion adds the company to the tracked-source workflow
- ongoing tracking monitors the company's jobs over time

## Product Outcomes

With company discovery in place, JobTracker should help answer four questions:

1. Which open roles are the best fit right now?
2. Which companies appear to be actively hiring for relevant roles?
3. Which companies keep showing up in Austin or remote discovery and deserve attention?
4. Which discovered companies have been promoted into active tracking, and why?

## Scope

Included in this design:

- company discovery from search, aggregator, and ATS-pattern sources
- company resolution into known ATS or careers endpoints
- company-level ranking and watch states
- promotion workflow from discovered company to tracked company
- review/reporting surfaces for discovered companies

Not included in the first discovery pass:

- full browser automation
- automated outreach or application workflows
- deep company enrichment from many paid APIs
- AI-heavy summarization as a core requirement

## Design Principles

- Keep discovery and tracking separate but connected
- Treat companies as first-class entities, not just job attributes
- Preserve traceability back to discovery evidence
- Prefer transparent, rule-based scoring first
- Keep manual review and promotion explicit in v1 of discovery
- Reuse the existing persistence, scoring, and reporting foundations where practical

## Conceptual Model

The system should manage three related company states:

### 1. Discovered company

A company found through search, aggregator results, directories, or repeated hiring signals.

Characteristics:

- may not yet have a known ATS identifier
- may not yet have any durable tracked source configuration
- should retain the evidence that caused discovery

### 2. Watchlist company

A discovered company that looks promising enough to keep reviewing, even if we have not promoted it to full tracking.

Characteristics:

- has a higher company discovery score
- has recent relevant evidence
- may have partial resolution data

### 3. Tracked company

A company that has been promoted into the durable monitoring workflow.

Characteristics:

- has a known ATS board, careers page, or other stable source
- is included in the recurring run pipeline
- contributes to ongoing job, status, and company activity tracking

## Discovery Source Types

Company discovery should support more than one kind of input.

### Search-driven discovery

Searches designed to surface companies behind relevant roles.

Examples:

- Austin software engineer openings
- remote backend engineer openings
- `site:boards.greenhouse.io Austin engineer`
- `site:jobs.lever.co remote backend`
- `site:jobs.ashbyhq.com software engineer remote`

What we extract:

- company name
- job title
- job URL
- location/workplace hints
- source URL
- discovered careers or ATS domain

### Aggregator-driven discovery

Use aggregator-style sources primarily to discover company names and hiring signals, not as the long-term source of truth.

Examples:

- LinkedIn
- Indeed
- Levels.fyi job pages

What we extract:

- company name
- repeated appearance of relevant roles
- likely Austin or remote hiring footprint
- downstream clue for careers-page resolution

### Direct ATS-pattern discovery

Search for companies indirectly through known ATS footprints.

Examples:

- Greenhouse board URLs
- Lever account pages
- Ashby job board pages

What we extract:

- candidate company slug or board token
- careers URL
- source platform

## Resolution Layer

Discovery alone is not enough. The system also needs to resolve a discovered company into a durable identity and, when possible, a stable source to track.

Resolution responsibilities:

- normalize company names
- merge likely duplicate discovered companies conservatively
- identify official company website if available
- identify ATS-backed careers surfaces if available
- map discovered company to one of:
  - Greenhouse board token
  - Lever account name
  - Ashby job board name
  - direct careers page URL

Resolution outputs should be explicit:

- `unresolved`
- `partially_resolved`
- `resolved_to_ats`
- `resolved_to_direct_careers`

The first pass should stay conservative. If resolution is uncertain, keep the company unresolved rather than attaching the wrong ATS board.

## Data Model Additions

The current `companies` table should remain the durable entity for tracked companies and normalized company identities. Company discovery adds related evidence and workflow tables.

Suggested additions:

### `company_discoveries`

One row per discovered company identity candidate.

Fields:

- `id`
- `company_id` nullable
- `normalized_name`
- `display_name`
- `discovery_status`
- `resolution_status`
- `discovery_score`
- `fit_score`
- `hiring_score`
- `priority_score`
- `first_discovered_at`
- `last_discovered_at`
- `promoted_at` nullable
- `ignored_at` nullable
- `notes`
- `score_payload`
- `created_at`
- `updated_at`

### `company_discovery_observations`

One row per discovery event or piece of evidence.

Fields:

- `id`
- `company_discovery_id`
- `search_run_id` nullable
- `source_type`
- `source_name`
- `source_url`
- `job_url` nullable
- `job_title` nullable
- `location_text` nullable
- `workplace_type` nullable
- `observed_at`
- `raw_payload`

### `company_resolutions`

Tracks candidate and accepted resolution targets.

Fields:

- `id`
- `company_discovery_id`
- `resolution_type`
- `platform`
- `identifier`
- `url`
- `confidence`
- `is_selected`
- `observed_at`

### Optional: `company_watchlist_events`

Useful if we later want a clean audit trail for workflow actions.

Fields:

- `id`
- `company_discovery_id`
- `event_type`
- `event_payload`
- `created_at`

Examples:

- promoted to tracked
- marked ignore
- moved to watchlist
- resolution accepted

## Discovery Status Model

Suggested company discovery statuses:

- `candidate`
- `watch`
- `tracked`
- `ignored`
- `archived`

Suggested resolution statuses:

- `unresolved`
- `partial`
- `resolved`
- `conflicted`

These should stay explicit and user-facing so the workflow is understandable from the CLI.

## Discovery Pipeline

The discovery pipeline should be adjacent to, but separate from, the current job collection pipeline.

Suggested high-level flow:

1. Load discovery config and search terms
2. Execute enabled discovery adapters
3. Parse raw company evidence
4. Normalize company names and URLs
5. Upsert discovered company identities
6. Write discovery observations
7. Attempt ATS or careers resolution
8. Compute company discovery scores
9. Produce review outputs
10. Optionally promote selected companies into tracked sources

## Discovery Adapters

Discovery adapters should have a distinct interface from job-source adapters.

Suggested interface:

```python
class CompanyDiscoveryAdapter(Protocol):
    source_name: str

    def discover(self, query: CompanyDiscoveryQuery) -> list[RawCompanyDiscovery]:
        ...
```

Suggested raw discovery fields:

- `company_name`
- `company_url`
- `careers_url`
- `job_url`
- `job_title`
- `location_text`
- `workplace_type`
- `source_type`
- `source_url`
- `evidence_kind`
- `raw_payload`

This separation matters because not every discovery source will produce durable job rows.

## Scoring Model

Company discovery needs its own scoring model. It can reuse the language of fit and hiring, but the signals differ from job scoring.

Suggested outputs:

- `company_fit_score`
- `company_hiring_score`
- `company_discovery_score`

### Company fit signals

- domain relevance
- Austin presence
- remote-friendliness
- role-family relevance across evidence
- repeated appearance in preferred searches
- repeated appearance in automated discovery sources

### Company hiring signals

- number of relevant openings found
- freshness of evidence
- repeated observations across runs
- presence of multiple relevant roles
- ATS-backed careers surface confidence

### Company discovery score

A combined ranking used for review and promotion priority.

Example:

```text
company_discovery_score = (0.50 * company_fit_score) + (0.50 * company_hiring_score)
```

As with job scoring, the important principle is transparency. The system should store reasons, not only numeric scores.

## Promotion Workflow

Promotion is how a discovered company becomes part of the durable ATS-tracking loop.

Suggested workflow:

1. Review discovered companies ranked by discovery score
2. Inspect evidence and any candidate resolutions
3. Accept one of these actions:
   - ignore
   - keep on watchlist
   - promote to tracked
4. If promoted:
   - attach or create the canonical `company`
   - create or update the appropriate tracked source configuration
   - persist the selected resolution target
   - mark discovery status as `tracked`

Promotion should stay explicit in the first pass. Automatic promotion can come later if the workflow proves trustworthy.

## CLI and Reporting Additions

Discovery should feel usable from the same CLI-first workflow as the rest of the tool.

Suggested new commands:

- `jobtracker discover companies run`
- `jobtracker discover companies list`
- `jobtracker discover companies top`
- `jobtracker discover companies promote`
- `jobtracker discover companies ignore`
- `jobtracker discover companies resolve`

Useful filters:

- Austin only
- remote-friendly only
- unresolved only
- watchlist only
- promoted only
- recent only
- minimum discovery score

Useful outputs:

- newly discovered companies this week
- companies with repeated recent evidence
- unresolved but high-priority companies
- promoted companies with active tracked jobs

## Configuration Shape

Company discovery likely needs its own config file rather than overloading `sources.yaml`.

Suggested config:

- `config/company_discovery.yaml`

Possible sections:

- enabled adapters
- discovery search terms
- location and workplace filters
- source-specific fetch and parsing behavior
- resolution behavior
- discovery scoring weights
- promotion defaults

`sources.yaml` should remain focused on durable tracked job sources.

## Relationship to Existing Architecture

The existing system already provides several pieces discovery can reuse:

- config loading
- search runs
- normalization helpers
- company persistence
- scoring patterns
- reporting patterns
- CLI structure

The discovery layer should be added as a sibling workflow, not a rewrite.

Suggested package shape:

```text
src/jobtracker/
  company_discovery/
    base.py
    models.py
    planner.py
    registry.py
    resolver.py
    runner.py
    scoring.py
```

## Testing Strategy

Discovery should follow the same test-first discipline as the core pipeline.

Unit tests:

- company normalization and merge heuristics
- discovery scoring
- resolution heuristics
- promotion workflow behavior

Fixture-based adapter tests:

- one fixture set per discovery source
- assert stable extraction of company names, URLs, and job evidence

Integration tests:

- end-to-end discovery run into DB tables
- repeated discovery observations across runs
- promotion from discovered company into tracked company state

CLI tests:

- discovery list and filter commands
- promotion and ignore actions
- resolution visibility

## Recommended Delivery Approach

The safest rollout is incremental:

### Phase 1: Discovery foundation

- config model
- discovery domain models
- DB schema
- discovery registry and runner

### Phase 2: First discovery sources

- one search-driven discovery adapter
- one aggregator or ATS-pattern discovery adapter
- fixture and integration coverage

### Phase 3: Resolution and scoring

- ATS/careers resolution
- company discovery scoring
- review outputs

### Phase 4: Promotion workflow

- promote discovered company to tracked company
- CLI actions
- workflow documentation

## Open Questions

1. Should discovery live in the same `search_runs` table, or should it get a separate `discovery_runs` concept?
2. Which discovery source should come first: search-driven, aggregator-driven, or ATS-pattern?
3. Should promotion update `sources.yaml`, or should tracked sources move into the database?
4. How much aggregator support do we want before we validate the workflow manually?

## Recommendation Summary

The next evolution of JobTracker should add a dedicated company discovery layer that finds companies, stores discovery evidence, resolves careers surfaces, ranks companies for review, and promotes good candidates into the existing tracked-source workflow.

That approach preserves the strengths of the current ATS-first pipeline while expanding the product from "track jobs from companies I already know" to "help me discover which companies I should care about next."
