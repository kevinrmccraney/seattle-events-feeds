# Seattle Events Feed Producers v4

This repository contains the venue/API scrapers only. It does **not** write to Supabase.
Each source is transformed into a normalized RSS 2.0 feed with structured `seattle:*` fields.

Current feeds:

- `docs/feeds/neumos.xml` — Carbonhouse
- `docs/feeds/barboza.xml` — Carbonhouse
- `docs/feeds/vera.xml` — DICE; Vera Project + Black Lodge, `music:gig` only
- `docs/feeds/showbox.xml` — Showbox Presents, Seattle venues only

## Architecture

```text
venue/API -> source adapter -> normalized Event -> RSS file -> GitHub Pages
```

There is deliberately no database code here. The separate importer consumes these feeds.

## Deploy to GitHub

1. Create a GitHub repository and place these files at its root.
2. Add repository secret `DICE_API_KEY` under **Settings -> Secrets and variables -> Actions**.
3. Under **Settings -> Pages**, select **Deploy from a branch**, branch `main`, folder `/docs`.
4. Run **Actions -> Refresh normalized RSS feeds -> Run workflow** once.
5. The scheduled job then runs weekly at `13:17 UTC` every Monday.

For a repo named `seattle-event-feeds`, URLs will look like:

```text
https://USERNAME.github.io/seattle-event-feeds/feeds/neumos.xml
https://USERNAME.github.io/seattle-event-feeds/feeds/barboza.xml
https://USERNAME.github.io/seattle-event-feeds/feeds/vera.xml
https://USERNAME.github.io/seattle-event-feeds/feeds/showbox.xml
```

## Failure behavior

Each producer also writes `docs/status/SOURCE.json`.

On success it contains the generation time and event count. On failure it contains an error code/message such as `dice_api_auth_failed`.

A failed source **does not overwrite its previous good RSS file**. This is why generated feeds/status are committed back to the repository rather than published as an ephemeral Pages artifact. The importer reads the status sidecar first and will not mark events missing when the producer failed.

If the GitHub repository blocks Actions from pushing to `main`, allow `GITHUB_TOKEN` write access or use an unprotected generated-data branch.

## Run locally

```bash
python -m pip install -r requirements.txt
DICE_API_KEY='...' python -m seattle_feeds.main --output-dir docs
```

One source only:

```bash
python -m seattle_feeds.main --source neumos --output-dir docs
```

## Tests

```bash
python -m unittest discover -s tests -v
```
