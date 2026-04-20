# Workflow Review Checklist

Use this checklist when validating the documented JobTracker workflow.

## Setup

- `python -m jobtracker config validate` works
- `python -m jobtracker sources list` shows the configured sources clearly
- The source/profile/scoring config files are easy to find and edit

## Daily Loop

- `python -m jobtracker discover companies run` is the obvious first step
- `python -m jobtracker discover companies fingerprint` is documented for unresolved companies
- `python -m jobtracker discover companies inbox` is the obvious first review view
- `python -m jobtracker discover companies review --company ...` is the obvious single-company review view
- There is a clear command for resolving, promoting, or ignoring discoveries
- There is a clear command for drilling into jobs for one selected company
- There is a clear command for reviewing top jobs after company selection
- There is a clear command for reviewing recent jobs
- There is a clear command for reviewing stale or closed jobs
- There is a clear command for reviewing company activity

## Weekly Loop

- There is a clear shortlist command for weekly discovery review
- The weekly loop includes discovery, fingerprinting, and inbox review before job review
- There is a clear command for reviewing discovered companies
- The workflow shows how to resolve and promote promising discoveries
- The workflow makes it clear that company discovery comes before broad job review
- There is a CSV export path for deeper review
- There is a Markdown export path for compact snapshots
- The workflow explains when to update profile, source, and scoring config
- The workflow points to discovery source tuning when the inbox is too noisy or too thin

## Usability

- The key commands are easy to remember
- The output is readable without extra post-processing
- The documented workflow does not require awkward manual database inspection
- The score interpretation guidance is concrete enough to use in practice
- The discovery workflow makes it obvious how a company moves from candidate to tracked
- The discovery workflow makes the next action obvious from inbox and review output
- The transition from discovered company to company-specific job drill-down feels natural

## Follow-up

- Any friction discovered during real usage should be captured for future workflow refinements or 8B hardening
