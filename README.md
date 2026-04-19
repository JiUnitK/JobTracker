# JobTracker

JobTracker is a local-first tool for discovering companies, promoting the right ones into active tracking, and then surfacing specific jobs from those tracked companies.

The intended user journey is:

1. discover promising companies first
2. resolve and promote the companies worth monitoring
3. collect jobs from those tracked companies
4. drill down into the specific roles that are worth attention now

## What It Does

JobTracker currently supports:

- company discovery from search-style and ecosystem-style discovery sources
- company scoring and resolution status tracking
- promotion of discovered companies into tracked monitoring
- tracked job collection from Greenhouse, Lever, and Ashby
- repeated-run job lifecycle tracking
- explainable scoring for jobs and discovered companies
- CLI reporting for discoveries, companies, and jobs

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

### 3. Add day-1 discovery inputs

Start with company discovery, not tracked job boards.

Edit [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml) and add discovery evidence to one or both of:

- `company_search.params.results`
- `austin_ecosystem.params.entries`

Then enable the source(s) you want to use.

The easiest day-1 setup is:

- add a small list of Austin or remote-friendly companies you want to evaluate
- include careers URLs when you know them
- prefer ATS-backed careers URLs when possible

### 4. Run company discovery

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies inbox
```

This is the front door of the product.

### 5. Review the discovery layer

Use these views first:

```powershell
python -m jobtracker discover companies top --limit 10
python -m jobtracker discover companies list --resolution-status resolved --limit 15
```

At this stage, the goal is not to review every job. The goal is to decide which companies deserve tracking.

### 6. Promote the companies worth monitoring

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

### 7. Run tracked job collection

Once you have promoted at least one company, collect tracked jobs:

```powershell
python -m jobtracker run
```

Promotion is DB-backed, so promoted companies can flow into tracked monitoring without manually editing `config/sources.yaml` first.

### 8. Drill down into jobs from tracked companies

This is the second layer of the workflow.

For one company:

```powershell
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

- populate discovery inputs
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

- `company_search.params.results`: search-style discovery evidence
- `austin_ecosystem.params.entries`: ecosystem-list discovery evidence

Profile tuning lives in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml).

## Useful Commands

```powershell
python -m jobtracker discover companies inbox
python -m jobtracker discover companies top
python -m jobtracker discover companies promote --company "Pulse Labs"
python -m jobtracker run
python -m jobtracker jobs list --company "Pulse Labs"
python -m jobtracker jobs top --remote-only --limit 10
python -m jobtracker export csv --output reports/jobs.csv
python -m pytest
```
