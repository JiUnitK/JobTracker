# JobTracker Roadmap

## Goal

Make JobTracker useful in two complementary modes:

1. instant relevant-job search for a user who wants fresh postings now
2. company-first discovery and tracking for users who want a longer-running watchlist workflow

The next priority is the instant job-search workflow. It should be easy to configure for a non-technical job seeker, run from the CLI first, and become the foundation for a local browser GUI.

## Current State

JobTracker already has:

- a local-first Python CLI application
- persistent storage, migrations, and test coverage
- config split across search terms, sources, scoring, and profile files
- autonomous company discovery from RemoteOK, HN Who's Hiring, and SerpAPI Google Jobs
- ATS fingerprinting for unresolved companies across Greenhouse, Lever, and Ashby
- company scoring and ATS/careers resolution with ranked candidates
- company review, promotion, ignore, and job drill-down flows
- DB-backed promotion from discovered company into tracked monitoring
- tracked job collection from Greenhouse, Lever, and Ashby
- job lifecycle tracking and scoring

Current verification baseline:

- `python -m pytest` passes
- `python -m jobtracker config validate` passes
- `python -m jobtracker search jobs --help` passes
- `python -m jobtracker db upgrade` passes
- `python -m jobtracker discover companies run` passes
- `python -m jobtracker discover companies fingerprint` passes
- `python -m jobtracker run` passes

## New Direction

Add a separate instant job-search workflow that searches the open web for relevant postings and surfaces the best matches immediately.

This workflow should:

- require `BRAVE_SEARCH_API_KEY`
- use Brave Search API as the first search provider
- search for postings no older than a configurable number of days
- use the user's local config for keywords, locations, workplace preferences, exclusions, and scoring
- work for non-tech job searches without requiring tech-specific source setup
- keep the CLI as a stable automation surface
- return structured results so a local web GUI can wrap the search logic without rewriting it

This is not a replacement for the company-first workflow. It is a faster front door for people who want current job postings without building a company watchlist first.

## Target CLI

Initial command shape:

```powershell
python -m jobtracker search jobs
python -m jobtracker search jobs --days 7
python -m jobtracker search jobs --query "customer success"
python -m jobtracker search jobs --location Remote
python -m jobtracker search jobs --limit 25
python -m jobtracker search jobs --include-unknown-age
python -m jobtracker search jobs --json
```

The default output should be a ranked, human-readable shortlist:

```text
Instant Job Search
Max age: 7 days | Results: 12

1. Customer Success Specialist | Example Health | Remote | 2 days old | score=86
   https://...
   Why: title match, remote, recent posting
```

## Proposed Config Shape

Use existing config files rather than adding another top-level config file.

In `config/search_terms.yaml`:

- add `instant_job_search.max_age_days`
- add `instant_job_search.include_unknown_age`
- add query templates or explicit instant-search queries
- reuse the existing include, exclude, locations, and workplace fields where practical

In `config/sources.yaml`:

- add an instant-search source section for `brave_search`
- read the key from `BRAVE_SEARCH_API_KEY`
- keep Brave-specific params such as endpoint, count, country, and language in source config

In `config/scoring.yaml`:

- either reuse current job scoring for v1
- or add a small `instant_job_search` scoring section if the relevance signals diverge

No separate selectable profile is needed. A user who clones the project should edit the local config for their own search needs.

## Implementation Tracks

### 1. Instant Job Search Foundation

Objective:

Create a separate workflow for fresh posting search without changing company discovery or tracked job collection.

Status:

- Implemented side-effect-light `jobtracker.job_search` foundation with typed request/result models, planner, Brave adapter, normalization, scoring, runner, reporting, registry, and CLI command.
- Added `python -m jobtracker search jobs` with `--days`, `--query`, `--location`, `--limit`, `--include-unknown-age`, and `--json`.
- Added fixture/injected-adapter tests for planning, Brave response parsing, missing API-key validation, runner filtering/scoring, and CLI output.

Focus:

- add `job_search` package with models, planner, Brave adapter, normalization, scoring, runner, and reporting
- add config models for instant search settings and Brave source params
- load `BRAVE_SEARCH_API_KEY` from `.env`
- keep the runner side-effect-light for v1, with no default database writes
- return structured result objects that the CLI and future GUI can both use

Suggested package:

```text
src/jobtracker/job_search/
  __init__.py
  models.py
  brave_adapter.py
  planner.py
  normalize.py
  scoring.py
  runner.py
  reporting.py
```

### 2. Brave Search Adapter

Objective:

Use Brave Search API to retrieve general web results likely to contain current job postings.

Status:

- Hardened the Brave adapter around the documented web search endpoint and `X-Subscription-Token` API key header.
- Added safe defaults for `count`, `country`, `search_lang`, and `safesearch`, with count clamped to Brave's supported web-search range.
- Added fixture-based parsing tests for successful, empty, and malformed responses.
- Added explicit tests for missing `BRAVE_SEARCH_API_KEY`, HTTP errors, network failures, and invalid JSON responses.
- CLI search now reports adapter/config failures as a concise command error instead of a traceback.

Focus:

- call `https://api.search.brave.com/res/v1/web/search`
- send the API key as `X-Subscription-Token`
- support count, country, search language, and safe defaults
- convert Brave results into raw instant-search records
- provide fixture-based tests for successful, empty, malformed, and error responses
- fail clearly when `BRAVE_SEARCH_API_KEY` is missing

### 3. Query Planning

Objective:

Generate useful job-search queries for non-tech and tech roles from local config.

Status:

- Added explicit `instant_job_search.queries` support for users who want hand-tuned search phrases instead of only global include terms.
- Query planning now combines configured search phrases, locations, workplace preferences, and templates into structured `InstantJobSearchQuery` objects.
- Added `{workplace_terms}` and `{job_intent}` template placeholders; custom templates that omit job-intent terms get a safe fallback.
- Default planning includes general job-intent queries and targeted Greenhouse, Lever, and Ashby site queries without requiring ATS parsing in the instant-search workflow.
- Added tests for CLI overrides, explicit configured queries, non-tech searches, workplace terms, job-intent fallback, and ATS-targeted templates.

Focus:

- combine configured keywords, locations, workplace types, and query templates
- support CLI overrides for query, location, max age, and limit
- include job-intent terms such as `job`, `apply`, `careers`, and `posted`
- support targeted searches against common ATS/job hosts later, without making v1 depend on every ATS parser
- avoid profile selection; the local config is the profile

### 4. Freshness and Age Filtering

Objective:

Honor "postings no older than x days" as honestly as possible.

Status:

- Expanded age classification to use `published_at`, relative age text, explicit dates in snippets/titles, and date-like URL path/query signals.
- Classifies age confidence as `high`, `medium`, `low`, or `unknown` based on the source of the signal.
- Strict freshness excludes unknown-age postings by default and includes them only with `--include-unknown-age`.
- CLI output already shows skipped age/relevance counts and labels unknown-age results as `age unknown` when included.
- Added tests for exact dates, relative age, URL-derived dates, unknown-age classification, and include/exclude filtering.

Focus:

- parse explicit dates or relative age text from search metadata, titles, snippets, and URLs when available
- classify age confidence as `high`, `medium`, `low`, or `unknown`
- default to excluding unknown-age postings if strict freshness is configured
- allow `--include-unknown-age` for sparse searches
- show skipped-result counts when age filtering removes otherwise relevant matches

Known risk:

Search results do not always expose posting age. V1 should be transparent about unknown age rather than pretending every result is date-verified.

### 5. Relevance Scoring and Output

Objective:

Surface a small set of results that feel immediately useful.

Status:

- Expanded instant-search relevance scoring across title strength, configured keywords, preferred skills, location/workplace, seniority, freshness confidence, source quality, and job-page signals.
- Scoring now emits concise user-facing `Why:` reasons such as strong title match, matched skills, remote workplace, recent posting, ATS source, and age unknown.
- JSON output remains structured for integration and GUI work.
- Added `--markdown-output` for instant-search review reports without adding database writes.
- Added focused tests for scoring signals, exclusions, unknown-age reasons, Markdown formatting, and CLI Markdown export.

Focus:

- score title, keyword, skill, location, workplace, freshness, and exclusion matches
- reuse existing scoring ideas where practical
- show concise "why" reasons in CLI output
- support `--json`, Markdown export, and possibly CSV export
- keep output friendly for users who do not know ATS terminology

### 6. GUI Readiness

Objective:

Prepare the instant-search implementation for a local browser GUI, then build the first usable GUI around it.

Chosen direction:

- Build a small local web app.
- Use a Python web backend so the GUI can call existing `jobtracker.job_search` services directly.
- Prefer FastAPI plus Uvicorn for the backend because the project already uses Pydantic models and typed request/response objects.
- Serve a static HTML/CSS/JS frontend from the same local process.
- Keep the app local-first at `http://127.0.0.1:<port>` and avoid database writes for instant search unless a later workflow explicitly adds saved searches.

Target local command:

```powershell
python -m jobtracker web
```

Target package shape:

```text
src/jobtracker/web/
  __init__.py
  app.py
  schemas.py
  static/
    index.html
    styles.css
    app.js
```

Target backend routes:

```text
GET /
  Serve the instant-search UI.

GET /api/config/summary
  Return defaults for query, location, max age, limit, include-unknown-age, and enabled instant-search sources.

POST /api/search/jobs
  Accept query, location, days, limit, and include_unknown_age.
  Run InstantJobSearchRunner.
  Return InstantJobSearchRunSummary JSON.
```

Target first screen:

- Search form with role/query, location, max age, result limit, and include-unknown-age controls.
- Summary strip with result count, max age, skipped-for-age count, and skipped-for-relevance count.
- Dense ranked results table with title, company, location/workplace, age/confidence, score, reasons, and open-link action.
- Loading, empty, and error states, including a clear missing `BRAVE_SEARCH_API_KEY` message.
- Markdown export or copy/download from the current result set after the initial table is working.

Focus:

- keep runner inputs and outputs typed and UI-agnostic
- provide JSON output for integration testing and prototype UI work
- avoid terminal-only formatting in the core runner
- design result fields for card/table display: title, company, location, age, score, URL, reasons
- add a local API layer that adapts web requests into `JobSearchOverrides`
- add the static frontend without moving search logic into JavaScript
- add backend route tests with an injected/fake runner
- add browser-level smoke tests once the page is interactive

Delivery steps:

1. Add GUI-readiness tests for the existing JSON shape and API-facing request fields.
2. Add FastAPI/Uvicorn dependencies and a `jobtracker.web` package.
3. Implement `/api/config/summary` and `/api/search/jobs` around the existing config loader and runner.
4. Add `python -m jobtracker web` to start the local server.
5. Build the static frontend as the first screen, not a landing page.
6. Add tests for route success, missing API-key/error responses, static asset serving, and basic browser rendering.

## Company-First Workflow Maintenance

The company-first workflow remains valuable, but it is no longer the next product expansion.

Keep maintaining:

- source failure diagnostics
- live fetch timeout and retry behavior
- HN and SerpAPI parsing improvements
- inbox and review output polish
- promotion into tracked ATS monitoring

Do not let this work block the instant job-search path unless it affects shared config, scoring, or source infrastructure.

## Testing Expectations

Before a roadmap item is considered done:

- relevant unit tests pass
- relevant integration tests pass
- new adapters include fixture coverage
- new CLI surfaces include command coverage
- missing API keys and API failures have explicit tests
- docs are updated when workflow behavior changes

## Immediate Next Steps

0. Preserve the cleaned workflow boundaries in [package-boundaries.md](package-boundaries.md) while adding the third workflow.
1. Add instant job-search config sections to `search_terms.yaml`, `sources.yaml`, and possibly `scoring.yaml`.
2. Create the `job_search` package and typed result models.
3. Implement the Brave Search adapter with fixtures and API-key validation.
4. Add `python -m jobtracker search jobs` with CLI overrides for days, query, location, limit, JSON, and unknown-age handling.
5. Implement age filtering, relevance scoring, and concise CLI reporting.
6. Finish GUI readiness and implement the local FastAPI/static HTML browser UI.
7. Re-run the workflow with non-tech search terms and tune query templates based on result quality.
