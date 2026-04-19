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

- autonomous company discovery from enabled search, ecosystem, and directory sources
- company scoring and resolution status tracking
- ranked ATS and careers-surface resolution targets for discovered companies
- company review flow with explicit next actions and resolution candidate visibility
- promotion of discovered companies into tracked monitoring
- tracked job collection from Greenhouse, Lever, and Ashby
- repeated-run job lifecycle tracking
- explainable scoring for jobs and discovered companies
- CLI reporting for discoveries, companies, and jobs

## Current State

The company-first workflow is in place and autonomous discovery is now the front door of the product.

Today:

- JobTracker can discover companies from enabled discovery sources
- discovery review shows the best current ATS or careers target for each company candidate
- promoted companies flow into tracked job monitoring automatically
- job review works as a second-layer drill-down from company review

Current limitation:

- discovery still depends on configured discovery sources in [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml), so completely zero-config discovery is not there yet

The next work is tracked in [docs/v1-roadmap.md](/abs/path/F:/Projects/JobTracker/docs/v1-roadmap.md).

## Quick Start

This quick start is meant to be day 1 of a daily or weekly cadence.

### 1. Install the project

```powershell
python -m pip install -e .[dev]
```

### 2. Validate config and create the database

```powershell
python -m jobtracker config validate
python -m jobtracker db upgrade
```

### 3. Run autonomous company discovery

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies inbox
```

This is the front door of the product.

If discovery returns little or nothing, that usually means your discovery sources in [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml) still need better source URLs or query templates.

### 4. Review the discovery layer

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

### 5. Resolve, promote, or ignore companies

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

### 6. Run tracked job collection

Once you have promoted at least one company, collect tracked jobs:

```powershell
python -m jobtracker run
```

Promotion is DB-backed, so promoted companies can flow into tracked monitoring without manually editing `config/sources.yaml` first.

### 7. Drill down into jobs from tracked companies

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
- review discoveries
- promote companies
- collect tracked jobs
- inspect jobs from those companies

For the recurring workflow after that, use:

- [docs/workflow.md](/abs/path/F:/Projects/JobTracker/docs/workflow.md)
- [docs/workflow-review-checklist.md](/abs/path/F:/Projects/JobTracker/docs/workflow-review-checklist.md)

That documentation covers the day-to-day and week-to-week cadence after the initial setup.

## Config Notes

Tracked ATS source identifiers in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml):

- `greenhouse.params.board_tokens`: Greenhouse board tokens such as `stripe`
- `lever.params.account_names`: Lever account names used in `https://api.lever.co/v0/postings/{account}`
- `ashby.params.job_board_names`: Ashby job board names used in `https://api.ashbyhq.com/posting-api/job-board/{name}`

Discovery inputs in [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml):

- `company_search.params.results_urls`: fetchable search-style discovery inputs
- `company_search.params.query_url_template`: query-driven search endpoint template
- `austin_ecosystem.params.entries_urls`: fetchable ecosystem-list discovery inputs
- `austin_ecosystem.params.query_url_template`: query-driven ecosystem endpoint template
- `company_directory.params.entries_urls`: fetchable directory-style discovery inputs
- `company_directory.params.query_url_template`: query-driven directory endpoint template
- `company_search.params.results`: seeded fallback search-style discovery evidence
- `austin_ecosystem.params.entries`: seeded fallback ecosystem-list discovery evidence
- `company_directory.params.entries`: seeded fallback directory-style discovery evidence

Profile tuning lives in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml).

## Useful Commands

```powershell
python -m jobtracker discover companies run
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
