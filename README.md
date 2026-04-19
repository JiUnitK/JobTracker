# JobTracker

JobTracker is a local-first tool for discovering, tracking, and ranking job opportunities in Austin, TX and remote-friendly markets.

This repository currently contains the v1 planning documents plus the initial Python project scaffold for implementation.

## Quick Start

Create a virtual environment if desired, then install the project in editable mode:

```powershell
python -m pip install -e .[dev]
```

Validate the default configuration:

```powershell
python -m pip install -e .[dev]
python -m jobtracker config validate
```

Create or upgrade the local database schema:

```powershell
python -m jobtracker db upgrade
```

Add one or more Greenhouse board tokens in `config/sources.yaml`, then run collection:

```powershell
python -m jobtracker run
```

Inspect source status and adapter coverage:

```powershell
python -m jobtracker sources list
```

Configure source identifiers in `config/sources.yaml`:

- `greenhouse.params.board_tokens`: Greenhouse board tokens such as `stripe`
- `lever.params.account_names`: Lever account names used in `https://api.lever.co/v0/postings/{account}`
- `ashby.params.job_board_names`: Ashby job board names used in `https://api.ashbyhq.com/posting-api/job-board/{name}`

Run the test suite:

```powershell
python -m pytest
```
