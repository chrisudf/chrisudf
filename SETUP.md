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
| `assets/snake*.svg` | the contribution snake, dark + light |
| `scripts/build_header.py` | regenerates `assets/header.svg` |
| `scripts/build_snake.py` | regenerates both snake SVGs |
| `.github/workflows/snake.yml` | re-renders the snake every 12h and commits it |

## First push

```bash
gh repo create chrisudf --public --source . --remote origin --push
```

Both SVGs are committed, so the README works the moment it lands — nothing
404s while you wait for a workflow.

## The snake

Not `Platane/snk`. That action only exposes `palette` / `color_snake` /
`color_dots`; its snake is a fixed length at a fixed speed, so it can't grow
or accelerate. `scripts/build_snake.py` replaces it:

- **grows** from 3.4 to 17 cells as it eats
- **accelerates** from 125 ms to 26 ms per cell, ramped over the first 80% of
  the food — so every green square it swallows makes it visibly quicker
- runs **right to left**, newest month first. Contributions cluster in the
  recent months; going left-to-right means 20 seconds of crawling through
  empty cells before anything happens. Starting at the food means it's long
  and fast by the time it hits the barren half, and the whole loop lands
  around 15s instead of 25s.
- eaten cells flash the snake colour for one frame before going empty

The body is one `<path>` with an animated `stroke-dasharray` /
`stroke-dashoffset` rather than one element per segment — growth is the dash
getting longer, variable speed is a non-linear offset curve. ~71 KB.

```bash
GITHUB_TOKEN=$(gh auth token) python scripts/build_snake.py chrisudf
```

### Colours

Grid colours are GitHub's own dark-mode greens (`#0e4429` `#006d32` `#26a641`
`#39d353`). Empty cells are white at 5.5% alpha rather than a solid hex, so
the grid reads correctly on both `#0d1117` (dark) and `#22272e` (dark
dimmed) without needing to know which theme you're on. Snake is `#ff2a6d`,
picked up from the banner; change `THEMES` at the top of the script.

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
