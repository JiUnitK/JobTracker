# JobTracker v1 Architecture

## Goal

Build a local-first tool that periodically discovers software job opportunities in Austin, TX and remote-friendly markets, tracks companies and openings over time, and ranks them by fit and hiring activity.

The tool should help answer two questions:

1. Which open roles are the best fit right now?
2. Which companies appear to be actively hiring for relevant roles, even if a specific posting is not yet a top match?

## Product Scope for v1

v1 is focused on a reliable backend pipeline and useful outputs, not a polished UI.

Included in v1:

- Config-driven search terms, locations, and source definitions
- Source adapters for structured job sources first
- Normalized storage for jobs, companies, and run history
- Deduplication and change tracking across repeated runs
- Explainable fit and hiring scoring
- CLI commands to run searches and inspect/export results

Not included in v1:

- Browser automation as the default strategy
- Complex AI-first extraction pipeline
- Full web dashboard
- Automated application submission
- CRM-style interview pipeline management

## Recommended Stack

### Language

- Python 3.12+

Why Python:

- Strong ecosystem for HTTP fetching, parsing, data normalization, and scheduling
- Fast iteration for a data-pipeline-heavy project
- Good fit for rule-based scoring and optional future AI enrichment

### Core Libraries

- `Typer` for CLI commands
- `httpx` for HTTP requests
- `BeautifulSoup` or `selectolax` for HTML parsing
- `Pydantic` for typed normalized models
- `SQLAlchemy` for ORM/data access
- `Alembic` for schema migrations
- `pytest` for tests
- `python-dateutil` for date parsing

### Storage

- Preferred: PostgreSQL
- Lightweight alternative: SQLite for early local development

Recommendation:

- Start development with SQLite if we want the fastest setup
- Move to PostgreSQL before relying on long-term history, richer queries, and multi-run reporting

### Scheduling

- External scheduler in v1
- Windows Task Scheduler locally, or cron in Linux/macOS environments

Rationale:

- Keeps the application simpler
- Avoids building and maintaining an internal scheduler too early

## System Design Overview

The system is composed of six logical layers:

1. Configuration
2. Source collection
3. Normalization and deduplication
4. Persistence and history tracking
5. Scoring
6. Output and reporting

### 1. Configuration Layer

The configuration layer defines what to search for and how.

Examples of configuration:

- Search terms:
  - `software engineer`
  - `backend engineer`
  - `platform engineer`
  - `python`
  - `distributed systems`
- Location filters:
  - `Austin, TX`
  - `Remote`
  - `United States`
- Seniority preferences:
  - mid-level
  - senior
- Exclusions:
  - internships
  - staff+ only roles
  - contract-only roles
- Source enablement:
  - enable/disable specific adapters
  - set source priority and reliability tier

Suggested config files:

- `config/search_terms.yaml`
- `config/sources.yaml`
- `config/scoring.yaml`
- `config/profile.yaml`

`profile.yaml` should eventually hold user-specific preferences such as preferred titles, must-have skills, disliked domains, target companies, and geographic flexibility.

### 2. Source Collection Layer

Each source is implemented as an adapter with a shared interface.

Responsibilities of a source adapter:

- Accept search terms and location constraints
- Fetch search results or open jobs from the source
- Parse relevant fields from the response or HTML
- Emit normalized raw records into the ingestion pipeline
- Record fetch metadata and errors

Suggested v1 source priority:

#### Tier 1: Structured ATS sources

- Greenhouse
- Lever
- Ashby
- Direct company career pages where listings are structured and stable

Why first:

- More stable data shape
- Better reliability
- Lower maintenance than aggregator sites

#### Tier 2: Search and aggregator sources

- Indeed
- LinkedIn
- Other search-heavy job listing sources

Why later:

- More fragile selectors and anti-bot controls
- Higher maintenance burden

#### Tier 3: Enrichment sources

- Levels.fyi
- Company metadata providers

Purpose:

- Compensation hints
- Company context
- Hiring signals not tied to a single posting

Suggested adapter interface:

```python
class SourceAdapter(Protocol):
    source_name: str

    def search(self, query: SearchQuery) -> list[RawJobPosting]:
        ...
```

Each adapter should be independently testable and isolated from downstream logic.

### 3. Normalization and Deduplication Layer

This layer converts source-specific records into canonical application models.

Canonical job fields should include:

- source
- source_job_id
- source_url
- title
- company_name
- location_text
- workplace_type: remote / hybrid / onsite / unknown
- posted_at
- description_snippet
- employment_type
- seniority
- salary_min
- salary_max
- salary_currency
- raw_tags

Canonical company fields should include:

- normalized_name
- display_name
- careers_url
- headquarters
- known_locations
- company_type
- notes

Normalization responsibilities:

- Normalize company names
- Standardize job titles and seniority levels
- Parse location and remote status
- Convert dates and salary fields into structured values
- Generate fingerprints for deduplication

Deduplication strategy:

- Primary match: `source + source_job_id`
- Secondary match: normalized company + normalized title + location + close URL match
- Optional fuzzy heuristics when the same job is reposted or syndicated

v1 should prefer conservative deduplication. False merges are worse than leaving two likely-duplicate rows that can later be cleaned up.

### 4. Persistence and History Tracking

The database should preserve both current state and historical observations across runs.

Core entities:

- `companies`
- `jobs`
- `job_observations`
- `search_runs`
- `sources`

Suggested high-level schema:

#### `companies`

- `id`
- `normalized_name`
- `display_name`
- `careers_url`
- `headquarters`
- `created_at`
- `updated_at`

#### `jobs`

- `id`
- `company_id`
- `canonical_key`
- `title`
- `location_text`
- `workplace_type`
- `employment_type`
- `seniority`
- `description_snippet`
- `salary_min`
- `salary_max`
- `salary_currency`
- `first_seen_at`
- `last_seen_at`
- `current_status`
- `best_source_url`
- `created_at`
- `updated_at`

#### `job_observations`

- `id`
- `job_id`
- `search_run_id`
- `source`
- `source_job_id`
- `source_url`
- `observed_posted_at`
- `observed_at`
- `raw_payload`
- `parse_status`

#### `search_runs`

- `id`
- `started_at`
- `completed_at`
- `status`
- `trigger_type`
- `summary_json`

#### `sources`

- `id`
- `name`
- `enabled`
- `reliability_tier`
- `last_success_at`
- `last_error_at`

Key behavior:

- A job is created the first time it is discovered
- `last_seen_at` updates whenever it is observed again
- A separate observation row is written for each run
- Job status is inferred from repeated observations

Suggested v1 job status values:

- `active`
- `stale`
- `closed`
- `unknown`

Possible status rules:

- `active`: seen recently and fetches are succeeding
- `stale`: not seen for N runs but evidence is incomplete
- `closed`: not seen for a stronger threshold or explicitly removed
- `unknown`: insufficient data

### 5. Scoring Layer

Scoring should be explainable and configurable.

v1 should compute at least three scores:

#### Fit Score

How well the job matches the target profile.

Example signals:

- Title match
- Skill keyword match
- Seniority match
- Domain preference match
- Location match
- Remote preference match
- Compensation signal if available

#### Hiring Score

How likely the company or role appears to be actively hiring.

Example signals:

- Posting freshness
- Repeated observations across runs
- Number of similar open roles at the same company
- Recent activity across multiple sources
- Structured ATS source confidence

#### Priority Score

A combined score used for ranking.

Example:

```text
priority_score = (0.65 * fit_score) + (0.35 * hiring_score)
```

Suggested scoring principles:

- Scores should be transparent and decomposable
- Store score reasons, not just the number
- Allow weights to be tuned in config
- Avoid black-box scoring in v1

Example explanation payload:

```json
{
  "fit_score": 82,
  "fit_reasons": [
    "title matched preferred role: backend engineer",
    "remote-compatible role",
    "contains preferred skills: python, distributed systems"
  ],
  "hiring_score": 71,
  "hiring_reasons": [
    "posting seen in 2 recent runs",
    "job posted within last 7 days",
    "company has 4 similar openings"
  ]
}
```

### 6. Output and Reporting Layer

v1 should expose the tool through a CLI.

Suggested commands:

- `jobtracker run`
- `jobtracker sources list`
- `jobtracker jobs list`
- `jobtracker jobs top`
- `jobtracker companies list`
- `jobtracker export csv`

Example outputs:

- Top Austin jobs this week
- Top remote jobs this week
- Companies with the most relevant recent openings
- Newly discovered roles since the last run
- Roles that appear to have gone stale or closed

CSV and Markdown export are both useful for v1. A web dashboard can come later once the underlying model is stable.

## Broad Data Flow

Each run should follow this sequence:

1. Load configuration
2. Build search queries from terms, locations, and source capabilities
3. Execute each enabled source adapter
4. Parse and normalize raw postings
5. Upsert companies
6. Deduplicate and upsert jobs
7. Write job observations for the run
8. Recompute job and company scores
9. Infer updated job status values
10. Produce run summary and optional exports

## Search Strategy in v1

Search should be term-driven and source-aware.

Example query groups:

- Austin software engineering roles
- Austin backend/platform roles
- Remote software engineering roles
- Remote backend/platform roles

Important detail:

Not every source supports the same filtering behavior. The query planner should account for source capability differences:

- Some sources allow keyword + location filters
- Some expose company-specific postings without free-text search
- Some only support URL parameter patterns

Because of this, the internal query model should be richer than a plain string.

Suggested internal query model:

```python
class SearchQuery(BaseModel):
    keywords: list[str]
    locations: list[str]
    workplace_types: list[str]
    seniority: list[str] = []
```

## Company Tracking Model

Jobs and companies should be separate first-class entities.

Why this matters:

- A company may have multiple relevant openings
- Hiring activity can be inferred across roles, not just within one posting
- It enables company-level ranking and watchlists

Suggested company-level derived fields:

- `active_relevant_job_count`
- `recent_relevant_job_count`
- `last_relevant_opening_seen_at`
- `company_hiring_score`

This supports outputs like:

- "Companies currently hiring most aggressively in Austin"
- "Remote-friendly companies with sustained relevant openings"

## Reliability and Compliance Considerations

This tool should be designed with source variability in mind.

Practical constraints:

- HTML structure changes frequently
- Some sources may block automated access
- Search result pages are less stable than ATS-hosted listings
- Some sites may have terms of service that require extra care

Design responses:

- Isolate source adapters from the rest of the system
- Attach reliability tiers to sources
- Log parse failures and fetch failures per source
- Prefer official or structured endpoints where possible
- Keep unsupported or brittle sources optional

v1 should succeed even if a subset of adapters is disabled.

## Testing Strategy

v1 should include automated tests in three layers:

### Unit tests

- Scoring rules
- Normalization helpers
- Deduplication logic
- Status inference logic

### Adapter tests

- Fixture-based parsing tests for each source
- Verify stable extraction of title, company, location, URL, and posted date

### Integration tests

- End-to-end ingest from mocked source payloads into the database
- Repeated-run behavior for job status changes

For adapters, fixture-based testing is important because it reduces accidental parser breakage when refactoring.

## Suggested Repository Shape

```text
jobtracker/
  src/jobtracker/
    cli/
    config/
    sources/
      base.py
      greenhouse.py
      lever.py
      ashby.py
    normalize/
    scoring/
    storage/
    models/
    reporting/
  tests/
    adapters/
    normalize/
    scoring/
    integration/
  config/
    search_terms.yaml
    sources.yaml
    scoring.yaml
    profile.yaml
  docs/
    v1-architecture.md
```

## Phased Delivery Plan

### Phase 1: Core foundation

- Project scaffold
- Database models and migrations
- Config loading
- Canonical job/company models
- CLI skeleton

### Phase 2: First collectors

- Greenhouse adapter
- Lever adapter
- Ashby adapter
- Basic run pipeline

### Phase 3: Tracking and scoring

- Deduplication
- Observation history
- Job status inference
- Fit/hiring/priority scoring

### Phase 4: Reporting

- Top jobs report
- Company activity report
- CSV/Markdown export

### Phase 5: Expansion

- Additional sources
- Company enrichment
- Optional dashboard
- Optional AI-assisted extraction/summarization

## Recommended v1 Decisions

If we want a practical and maintainable first version, the following decisions are recommended:

- Use Python for the full v1 backend
- Use a modular adapter architecture
- Use PostgreSQL as the target storage design, with SQLite acceptable for initial local setup
- Track jobs and companies separately
- Store raw observations for historical analysis
- Keep scoring rule-based and explainable
- Prioritize structured ATS sources before LinkedIn/Indeed
- Start with CLI outputs instead of a UI

## Open Design Questions

These do not block initial implementation, but we should settle them before coding too far:

1. Should v1 start on SQLite for convenience, or go straight to PostgreSQL?
2. Which job profile are we optimizing for first: backend, full-stack, platform, data, or a mix?
3. How much company enrichment do we want in v1 versus later?
4. Do we want a local-only tool, or should the design anticipate future deployment as a hosted service?
5. Should we incorporate resume-driven keyword extraction in v1, or keep the profile manually configured?

## Recommendation Summary

The best v1 is a local-first Python application with a config-driven query model, structured source adapters, normalized storage for jobs and companies, repeat-run history tracking, and explainable scoring.

That gives us a durable foundation that is useful quickly, while leaving room for richer search, more sources, and a dashboard later.
