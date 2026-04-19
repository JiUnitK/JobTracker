# Workflow Review Checklist

Use this checklist when validating the documented JobTracker workflow.

## Setup

- `python -m jobtracker config validate` works
- `python -m jobtracker sources list` shows the configured sources clearly
- The source/profile/scoring config files are easy to find and edit

## Daily Loop

- `python -m jobtracker run` is the obvious first step
- There is a clear command for reviewing top jobs
- There is a clear command for reviewing recent jobs
- There is a clear command for reviewing stale or closed jobs
- There is a clear command for reviewing company activity

## Weekly Loop

- There is a clear shortlist command for weekly review
- There is a CSV export path for deeper review
- There is a Markdown export path for compact snapshots
- The workflow explains when to update profile, source, and scoring config

## Usability

- The key commands are easy to remember
- The output is readable without extra post-processing
- The documented workflow does not require awkward manual database inspection
- The score interpretation guidance is concrete enough to use in practice

## Follow-up

- Any friction discovered during real usage should be captured for future 8A refinements or 8B hardening
