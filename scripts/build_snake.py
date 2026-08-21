#!/usr/bin/env python3
"""Render the contribution-grid snake.

Platane/snk only exposes palette/color_snake/color_dots — the snake there is a
fixed length moving at a fixed speed. This one grows a segment for every cell
it eats and accelerates as it fills up, so it does what snk can't.

The body is a single <path> with an animated stroke-dasharray/dashoffset
rather than one element per segment: growth is just the dash getting longer,
and variable speed is just a non-linear dashoffset curve. Keeps the file small
and the motion exact.

Usage:  GITHUB_TOKEN=... python scripts/build_snake.py chrisudf
"""

import json
import os
import sys
import urllib.request

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          firstDay
          contributionDays { weekday date contributionCount contributionLevel }
        }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# --- geometry (GitHub's own: 11px cell, 3px gutter, 2px radius) ------------
CELL, GAP = 11, 3
PITCH = CELL + GAP
LEFT, TOP, RIGHT, BOTTOM = 34, 22, 14, 12
ROWS = 7

# --- motion ---------------------------------------------------------------
STEP_SLOW_MS = 125      # ms per cell before it has eaten anything
STEP_FAST_MS = 26       # floor once it's fat and quick
BODY_MIN = 3.4          # body length, in cells
BODY_MAX = 17.0
TAIL_MS = 1100          # beat at the end before the loop restarts

THEMES = {
    # Empty cells are white/black at low alpha rather than a solid hex, so the
    # grid sits correctly on #0d1117 (dark) *and* #22272e (dark dimmed).
    "dark": {
        "empty": ("#ffffff", 0.055),
        "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"],
        "snake": "#ff2a6d",
        "label": "#8b949e",
    },
    "light": {
        "empty": ("#000000", 0.055),
        "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "snake": "#ff2a6d",
        "label": "#57606a",
    },
}


def fetch(login, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": f"{login}-snake"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]


def to_grid(weeks):
    """[(col, row)] -> level, plus the month label positions."""
    grid, months, seen = {}, [], set()
    for c, week in enumerate(weeks):
        for day in week["contributionDays"]:
            grid[(c, day["weekday"])] = LEVELS[day["contributionLevel"]]
        month = int(week["firstDay"][5:7])
        # label a month on the first column that is mostly inside it
        if month not in seen and int(week["firstDay"][8:10]) <= 7:
            seen.add(month)
            months.append((c, MONTHS[month - 1]))
    return grid, len(weeks), months


def route(cols):
    """Boustrophedon walk over every cell, entering right and exiting left.

    Right-to-left on purpose: contributions cluster in the recent months, so
    starting at the newest column means the snake finds food immediately and
    is already long and fast by the time it reaches the barren older half.
    Left-to-right spends the first 20s crawling through empty cells.

    Every hop is exactly one PITCH, which makes the dash arithmetic exact.
    """
    def cx(c):
        return LEFT + c * PITCH + CELL / 2

    def cy(r):
        return TOP + r * PITCH + CELL / 2

    nodes = [(cx(cols + 1), cy(0), None), (cx(cols), cy(0), None)]
    for i, c in enumerate(range(cols - 1, -1, -1)):
        rows = range(ROWS) if i % 2 == 0 else range(ROWS - 1, -1, -1)
        for r in rows:
            nodes.append((cx(c), cy(r), (c, r)))
    last_row = ROWS - 1 if (cols - 1) % 2 == 0 else 0
    nodes.append((cx(-1), cy(last_row), None))
    nodes.append((cx(-2), cy(last_row), None))
    return nodes


def timeline(nodes, grid):
    """Per-node arrival time and body length, both driven by the eat count."""
    total_food = sum(1 for lvl in grid.values() if lvl > 0) or 1

    times, bodies, eaten_at = [0.0], [BODY_MIN * PITCH], {}
    eaten, t = 0, 0.0
    for i in range(len(nodes) - 1):
        cell = nodes[i][2]
        if cell is not None and grid.get(cell, 0) > 0:
            eaten += 1
            eaten_at[cell] = t
        # accelerate over the first 80% of the food, then hold at the floor
        ramp = min(1.0, eaten / (total_food * 0.8))
        t += STEP_SLOW_MS - (STEP_SLOW_MS - STEP_FAST_MS) * ramp
        times.append(t)
        bodies.append((BODY_MIN + (BODY_MAX - BODY_MIN) * ramp) * PITCH)

    # the head can still be mid-grid on the last node; catch any final cell
    cell = nodes[-1][2]
    if cell is not None and grid.get(cell, 0) > 0:
        eaten_at[cell] = t
    return times, bodies, eaten_at, t + TAIL_MS


def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def build(login, token, theme_name):
    th = THEMES[theme_name]
    empty_hex, empty_op = th["empty"]

    weeks = fetch(login, token)
    grid, cols, months = to_grid(weeks)
    nodes = route(cols)
    times, bodies, eaten_at, total_ms = timeline(nodes, grid)

    W = LEFT + cols * PITCH - GAP + RIGHT
    H = TOP + ROWS * PITCH - GAP + BOTTOM
    dur = total_ms / 1000.0

    def kt(ms):  # ms -> keyTime
        return min(1.0, max(0.0, ms / total_ms))

    p = []
    a = p.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
      f'height="{H}" role="img" aria-label="{login}’s contribution grid, eaten by a snake">')
    a('<defs><filter id="snakeglow" x="-40%" y="-40%" width="180%" height="180%">'
      '<feGaussianBlur stdDeviation="3" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
      '</filter></defs>')

    # ---- labels
    a(f'<g font-family="-apple-system,\'Segoe UI\',Helvetica,Arial,sans-serif" '
      f'font-size="10" fill="{th["label"]}">')
    for c, name in months:
        a(f'<text x="{fmt(LEFT + c * PITCH)}" y="{TOP - 8}">{name}</text>')
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        a(f'<text x="{LEFT - 8}" y="{fmt(TOP + r * PITCH + CELL - 1.5)}" '
          f'text-anchor="end">{name}</text>')
    a('</g>')

    # ---- cells; the green ones flash the snake colour, then go empty
    a('<g>')
    for (c, r), lvl in sorted(grid.items()):
        x = fmt(LEFT + c * PITCH)
        y = fmt(TOP + r * PITCH)
        fill = empty_hex if lvl == 0 else th["levels"][lvl - 1]
        op = empty_op if lvl == 0 else 1
        a(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" '
          f'fill="{fill}" fill-opacity="{op}">')
        if lvl > 0 and (c, r) in eaten_at:
            t0 = kt(eaten_at[(c, r)])
            t1 = min(1.0, t0 + 0.008)
            a(f'<animate attributeName="fill" calcMode="discrete" '
              f'values="{fill};{th["snake"]};{empty_hex};{empty_hex}" '
              f'keyTimes="0;{fmt(t0)};{fmt(t1)};1" dur="{dur:.2f}s" repeatCount="indefinite"/>')
            a(f'<animate attributeName="fill-opacity" calcMode="discrete" '
              f'values="1;1;{empty_op};{empty_op}" '
              f'keyTimes="0;{fmt(t0)};{fmt(t1)};1" dur="{dur:.2f}s" repeatCount="indefinite"/>')
        a('</rect>')
    a('</g>')

    # ---- the snake: one polyline, dash animated
    d = "M" + " L".join(f"{fmt(x)} {fmt(y)}" for x, y, _ in nodes)
    path_len = (len(nodes) - 1) * PITCH

    offsets, dashes, keys = [], [], []
    for i in range(len(nodes)):
        progress = i * PITCH
        offsets.append(fmt(bodies[i] - progress))
        dashes.append(f"{fmt(bodies[i])} {fmt(path_len + BODY_MAX * PITCH)}")
        keys.append(fmt(kt(times[i])))
    # hold through the tail beat so the loop doesn't snap
    offsets.append(offsets[-1]); dashes.append(dashes[-1]); keys.append("1")

    a(f'<path id="route" d="{d}" fill="none" stroke="{th["snake"]}" stroke-width="{CELL}" '
      f'stroke-linecap="round" stroke-linejoin="round" filter="url(#snakeglow)" '
      f'stroke-dasharray="{dashes[0]}" stroke-dashoffset="{offsets[0]}">')
    a(f'<animate attributeName="stroke-dashoffset" values="{";".join(offsets)}" '
      f'keyTimes="{";".join(keys)}" dur="{dur:.2f}s" repeatCount="indefinite"/>')
    a(f'<animate attributeName="stroke-dasharray" values="{";".join(dashes)}" '
      f'keyTimes="{";".join(keys)}" dur="{dur:.2f}s" repeatCount="indefinite"/>')
    a('</path>')

    # ---- eyes, riding the same path at the same speed
    kp = [fmt(min(1.0, i * PITCH / path_len)) for i in range(len(nodes))] + ["1"]
    a('<g fill="#ffffff" opacity=".92">'
      f'<circle cx="1.2" cy="-2.6" r="1.25"/><circle cx="1.2" cy="2.6" r="1.25"/>'
      f'<animateMotion dur="{dur:.2f}s" repeatCount="indefinite" rotate="auto" '
      f'keyPoints="{";".join(kp)}" keyTimes="{";".join(keys)}" calcMode="linear">'
      f'<mpath href="#route"/></animateMotion></g>')

    a('</svg>')
    return "\n".join(p)


def main():
    login = sys.argv[1] if len(sys.argv) > 1 else "chrisudf"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (or GH_TOKEN)")

    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    for theme, name in (("dark", "snake-dark.svg"), ("light", "snake.svg")):
        svg = build(login, token, theme)
        out = os.path.join(root, "assets", name)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg + "\n")
        print(f"wrote assets/{name} ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
