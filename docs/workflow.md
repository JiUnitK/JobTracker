# JobTracker Workflow

## Goal

Use JobTracker as a lightweight recurring system for:

- discovering new opportunities
- tracking companies with sustained hiring activity
- reviewing which roles are worth attention now
- noticing when roles go stale or disappear

This guide is intentionally practical. It assumes the tool is running locally and that the main workflow is CLI-first.

## Before You Start

Make sure these are in place:

1. Source identifiers are configured in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml)
2. Your profile preferences are reasonably current in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml)
3. The database schema is current

```powershell
python -m jobtracker db upgrade
```

Useful commands to sanity-check setup:

```powershell
python -m jobtracker config validate
python -m jobtracker sources list
```

## Core Idea

Treat JobTracker as a review tool, not just a scraper.

The recurring loop is:

1. run collection
2. review top jobs
3. review company activity
4. review stale/closed movement
5. export a report when you want a durable snapshot
6. tune profile and source config based on what you learned

## Daily Workflow

The daily workflow is meant to be short, roughly 5-15 minutes.

### 1. Run collection

```powershell
python -m jobtracker run
```

If a live source is unavailable, check:

```powershell
python -m jobtracker sources list
```

### 2. Review top remote or Austin roles

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
- jobs with good fit but fresh hiring signals
- companies showing up repeatedly across days

### 3. Review newly relevant jobs

Use a recent window to focus on what changed recently:

```powershell
python -m jobtracker jobs list --recent-days 3 --sort-by recent --limit 20
```

This is the best quick “what is new?” view right now.

### 4. Review stale jobs

This helps you avoid chasing opportunities that are aging out:

```powershell
python -m jobtracker jobs list --status stale --sort-by recent --limit 20
```

If you want to see what is effectively gone:

```powershell
python -m jobtracker jobs list --status closed --limit 20
```

### 5. Review company momentum

```powershell
python -m jobtracker companies list --recent-days 14 --limit 20
```

This is useful for spotting companies that may deserve broader attention even if one specific job is not perfect.

## Weekly Workflow

The weekly workflow is meant to be a more deliberate review, roughly 20-40 minutes.

### 1. Run a fresh collection pass

```powershell
python -m jobtracker run
```

### 2. Review the best current shortlist

```powershell
python -m jobtracker jobs top --limit 25
python -m jobtracker jobs top --remote-only --limit 15
python -m jobtracker jobs list --location "Austin" --min-score 60 --limit 20
```

Suggested questions:

- Which roles still look attractive after a week?
- Which companies keep appearing with strong hiring signals?
- Are there companies you should start tracking even before a perfect role appears?

### 3. Review company activity

```powershell
python -m jobtracker companies list --recent-days 30 --limit 25
```

This is where company-level tracking becomes especially useful.

### 4. Review new company discoveries

```powershell
python -m jobtracker discover companies top --limit 15
python -m jobtracker discover companies list --resolution-status resolved --limit 20
```

Suggested questions:

- Which newly discovered companies look worth tracking even if no single job is perfect yet?
- Which discoveries already have a strong ATS resolution and can move into monitoring?
- Which companies should be ignored so they stop taking review time?

### 5. Promote or ignore discoveries

If a company looks promising and already resolves to Greenhouse, Lever, or Ashby, promote it into tracked monitoring:

```powershell
python -m jobtracker discover companies promote --company "Pulse Labs"
```

If a discovery has multiple competing resolutions, explicitly choose one first:

```powershell
python -m jobtracker discover companies resolve --company "ConflictCo" --resolution-url "https://jobs.lever.co/conflictco"
python -m jobtracker discover companies promote --company "ConflictCo"
```

If a discovery is not relevant, ignore it:

```powershell
python -m jobtracker discover companies ignore --company "Lakeside Robotics"
```

### 6. Export a weekly snapshot

CSV for spreadsheet-style review:

```powershell
python -m jobtracker export csv --output reports/weekly-jobs.csv --limit 100
```

Markdown for a compact review artifact:

```powershell
python -m jobtracker export markdown --output reports/weekly-jobs.md --limit 25
```

### 7. Tune your configuration

At the end of the weekly review, update config based on what you learned:

- add or remove source identifiers in [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml)
- use company discovery promotion for ATS-backed companies you want monitored without manually editing source lists first
- refine target titles and skills in [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml)
- adjust weighting in [config/scoring.yaml](/abs/path/F:/Projects/JobTracker/config/scoring.yaml) if the ranking feels off

## How To Read Scores

### Fit Score

This answers:

- how well does this role match the target profile?

High fit usually means:

- title alignment
- preferred skills show up
- location/workplace arrangement matches preferences
- seniority looks right

### Hiring Score

This answers:

- how active does the hiring signal look?

High hiring usually means:

- fresh posting or recent observation
- repeated observations across runs
- multiple related openings at the same company
- a high-confidence ATS source

### Priority Score

This is the main ranking score.

Interpret it as:

- the best single score for deciding what to review first

## Recommended Review Views

Use these as your default “muscle memory” commands.

### Daily shortlist

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

### Recent changes

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

### Discovery review

```powershell
python -m jobtracker discover companies top --limit 10
```

### Resolved discovery candidates

```powershell
python -m jobtracker discover companies list --resolution-status resolved --limit 15
```

## Lightweight Scheduling

For a simple recurring workflow on Windows, use Task Scheduler to run:

```powershell
python -m jobtracker run
```

Suggested cadence:

- daily if you want an active search rhythm
- two or three times per week if you want lower maintenance
- weekly at minimum if you mostly care about company momentum and broad opportunity tracking

The reporting commands do not need to be scheduled automatically at first. It is usually better to run them when you sit down to review.

## When To Update Config

Update [config/profile.yaml](/abs/path/F:/Projects/JobTracker/config/profile.yaml) when:

- too many low-fit roles appear near the top
- a new target role family becomes relevant
- your location preferences change
- you discover useful or noisy keywords

Update [config/sources.yaml](/abs/path/F:/Projects/JobTracker/config/sources.yaml) when:

- you want to watch more companies on Greenhouse, Lever, or Ashby
- a source is noisy and should be disabled temporarily
- you want to expand the set of tracked company boards

Update [config/scoring.yaml](/abs/path/F:/Projects/JobTracker/config/scoring.yaml) when:

- the ranking is technically correct but not practically helpful
- you care more about fit than urgency, or vice versa

## Friction Checklist

As you use the workflow in practice, pay attention to:

- commands you run repeatedly with awkward flags
- views you wish existed but do not
- places where score explanations are not intuitive
- exports that still need manual cleanup
- cases where stale/closed behavior feels wrong

Those are good candidates for future workflow improvements or Milestone 8B hardening work.
