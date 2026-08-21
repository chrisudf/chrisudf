# Setup

Profile README repo. Because it's named `chrisudf` (same as the account),
GitHub renders `README.md` on <https://github.com/chrisudf>. It has to be
**public**, and the README has to be on the **default branch**.

## What's in here

| path | what it does |
|---|---|
| `README.md` | banner + contribution snake, nothing else |
| `assets/header.svg` | the banner — animated, self-contained, no external requests |
| `assets/fonts/*.woff2` | Orbitron 900 + JetBrains Mono, latin subsets, embedded into the SVG |
| `scripts/build_header.py` | regenerates `assets/header.svg` |
| `.github/workflows/snake.yml` | eats the contribution grid, pushes SVGs to the `output` branch |

## First push

```bash
gh repo create chrisudf --public --source . --remote origin --push
```

Then run the snake once — until it does, the graph image 404s:

```bash
gh workflow run "generate snake animation" --repo chrisudf/chrisudf
```

It writes three files to the `output` branch: `snake.svg` (stock palette),
`snake-dark.svg`, and `snake-neon.svg` — magenta snake `#ff2a6d` eating neon
green cells `#19f6a4`. The README points at `snake-neon.svg`; swap the
`<source>` URLs to change that. After the first run it re-runs every 12h.

## Editing the banner

Everything lives in `scripts/build_header.py` — the palette constants and the
copy strings are at the top:

```bash
python scripts/build_header.py
```

Palette is lifted from `chrisudf/cq-portfolio` (`src/app/globals.css`):

| token | value |
|---|---|
| bg | `#07070d` |
| cyan | `#00f0ff` |
| magenta | `#ff2a6d` |
| yellow | `#fcee0a` |
| neon green | `#19f6a4` |
| muted | `#6b7a8d` |

The name uses the same split glitch as the portfolio hero — magenta on the top
45%, cyan on the bottom, both jumping a few px near the end of each cycle.

### Why the fonts are embedded

GitHub proxies README images through camo, which blocks every external
request the SVG could make — a `<link>` to Google Fonts would silently fall
back to a system face. A `@font-face` with a `data:` URI needs no request, so
Orbitron renders on GitHub exactly like it does locally. Cost is ~63 KB for
the whole banner.

## Local preview

```bash
python -m http.server 8899 --directory .
```

`preview.local.html` is a GitHub-rendered snapshot of the README (gitignored).
