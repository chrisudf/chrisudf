#!/usr/bin/env python3
"""Render the contribution-grid snake.

Platane/snk only exposes palette/color_snake/color_dots — the snake there is a
fixed length. This one grows a segment for every cell it eats.

It also doesn't sweep the grid column by column. It forages: repeatedly heads
for a nearby green cell, wandering there on a randomised staircase instead of
a straight line. Reads as something alive rather than a print head.

The body is a single <path> with an animated stroke-dasharray/dashoffset
rather than one element per segment: growth is just the dash getting longer.
Keeps the file small and the motion exact.

Usage:  GITHUB_TOKEN=... python scripts/build_snake.py chrisudf
"""

import json
import os
import random
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
STEP_MS = 74            # ms per cell, constant
BODY_MIN = 3.4          # body length, in cells
BODY_MAX = 13.0         # kept modest: a longer body crosses itself on the
                        # foraging path often enough to look wrong
TAIL_MS = 900           # beat at the end before the loop restarts
LOOKAHEAD = 3           # pick among the N nearest cells, not always the closest

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


def stagger(a, b, rng, incoming=None):
    """Cells from a (exclusive) to b (inclusive) on a randomised staircase.

    An L-shaped move reads as a machine. Interleaving the two axes — weighted
    by how far is left on each, so it still arrives directly — reads as
    something slithering.

    `incoming` is the direction of the hop that landed on `a`. The first step
    is never allowed to invert it: a snake that reverses walks head-first into
    its own neck, which is both impossible and the ugliest artefact on the
    grid. If the target is straight behind, it sidesteps a row first.
    """
    (x, y), (tx, ty) = a, b
    dx = (tx > x) - (tx < x)
    dy = (ty > y) - (ty < y)
    out = []
    first = True
    while (x, y) != (tx, ty):
        rx, ry = abs(tx - x), abs(ty - y)
        take_x = rng.random() < rx / (rx + ry) if (rx and ry) else bool(rx)

        if first and incoming:
            step = (dx, 0) if take_x else (0, dy)
            if step == (-incoming[0], -incoming[1]):
                if take_x and ry:
                    take_x = False          # go the other way instead
                elif not take_x and rx:
                    take_x = True
                else:                       # nothing but backwards — dodge
                    away = [r for r in (y - 1, y + 1) if 0 <= r < ROWS]
                    y = rng.choice(away) if away else y
                    out.append((x, y))
                    first = False
                    continue
        first = False

        if take_x:
            x += dx
        else:
            y += dy
        out.append((x, y))
    return out


def route(cols, grid):
    """Forage: hop between green cells, eating whatever it crosses on the way.

    Nowhere near an optimal tour, and that's the point — a greedy walk with a
    little jitter in the target choice wanders the way a snake should.
    """
    food = {cell for cell, lvl in grid.items() if lvl > 0}
    # seeded off the data, so the same grid always renders the same path and
    # the daily commit is a no-op when nothing changed
    rng = random.Random(len(food) * 7919 + sum(c * 7 + r for c, r in sorted(food)))

    if not food:
        cells = [(c, ROWS // 2) for c in range(cols)]
    else:
        start = min(food, key=lambda cell: (cell[0], cell[1]))
        cur, heading = (-1, start[1]), (1, 0)
        cells, remaining = [cur], set(food)
        while remaining:
            near = sorted(remaining,
                          key=lambda cell: (abs(cell[0] - cur[0]) + abs(cell[1] - cur[1]),
                                            cell[0], cell[1]))[:LOOKAHEAD]
            target = near[0] if len(near) == 1 else rng.choices(
                near, weights=[0.62, 0.24, 0.14][:len(near)])[0]
            leg = stagger(cur, target, rng, heading)
            for cell in leg:
                cells.append(cell)
                remaining.discard(cell)     # anything crossed en route is eaten
            if len(leg) >= 2:
                heading = (leg[-1][0] - leg[-2][0], leg[-1][1] - leg[-2][1])
            elif leg:
                heading = (leg[0][0] - cur[0], leg[0][1] - cur[1])
            cur = target
        # leave by whichever edge is closer
        exit_col = cols + 1 if cur[0] * 2 >= cols else -2
        cells += stagger(cur, (exit_col, cur[1]), rng, heading)

    def cx(c):
        return LEFT + c * PITCH + CELL / 2

    def cy(r):
        return TOP + r * PITCH + CELL / 2

    return [(cx(c), cy(r), (c, r)) for c, r in cells]


def timeline(nodes, grid):
    """Per-node arrival time and body length. Speed is constant; only the
    body responds to eating."""
    total_food = sum(1 for lvl in grid.values() if lvl > 0) or 1

    times, bodies, eaten_at = [], [], {}
    eaten = 0
    for i, (_, _, cell) in enumerate(nodes):
        t = i * STEP_MS
        if grid.get(cell, 0) > 0 and cell not in eaten_at:
            eaten += 1
            eaten_at[cell] = t
        times.append(t)
        grown = min(1.0, eaten / total_food)
        bodies.append((BODY_MIN + (BODY_MAX - BODY_MIN) * grown) * PITCH)

    return times, bodies, eaten_at, times[-1] + TAIL_MS


def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def build(login, token, theme_name):
    th = THEMES[theme_name]
    empty_hex, empty_op = th["empty"]

    weeks = fetch(login, token)
    grid, cols, months = to_grid(weeks)
    nodes = route(cols, grid)
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

    # ---- eyes, riding the same path. Constant speed and equal-length hops
    # mean distance is linear in time, so two keyPoints cover the whole walk.
    a('<g fill="#ffffff" opacity=".92">'
      f'<circle cx="1.2" cy="-2.6" r="1.25"/><circle cx="1.2" cy="2.6" r="1.25"/>'
      f'<animateMotion dur="{dur:.2f}s" repeatCount="indefinite" rotate="auto" '
      f'keyPoints="0;1;1" keyTimes="0;{fmt(kt(times[-1]))};1" calcMode="linear">'
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
