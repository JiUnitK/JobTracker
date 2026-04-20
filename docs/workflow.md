# JobTracker Workflow

## Goal

Use JobTracker as a recurring, company-first workflow for:

- discovering promising companies from live sources
- deciding which companies deserve active monitoring
- resolving companies to ATS or careers surfaces
- collecting jobs from tracked companies
- drilling down into specific roles only after a company has earned attention
- reviewing company and job movement over time

This guide picks up after day 1 onboarding. The README covers day 1. This document covers the daily and weekly cadence after that.

## Core Idea

Treat company discovery as the top of the funnel and job review as the deeper layer.

The recurring loop is:

1. run company discovery
2. optionally fingerprint unresolved companies
3. review the discovery inbox
4. review one company at a time when needed
5. resolve, promote, or ignore companies
6. run tracked job collection
7. drill down into jobs for the companies that matter
8. review the broader tracked-job shortlist
9. tune config based on what you learned

## Daily Workflow

The daily workflow should be short, roughly 5-15 minutes.

### 1. Run company discovery

```powershell
python -m jobtracker discover companies run
```

Discovery can pull from RemoteOK, HN Who's Hiring, and Brave Search depending on what is enabled under `discovery_sources` in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml).

### 2. Improve unresolved companies when needed

If the last discovery run found promising but unresolved companies:

```powershell
python -m jobtracker discover companies fingerprint
```

This probes likely Greenhouse, Lever, and Ashby board URLs and adds resolution candidates when it finds matches.

### 3. Open the discovery inbox

```powershell
python -m jobtracker discover companies inbox
```

This should be the default review entry point.

What to look for:

- companies with strong `discovery_score`
- discoveries that show `Next: Promote`
- discoveries that show `Next: Resolve`
- repeated appearances across discovery sources
- promising unresolved companies that may benefit from fingerprinting
- obvious ignores you can clear out quickly

### 4. Review one promising company directly

When one company stands out, open the company review view:

```powershell
python -m jobtracker discover companies review --company "Pulse Labs"
```

This is the cleanest bridge from discovery into action. It shows:

- the company's current status
- the best current ATS or careers target
- the next action to take
- the known resolution candidates
- tracked jobs inline once the company has already been promoted

### 5. Resolve, promote, or ignore discoveries

If a company looks promising and already has a strong ATS resolution:

```powershell
python -m jobtracker discover companies promote --company "Pulse Labs"
```

If you need to choose a specific resolution first:

```powershell
python -m jobtracker discover companies resolve --company "ConflictCo" --resolution-url "https://jobs.lever.co/conflictco"
python -m jobtracker discover companies promote --company "ConflictCo"
```

If a company is not relevant:

```powershell
python -m jobtracker discover companies ignore --company "Lakeside Robotics"
```

### 6. Run tracked job collection

```powershell
python -m jobtracker run
```

If a tracked source is unavailable, check:

```powershell
python -m jobtracker sources list
```

### 7. Drill down into jobs for the companies that earned attention

This is the deeper layer of the workflow.

For one company:

```powershell
python -m jobtracker discover companies review --company "Pulse Labs"
python -m jobtracker jobs list --company "Pulse Labs" --sort-by priority --limit 10
python -m jobtracker jobs top --company "Pulse Labs" --limit 5
```

### 8. Review the broader tracked-job shortlist

For remote:

```powershell
python -m jobtracker jobs top --remote-only --limit 10
```

For Austin:

```powershell
python -m jobtracker jobs list --location "Austin" --sort-by priority --limit 15
```

What to look for:

- strong `priority_score`
- jobs with good fit and fresh hiring signals
- tracked companies that keep producing attractive roles

### 9. Review recent job movement

```powershell
python -m jobtracker jobs list --recent-days 3 --sort-by recent --limit 20
```

### 10. Review stale or closed jobs

```powershell
python -m jobtracker jobs list --status stale --sort-by recent --limit 20
python -m jobtracker jobs list --status closed --limit 20
```

### 11. Review company momentum

```powershell
python -m jobtracker companies list --recent-days 14 --limit 20
```

## Weekly Workflow

The weekly workflow is meant to be more deliberate, roughly 20-40 minutes.

### 1. Run discovery and fingerprinting

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies fingerprint
python -m jobtracker discover companies inbox --limit 20
```

### 2. Review and triage the discovery layer

```powershell
python -m jobtracker discover companies top --limit 25
python -m jobtracker discover companies list --resolution-status resolved --limit 20
python -m jobtracker discover companies review --company "Pulse Labs"
```

Suggested questions:

- Which companies keep reappearing strongly enough to deserve monitoring?
- Which live sources are producing good candidates?
- Which discoveries can be promoted now?
- Which discoveries should be ignored so they stop cluttering review?

### 3. Promote or ignore discoveries

```powershell
python -m jobtracker discover companies promote --company "Pulse Labs"
python -m jobtracker discover companies ignore --company "Lakeside Robotics"
```

### 4. Run tracked job collection

```powershell
python -m jobtracker run
```

### 5. Drill down into jobs for tracked companies that matter most

If a promoted or already-tracked company deserves closer review:

```powershell
python -m jobtracker discover companies review --company "Pulse Labs"
python -m jobtracker jobs list --company "Pulse Labs" --sort-by priority --limit 10
python -m jobtracker jobs top --company "Pulse Labs" --limit 5
```

### 6. Review the broad tracked-job shortlist

```powershell
python -m jobtracker jobs top --limit 25
python -m jobtracker jobs top --remote-only --limit 15
python -m jobtracker jobs list --location "Austin" --min-score 60 --limit 20
```

### 7. Review company activity

```powershell
python -m jobtracker companies list --recent-days 30 --limit 25
```

### 8. Export a weekly snapshot

CSV for spreadsheet-style review:

```powershell
python -m jobtracker export csv --output reports/weekly-jobs.csv --limit 100
```

Markdown for a compact review artifact:

```powershell
python -m jobtracker export markdown --output reports/weekly-jobs.md --limit 25
```

### 9. Tune discovery and scoring

At the end of the weekly review, update config based on what you learned:

- disable sources that are too noisy
- set `BRAVE_SEARCH_API_KEY` if Brave Search would improve discovery or instant search
- use discovery promotion for ATS-backed companies you want monitored without manually editing source lists first
- add or remove source identifiers in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml) when you want broader direct tracked coverage
- refine target titles and skills in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml)
- adjust weighting in [config/scoring.yaml](/abs/path/F:/Projects/JobTracker/config/scoring.yaml) if the ranking feels off

## Recommended Review Views

Use these as your default muscle-memory commands.

### Discovery inbox

```powershell
python -m jobtracker discover companies inbox --limit 10
```

### Discovery shortlist

```powershell
python -m jobtracker discover companies top --limit 10
```

### Single-company review

```powershell
python -m jobtracker discover companies review --company "Pulse Labs"
```

### ATS fingerprinting

```powershell
python -m jobtracker discover companies fingerprint
```

### Resolved discovery candidates

```powershell
python -m jobtracker discover companies list --resolution-status resolved --limit 15
```

### Company drill-down

```powershell
python -m jobtracker jobs list --company "Pulse Labs" --sort-by priority --limit 10
```

### Daily shortlist across tracked companies

```powershell
python -m jobtracker jobs top --limit 10
```

### Remote shortlist

```powershell
python -m jobtracker jobs top --remote-only --limit 10
```

### Austin shortlist

```powershell
python -m jobtracker jobs list --location "Austin" --sort-by priority --limit 15
```

### Recent job changes

```powershell
python -m jobtracker jobs list --recent-days 7 --sort-by recent --limit 20
```

### Stale review

```powershell
python -m jobtracker jobs list --status stale --limit 20
```

### Company momentum

```powershell
python -m jobtracker companies list --recent-days 14 --limit 20
```

## Lightweight Scheduling

For a simple recurring workflow on Windows, use Task Scheduler to run:

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies fingerprint
python -m jobtracker run
```

Suggested cadence:

- daily if you want an active discovery rhythm
- two or three times per week if you want lower maintenance
- weekly at minimum if you mostly care about company momentum and broad opportunity tracking

The reporting commands usually do not need to be scheduled automatically at first. It is better to run them when you sit down to review.

## Friction Checklist

As you use the workflow in practice, pay attention to:

- discovery sources that are too noisy
- sources that fail often enough to need better diagnostics
- commands you run repeatedly with awkward flags
- views you wish existed but do not
- places where score explanations are not intuitive
- exports that still need manual cleanup
- cases where stale or closed behavior feels wrong
- moments where the jump from company discovery to company-specific job review feels clumsy

Those are good candidates for future workflow improvements or hardening work.
