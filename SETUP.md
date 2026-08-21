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
`color_dots`, and its snake is a fixed length. `scripts/build_snake.py`
replaces it:

- **grows** from 3.4 to 13 cells as it eats, at a **constant** 74 ms per cell
- **restarts on the last bite.** It doesn't walk out to the wall afterwards —
  that was three dead seconds per loop. It holds, fades out over 0.4 s, and
  the next round begins. ~12.5 s total.
- **forages** instead of sweeping. It picks a nearby green cell, walks there
  on a randomised staircase rather than an L, and eats anything it crosses on
  the way. About 42% of hops change direction, so it wanders — but the target
  choice is greedy enough that it still drifts left to right across the year.
- never reverses into itself. A 180° turn puts the head through its own neck,
  which is the ugliest artefact on a grid this small; when the next target is
  straight behind, it sidesteps a row first. That cut visible self-overlaps
  from 10 per loop to 2.
- eaten cells flash the snake colour for one frame before going empty

The body is one `<path>` with an animated `stroke-dasharray` /
`stroke-dashoffset` rather than one element per segment — growth is just the
dash getting longer. ~61 KB, ~14 s per loop.

```bash
GITHUB_TOKEN=$(gh auth token) python scripts/build_snake.py chrisudf
```

### Colours

Grid colours are GitHub's own dark-mode greens (`#0e4429` `#006d32` `#26a641`
`#39d353`). Empty cells are white at 5.5% alpha rather than a solid hex, so
the grid reads correctly on both `#0d1117` (dark) and `#22272e` (dark
dimmed) without needing to know which theme you're on.

Snake is `#00f0ff` on dark (`#0092b8` on light, since full cyan is invisible
on white) — the banner's primary accent, so the two graphics read as one
system. To try another, either edit `THEMES` or pass a flag:

```bash
python scripts/build_snake.py chrisudf --snake='#ff2a6d'
```

Candidates worth knowing: `#ff2a6d` magenta separates from green best (it's
nearly complementary), `#a371f7` is GitHub's own purple and the calmest
option, `#fcee0a` is the loudest. Avoid anything in the green family — it
reads as food.

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
