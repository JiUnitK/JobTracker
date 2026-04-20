# JobTracker Roadmap

## Goal

Make JobTracker reliable and pleasant as a company-first workflow:

1. run discovery
2. review discovered companies
3. improve unresolved companies with ATS fingerprinting
4. promote the right companies
5. collect jobs from those companies
6. drill into the jobs that matter

This roadmap is intentionally forward-looking. Completed milestones have been removed so the document stays focused on the current state and the next work.

## Current State

JobTracker already has:

- a local-first Python CLI application
- persistent storage, migrations, and test coverage
- autonomous discovery from RemoteOK, HN Who's Hiring, SerpAPI Google Jobs, local Austin ecosystem data, and local company-directory data
- ATS fingerprinting for unresolved companies across Greenhouse, Lever, and Ashby
- company scoring and ATS/careers resolution with ranked candidates
- company review, promotion, ignore, and job drill-down flows
- DB-backed promotion from discovered company into tracked monitoring
- tracked job collection from Greenhouse, Lever, and Ashby
- job lifecycle tracking and scoring

Current verification baseline:

- `python -m pytest` passes
- `python -m jobtracker config validate` passes
- `python -m jobtracker db upgrade` passes
- `python -m jobtracker discover companies run` passes
- `python -m jobtracker discover companies fingerprint` passes
- `python -m jobtracker run` passes

## Current Workflow

The intended workflow is now:

1. `python -m jobtracker discover companies run`
2. `python -m jobtracker discover companies fingerprint`
3. `python -m jobtracker discover companies inbox`
4. `python -m jobtracker discover companies review --company "..."`
5. resolve, promote, or ignore companies
6. `python -m jobtracker run`
7. `python -m jobtracker jobs top --company "..."`

The product is meaningfully discovery-first. Users should not need to manually find companies before starting the workflow.

## Remaining Gaps

The biggest remaining gaps are operational quality and signal quality:

- source failures need clearer per-source diagnostics
- live fetches need stronger timeout and retry behavior
- discovery output needs iteration after real usage
- keyword matching is still relatively simple
- local curated source data will need ongoing tuning

## Next Tracks

### Workflow Hardening

Objective:

Make the current company-first workflow dependable for daily or weekly use.

Focus:

- timeout and retry policy for live sources
- clearer per-source diagnostics on failure
- better handling when optional API keys such as `SERPAPI_KEY` are missing
- unattended-run ergonomics, including exit codes and structured output options

### Signal Quality

Objective:

Improve candidate quality while reducing inbox noise.

Focus:

- broaden keyword matching beyond exact title snippets
- add exclude terms for common false positives
- improve HN comment parsing edge cases
- improve SerpAPI field mapping as real payloads are observed
- tune curated Austin and broader company-directory data

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

1. Run the current discovery workflow against real network sources and capture failures/noise.
2. Prioritize hardening around the sources that are most useful but least reliable.
3. Tune discovery scoring and filters based on real inbox quality.
