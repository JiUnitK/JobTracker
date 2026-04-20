# JobTracker Roadmap

## Goal

Make JobTracker feel natural as a company-first workflow:

1. run discovery
2. review discovered companies
3. promote the right companies
4. collect jobs from those companies
5. drill into the jobs that matter

This roadmap is intentionally forward-looking. Completed milestones have been removed so the document stays focused on the current state and the next work.

## Current State

JobTracker already has:

- a local-first Python CLI application
- persistent storage, migrations, and test coverage
- tracked job collection from Greenhouse, Lever, and Ashby
- job lifecycle tracking and scoring
- autonomous company discovery from enabled search, ecosystem, and directory sources
- ATS and careers-surface resolution with ranked candidates
- company review, promotion, ignore, and job drill-down flows
- DB-backed promotion from discovered company into tracked monitoring
- curated starter data for Austin ecosystem and broader company directory sources

Current verification baseline:

- `python -m pytest` passes
- `python -m jobtracker config validate` passes
- `python -m jobtracker db upgrade` passes
- `python -m jobtracker discover companies run` passes
- `python -m jobtracker run` passes

## Current Workflow

The intended workflow is now:

1. `python -m jobtracker discover companies run`
2. `python -m jobtracker discover companies inbox`
3. `python -m jobtracker discover companies review --company "..."`
4. resolve, promote, or ignore companies
5. `python -m jobtracker run`
6. `python -m jobtracker jobs top --company "..."`

The product is now meaningfully discovery-first.

## Remaining Gap

The biggest remaining product gap is true autonomous discovery.

Today, discovery is functional but closed — it surfaces what you already put in the data files. The inbox fills up, but only with companies you curated yourself. There is no live, open-web signal that finds companies you did not already know about.

The path to fixing this is a sequence of increasingly powerful live discovery sources, starting with sources that require no API key and expanding from there.

## Primary Track: Autonomous Discovery Sources

The five steps below are ordered by effort and dependency. Steps 1 and 2 require no external accounts or API keys and can be done immediately.

### Step 1 — RemoteOK Adapter

RemoteOK (`https://remoteok.com/api`) exposes a public JSON feed of remote tech job listings — no API key, no auth. Each entry includes company name, job title, tags, and URLs.

Work:

- build a `RemoteOKDiscoveryAdapter` that fetches the feed and maps entries to `RawCompanyDiscovery`
- add `remoteok` as a named source in the registry
- add `remote_ok` to `DiscoverySourceType` in `domain.py`
- add the source to `config/company_discovery.yaml` as `enabled: true` with no required params
- add fixture coverage and unit tests

Why first: zero config friction, live signal, straightforward JSON shape, no new adapter patterns needed.

### Step 2 — HN Who's Hiring Adapter

The monthly Hacker News "Who's Hiring" thread is the richest organic signal for active tech hiring. The HN Algolia API (`hn.algolia.com/api/v1`) retrieves thread comments as structured JSON — no auth. Each comment is a company posting jobs in free-form text, typically including company name, location, role, and a careers or ATS URL.

Work:

- build an `HNHiringDiscoveryAdapter` that fetches the current month's thread via HN Algolia and parses comments
- parse each comment for: company name, ATS or careers URL, location signal, remote/hybrid indicator
- add `hn_hiring` to `DiscoverySourceType` in `domain.py`
- add the source to `config/company_discovery.yaml` as `enabled: true` with a configurable `thread_id` param (or auto-detect current month's thread)
- add fixture coverage and unit tests

Why second: highest-quality live signal after RemoteOK, no API key needed, but requires comment parsing that adds complexity.

### Step 3 — Search API Integration

Enable the `company_search` source with a working `query_url_template`. The adapter and config structure are already in place — only a real endpoint is missing.

Recommended: SerpAPI Google Jobs engine. Free tier is 100 searches per month with no credit card.

Template:

```
https://serpapi.com/search.json?engine=google_jobs&q={query}&location={location}&api_key=YOUR_KEY
```

Work:

- document SerpAPI setup in the README under Config Notes
- update `config/company_discovery.yaml` to show a populated `query_url_template` example (with placeholder key)
- enable `company_search` once a key is configured
- verify the existing `CompanySearchDiscoveryAdapter` handles the SerpAPI response shape, fix if needed
- add fixture coverage for the SerpAPI response format

Why third: the highest-signal source for keyword-driven discovery, but the only step in this track that requires an external account.

### Step 4 — ATS Fingerprinting Pass

After discovery runs, companies with `resolution_status = unresolved` have no known ATS board. Many of these can be resolved automatically by probing common ATS board URL patterns using the normalized company name as the slug.

Probe order:

1. `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` — 200 with job data = Greenhouse match
2. `https://api.lever.co/v0/postings/{slug}` — 200 with job array = Lever match
3. `https://api.ashbyhq.com/posting-api/job-board/{slug}` — 200 with job data = Ashby match

Where `slug` is derived from the normalized company name (lowercase, hyphenated).

Work:

- build an `ATSFingerprintingService` that accepts a list of unresolved discoveries and probes the three platforms
- add successful probes as new `CompanyResolutionORM` candidates with appropriate confidence
- run fingerprinting as a post-pass in `CompanyDiscoveryRunner.run()` after the main discovery loop
- expose a standalone CLI command: `python -m jobtracker discover companies fingerprint`
- add unit tests with mocked HTTP responses for hit and miss cases

Why fourth: dramatically improves unresolved → resolved rate without manual lookup, but depends on having a meaningful pool of unresolved companies first (which Steps 1–3 provide).

### Step 5 — Discovery Freshness

Once discovery is running repeatedly from live sources, the inbox needs to distinguish new signal from noise. Currently, repeated runs re-surface the same companies with no indication of whether they are new or recurring.

Work:

- add a `first_discovered_at` field to `CompanyDiscoveryORM` (migration required)
- add a `--new-only` flag to `discover companies inbox` that filters to companies first seen in the current run
- surface "new this run" vs. "seen before" in the inbox and top output
- add a `recent_days` filter to `discover companies run` output summary

Why fifth: low product value until live sources (Steps 1–3) are generating volume. With only curated static sources, freshness is not meaningful.

## Secondary Tracks

### Workflow Hardening

Objective:

Make the current company-first workflow dependable for daily or weekly use.

Focus:

- timeout and retry policy for source fetches
- clearer per-source diagnostics on failure
- unattended-run ergonomics (exit codes, structured output option)
- keyword matching robustness — broaden beyond exact title match (e.g. "engineer" anchor with exclude terms)

### Workflow Refinement

Objective:

Improve the feel of the discovery-to-jobs loop based on real usage.

Focus:

- inbox and review output polish
- better shortcuts for repetitive review actions
- reducing friction in the move from company review to job review
- documentation tuned to how the workflow is actually used

## Testing Expectations

Before a roadmap item is considered done:

- relevant unit tests pass
- relevant integration tests pass
- new adapters include fixture coverage
- new CLI surfaces include command coverage
- docs are updated when workflow behavior changes

## Immediate Next Steps

1. Build the RemoteOK adapter (Step 1) — no dependencies, can start immediately.
2. Build the HN Who's Hiring adapter (Step 2) — no dependencies, can start immediately.
3. Use the current workflow in practice and capture friction for the Hardening and Refinement tracks.
