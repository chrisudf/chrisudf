# Setup

This is a **profile README** repo: because it's named `chrisudf` (same as the
account), GitHub renders `README.md` on <https://github.com/chrisudf>.
It must be **public** and the README must live on the **default branch**.

## What's in here

| path | what it does |
|---|---|
| `README.md` | the profile page |
| `assets/header.svg` | hand-written animated synthwave banner (SMIL, no JS) |
| `assets/divider.svg` | animated neon section divider |
| `assets/stats.svg` | generated stats card — **committed**, not fetched at view time |
| `scripts/gen_stats.py` | renders `assets/stats.svg` from the GitHub GraphQL API (stdlib only) |
| `.github/workflows/snake.yml` | eats the contribution grid, pushes SVGs to the `output` branch |
| `.github/workflows/stats.yml` | re-renders `assets/stats.svg` nightly and commits it |
| `.github/workflows/metrics.yml` | optional extra panel, needs a PAT (see below) |

## First push

```bash
gh repo create chrisudf --public --source . --remote origin --push
```

Then let the snake run once — until it does, the contribution graph image 404s:

```bash
gh workflow run "generate snake animation" --repo chrisudf/chrisudf
```

It writes `snake.svg`, `snake-dark.svg` and `snake-neon.svg` to the `output`
branch. `README.md` points at `snake-neon.svg` (cyan snake, magenta/violet
contribution dots). Swap the `<source>` URLs if you prefer the stock palette.

## Regenerating the stats card by hand

```bash
GITHUB_TOKEN=$(gh auth token) python scripts/gen_stats.py chrisudf assets/stats.svg
```

## Optional: metrics panel

`metrics.yml` skips every step unless `METRICS_TOKEN` exists, so it's inert
until you want it. To turn it on, create a classic PAT with the `public_repo`
scope and save it as a repo secret:

```bash
gh secret set METRICS_TOKEN --repo chrisudf/chrisudf
```

Then add `<img src="assets/metrics.svg" width="100%" />` wherever you want it.

## Local preview

```bash
python -m http.server 8899 --directory .
```

`preview.local.html` is a GitHub-rendered snapshot of the README (gitignored).
Rebuild it after editing `README.md`:

```bash
python -c "import json,subprocess,pathlib; print(subprocess.run(['gh','api','markdown','--input','-'],input=json.dumps({'text':pathlib.Path('README.md').read_text(encoding='utf-8'),'mode':'gfm'}),capture_output=True,text=True).stdout)" > body.html
```

## Third-party widgets — read before adding more

These were live/dead as of 2026-08-21, checked directly:

| service | status |
|---|---|
| `readme-typing-svg.demolab.com` | ✅ 200 |
| `github-readme-activity-graph.vercel.app` | ✅ 200 |
| `skillicons.dev`, `img.shields.io`, `komarev.com` | ✅ 200 |
| `github-readme-stats.vercel.app` | ❌ 503 — shared instance over quota |
| `streak-stats.demolab.com` | ❌ connection refused |
| `github-profile-trophy.vercel.app` | ❌ 402 Payment Required |

That's why the stats card is generated in-repo instead of fetched. If you ever
want the classic `github-readme-stats` card, self-host it on your own Vercel
account rather than pointing at the public instance.
