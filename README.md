# JobTracker

JobTracker is a local-first tool for discovering companies, promoting the right ones into active tracking, and then surfacing specific jobs from those tracked companies.

The intended user journey is:

1. discover promising companies first
2. review and resolve the right companies
3. promote the companies worth monitoring
4. collect jobs from those tracked companies
5. drill down into the specific roles that are worth attention now

## What It Does

JobTracker currently supports:

- instant open-web job search through Brave Search when `BRAVE_SEARCH_API_KEY` is configured
- autonomous company discovery from live sources
- RemoteOK discovery with no API key
- Hacker News "Who is hiring?" discovery with no API key
- SerpAPI Google Jobs discovery when `SERPAPI_KEY` is configured
- ATS fingerprinting for unresolved companies across Greenhouse, Lever, and Ashby
- company scoring and resolution status tracking
- ranked ATS and careers-surface resolution targets
- company review flow with explicit next actions and resolution candidate visibility
- promotion of discovered companies into tracked monitoring
- tracked job collection from Greenhouse, Lever, and Ashby
- repeated-run job lifecycle tracking
- explainable scoring for jobs and discovered companies
- CLI reporting for discoveries, companies, and jobs

## Current State

The company-first workflow is in place and autonomous discovery is now the front door of the product.

Today:

- JobTracker can run a side-effect-light instant search for fresh postings without writing to the database
- JobTracker can discover companies from enabled discovery sources
- RemoteOK and HN discovery can work without external accounts
- SerpAPI search discovery works when `SERPAPI_KEY` is available in `.env`
- discovery review shows the best current ATS or careers target for each company candidate
- unresolved companies can be fingerprinted against Greenhouse, Lever, and Ashby
- promoted companies flow into tracked job monitoring automatically
- job review works as a second-layer drill-down from company review

Current limitation:

- instant job search requires `BRAVE_SEARCH_API_KEY` and freshness depends on the age signals exposed by search results
- discovery quality depends on enabled source quality, API availability, and how well configured queries match your target market

The next work is tracked in [docs/v1-roadmap.md](/abs/path/F:/Projects/JobTracker/docs/v1-roadmap.md).

## Quick Start

This quick start is meant to be day 1 of a daily or weekly cadence.

### 1. Install the project

```powershell
python -m pip install -e .[dev]
```

### 2. Optional: configure API keys

RemoteOK and HN Who's Hiring do not require an API key.

If you want instant open-web job search, add a Brave Search key. If you want Google Jobs company discovery too, add a SerpAPI key:

```powershell
BRAVE_SEARCH_API_KEY=your_key_here
SERPAPI_KEY=your_key_here
```

If you do not want to use SerpAPI yet, set `company_search.enabled: false` under `discovery_sources` in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml).

### 3. Validate config and create the database

```powershell
python -m jobtracker config validate
python -m jobtracker db upgrade
```

### 4. Search fresh postings now

Instant job search is the fastest front door when you want current postings without building a company watchlist first:

```powershell
python -m jobtracker search jobs
python -m jobtracker search jobs --days 7 --query "customer success" --location Remote --limit 25
python -m jobtracker search jobs --include-unknown-age
python -m jobtracker search jobs --json
```

This workflow uses [config/search_terms.yaml](/abs/path/F:/Projects/JobTracker/config/search_terms.yaml), [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml), and [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml). It returns structured results and does not write to the database by default.

### 5. Run autonomous company discovery

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies inbox
```

This is the front door of the product.

The default discovery config can pull from:

- `remote_ok`: RemoteOK public API
- `hn_whos_hiring`: HN Algolia API for the monthly Who's Hiring thread
- `company_search`: SerpAPI Google Jobs, when `SERPAPI_KEY` is set

### 6. Improve unresolved companies with ATS fingerprinting

If the inbox contains promising companies with `resolution=unresolved`, run:

```powershell
python -m jobtracker discover companies fingerprint
python -m jobtracker discover companies inbox
```

Fingerprinting probes likely Greenhouse, Lever, and Ashby board URLs and adds resolution candidates when it finds matches.

### 7. Review the discovery layer

Use these views first:

```powershell
python -m jobtracker discover companies top --limit 10
python -m jobtracker discover companies review --company "Pulse Labs"
python -m jobtracker discover companies list --resolution-status resolved --limit 15
```

At this stage, the goal is not to review every job. The goal is to decide which companies deserve tracking.

The `review` command is the best single-company bridge in the workflow. It shows:

- the company's current status and best resolution target
- the next action to take
- the resolution candidates currently on record
- tracked jobs inline when the company has already been promoted

### 8. Resolve, promote, or ignore companies

If a company already has a good Greenhouse, Lever, or Ashby resolution:

```powershell
python -m jobtracker discover companies promote --company "Pulse Labs"
```

If a company has multiple candidate resolutions, choose one first:

```powershell
python -m jobtracker discover companies resolve --company "ConflictCo" --resolution-url "https://jobs.lever.co/conflictco"
python -m jobtracker discover companies promote --company "ConflictCo"
```

If a company is not relevant:

```powershell
python -m jobtracker discover companies ignore --company "Lakeside Robotics"
```

### 9. Run tracked job collection

Once you have promoted at least one company, collect tracked jobs:

```powershell
python -m jobtracker run
```

Promotion is DB-backed, so promoted companies can flow into tracked monitoring without manually editing `config/sources.yaml` first.

### 10. Drill down into jobs from tracked companies

This is the second layer of the workflow.

For one company:

```powershell
python -m jobtracker discover companies review --company "Pulse Labs"
python -m jobtracker jobs list --company "Pulse Labs" --sort-by priority --limit 10
python -m jobtracker jobs top --company "Pulse Labs" --limit 5
```

For a broader tracked-job review:

```powershell
python -m jobtracker jobs top --limit 10
python -m jobtracker jobs top --remote-only --limit 10
python -m jobtracker companies list --recent-days 14 --limit 20
```

## After Day 1

The README is intentionally focused on getting a user through day 1:

- run company discovery
- fingerprint unresolved companies when useful
- review discoveries
- promote companies
- collect tracked jobs
- inspect jobs from those companies

For the recurring workflow after that, use:

- [docs/workflow.md](/abs/path/F:/Projects/JobTracker/docs/workflow.md)
- [docs/workflow-review-checklist.md](/abs/path/F:/Projects/JobTracker/docs/workflow-review-checklist.md)
- [docs/discovery-sources.md](/abs/path/F:/Projects/JobTracker/docs/discovery-sources.md)

## Config Notes

Tracked ATS source identifiers in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml):

- `greenhouse.params.board_tokens`: Greenhouse board tokens such as `stripe`
- `lever.params.account_names`: Lever account names used in `https://api.lever.co/v0/postings/{account}`
- `ashby.params.job_board_names`: Ashby job board names used in `https://api.ashbyhq.com/posting-api/job-board/{name}`

Discovery sources live under `discovery_sources` in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml):

- `company_search`: SerpAPI Google Jobs through `query_url_template`, using `SERPAPI_KEY`
- `remote_ok`: RemoteOK public API at `https://remoteok.com/api`
- `hn_whos_hiring`: HN Algolia API, auto-detecting the current monthly thread

Discovery queries live under `discovery_queries` in [config/search_terms.yaml](/abs/path/F:/Projects/JobTracker/config/search_terms.yaml). Discovered-company scoring lives under `company_discovery` in [config/scoring.yaml](/abs/path/F:/Projects/JobTracker/config/scoring.yaml).

Instant search sources live under `instant_search_sources` in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml). Instant search query defaults live under `instant_job_search` in [config/search_terms.yaml](/abs/path/F:/Projects/JobTracker/config/search_terms.yaml).

Profile tuning lives in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml).

## Useful Commands

```powershell
python -m jobtracker search jobs
python -m jobtracker discover companies run
python -m jobtracker discover companies fingerprint
python -m jobtracker discover companies inbox
python -m jobtracker discover companies top
python -m jobtracker discover companies review --company "Pulse Labs"
python -m jobtracker discover companies promote --company "Pulse Labs"
python -m jobtracker run
python -m jobtracker jobs list --company "Pulse Labs"
python -m jobtracker jobs top --remote-only --limit 10
python -m jobtracker export csv --output reports/jobs.csv
python -m pytest
```
