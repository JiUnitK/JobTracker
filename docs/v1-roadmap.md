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

The biggest remaining product gap is zero-config discovery startup.

Today, autonomous discovery works through enabled discovery sources in [config/company_discovery.yaml](/abs/path/F:/Projects/JobTracker/config/company_discovery.yaml). That means users still need a usable set of discovery endpoints or feeds configured before discovery becomes productive.

The longer-term target is:

- discovery that feels useful immediately
- less manual source setup before day 1
- smoother unattended recurring use

## Next Tracks

### Zero-Config Discovery Bootstrap

Objective:

Reduce how much source setup is required before discovery becomes useful.

Focus:

- ship better starter discovery-source examples or defaults
- make it easier to understand what to configure first
- reduce the "empty inbox on day 1" problem

### Workflow Hardening

Objective:

Make the current company-first workflow dependable for daily or weekly use.

Focus:

- better failure handling
- timeout and retry policy
- clearer source diagnostics
- unattended-run ergonomics

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

1. Use the current autonomous discovery workflow in practice and capture the highest-friction moments.
2. Prioritize zero-config discovery improvements if day-1 setup still feels too manual.
3. Pull hardening work from the workflow pain that shows up in real use.
