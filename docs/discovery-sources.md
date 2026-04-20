# Discovery Sources

Company discovery is the entry point for JobTracker. The default config uses live automated sources so discovery results are tied to current hiring signals rather than hand-maintained company lists.

Discovery configuration is split across the main config files:

- discovery sources live under `discovery_sources` in `config/sources.yaml`
- discovery queries live under `discovery_queries` in `config/search_terms.yaml`
- discovered-company scoring lives under `company_discovery` in `config/scoring.yaml`

## Default Sources

### `company_search`

Purpose:

- query-driven job search discovery
- best for Austin and remote keyword searches

Default setup:

- uses SerpAPI Google Jobs through `company_search.params.query_url_template`
- requires `SERPAPI_KEY` in repo-root `.env`

Example `.env`:

```powershell
SERPAPI_KEY=your_key_here
```

If you do not want to use SerpAPI yet, set `enabled: false` for `company_search` in `config/sources.yaml`.

### `remote_ok`

Purpose:

- live remote-job discovery from RemoteOK
- no API key required

Recommended URL:

```yaml
feed_url: "https://remoteok.com/api"
```

This source fetches remote jobs and filters them locally against your discovery keywords.

### `hn_whos_hiring`

Purpose:

- live company discovery from the monthly Hacker News "Who is hiring?" thread
- no API key required

Default behavior:

- auto-detects the current thread through HN Algolia
- fetches comments as structured JSON
- parses company name, role, location, remote/hybrid signal, and ATS/careers URLs when present

Optional pinning:

```yaml
params:
  story_id: "12345678"
```

Use `story_id` only when you want to force a specific monthly thread.

## Recommended Starting Setup

For day 1:

- keep `remote_ok` enabled
- keep `hn_whos_hiring` enabled
- enable `company_search` only if `SERPAPI_KEY` is configured

This keeps discovery automated while avoiding manual seed lists.

## After Discovery

Run:

```powershell
python -m jobtracker discover companies run
python -m jobtracker discover companies inbox
```

If many companies are unresolved, run ATS fingerprinting:

```powershell
python -m jobtracker discover companies fingerprint
```

Fingerprinting probes likely Greenhouse, Lever, and Ashby boards for unresolved companies and adds resolution candidates when it finds matches.
