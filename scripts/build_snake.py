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
STEP_MS = 105           # ms per cell, constant
BODY_MIN = 3.4          # body length, in cells
BODY_MAX = 13.0         # kept modest: a longer body crosses itself on the
                        # foraging path often enough to look wrong
LOOKAHEAD = 3           # pick among the N nearest cells, not always the closest

# end of loop: hold on the last bite, fade the snake out, blank beat, restart
HOLD_MS, FADE_MS, REST_MS = 340, 420, 260

THEMES = {
    # Empty cells are white/black at low alpha rather than a solid hex, so the
    # grid sits correctly on #0d1117 (dark) *and* #22272e (dark dimmed).
    "dark": {
        "empty": ("#ffffff", 0.055),
        "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"],
        "snake": "#00f0ff",
        "label": "#8b949e",
    },
    "light": {
        "empty": ("#000000", 0.055),
        "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "snake": "#0092b8",
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


DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def body_span(eaten, total_food):
    """Body length in cells after `eaten` bites."""
    return BODY_MIN + (BODY_MAX - BODY_MIN) * min(1.0, eaten / total_food)


def open_space(start, seen, idx, body, walkable, limit):
    """How many cells are reachable from `start` without touching the body.

    Stops counting at `limit` — we only need to know whether there is room to
    fit, not the exact size of the pocket.
    """
    stack, vis, n = [start], {start}, 0
    while stack and n < limit:
        x, y = stack.pop()
        n += 1
        for s in DIRS:
            nxt = (x + s[0], y + s[1])
            if nxt in vis or nxt not in walkable:
                continue
            if idx + 1 - seen.get(nxt, -1 << 30) <= body:
                continue
            vis.add(nxt)
            stack.append(nxt)
    return n


def choose_step(cur, target, heading, seen, idx, body, walkable, rng):
    """One hop toward `target` that the body isn't already lying on.

    A cell last entered at step `i` is still under the body at step `j` when
    `j - i <= body`, so self-collision is an exact test, not a heuristic —
    which is what banning reversals alone failed to catch.
    """
    x, y = cur
    tx, ty = target
    opts = []
    for s in DIRS:
        if heading and s == (-heading[0], -heading[1]):
            continue                                    # no 180° turns
        nxt = (x + s[0], y + s[1])
        if nxt not in walkable:
            continue
        age = idx + 1 - seen.get(nxt, -1 << 30)
        opts.append((age > body, abs(tx - nxt[0]) + abs(ty - nxt[1]), age, s))

    if not opts:                                        # boxed in; back out
        return (-heading[0], -heading[1]) if heading else (1, 0)

    # clear cells first, then whichever is closest to vacating
    free = [o for o in opts if o[0]]

    # of those, drop any that lead into a pocket too small to hold the body —
    # entering one means the only way out later is through itself
    if len(free) > 1:
        room = int(body) + 3
        roomy = [o for o in free
                 if open_space((x + o[3][0], y + o[3][1]), seen, idx, body,
                               walkable, room) >= room]
        free = roomy or free

    pool = free or sorted(opts, key=lambda o: -o[2])[:1]

    best = min(o[1] for o in pool)
    # ties are the two axes that both close the gap — picking between them at
    # random is what gives the staircase its wander
    return rng.choice([o[3] for o in pool if o[1] == best])


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
        total = len(food)
        # only cells that actually have a square, plus the off-grid entry
        # column. The final week is a partial one — the days after today have
        # no square drawn, and the snake slithering over that blank corner
        # looks like a rendering fault.
        walkable = set(grid) | {(-1, r) for r in range(ROWS)}
        start = min(food, key=lambda cell: (cell[0], cell[1]))
        cur, heading = (-1, start[1]), (1, 0)
        cells, remaining, seen = [cur], set(food), {cur: 0}
        eaten = 0

        deferred, slack, cap = [], 1, 24 * ROWS * cols
        while remaining and len(cells) < cap:
            near = sorted(remaining,
                          key=lambda cell: (abs(cell[0] - cur[0]) + abs(cell[1] - cur[1]),
                                            cell[0], cell[1]))[:LOOKAHEAD]
            target = near[0] if len(near) == 1 else rng.choices(
                near, weights=[0.62, 0.24, 0.14][:len(near)])[0]

            # detours around its own body cost extra hops
            budget = slack * (4 * (abs(target[0] - cur[0])
                                   + abs(target[1] - cur[1])) + 24)
            while cur != target and budget:
                step = choose_step(cur, target, heading, seen, len(cells) - 1,
                                   body_span(eaten, total), walkable, rng)
                cur = (cur[0] + step[0], cur[1] + step[1])
                heading = step
                cells.append(cur)
                seen[cur] = len(cells) - 1
                if cur in remaining:        # anything crossed en route is eaten
                    remaining.discard(cur)
                    eaten += 1
                budget -= 1

            if cur != target:
                # walled off by its own body. Park it and move on — leaving it
                # in `remaining` means the next pass picks the same unreachable
                # cell and loops forever.
                remaining.discard(target)
                deferred.append(target)

            if not remaining and deferred and slack == 1:
                remaining, deferred, slack = set(deferred), [], 4
        # stops on the last bite — walking out to the wall afterwards is dead
        # time, so the loop fades and restarts from there instead

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
        bodies.append(body_span(eaten, total_food) * PITCH)

    return times, bodies, eaten_at, times[-1] + HOLD_MS + FADE_MS + REST_MS


def fmt(x):
    return f"{x:.2f}".rstrip("0").rstrip(".")


def build(login, token, theme_name, weeks=None, snake=None):
    th = dict(THEMES[theme_name])
    if snake:
        th["snake"] = snake
    empty_hex, empty_op = th["empty"]

    weeks = weeks or fetch(login, token)
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

    # the loop ends on the last bite, so the snake dissolves rather than
    # snapping away mid-grid when the animation restarts
    fade_a, fade_b = kt(times[-1] + HOLD_MS), kt(times[-1] + HOLD_MS + FADE_MS)

    def fade(peak):
        return (f'<animate attributeName="opacity" values="{peak};{peak};0;0" '
                f'keyTimes="0;{fmt(fade_a)};{fmt(fade_b)};1" dur="{dur:.2f}s" '
                f'repeatCount="indefinite"/>')

    a(f'<path id="route" d="{d}" fill="none" stroke="{th["snake"]}" stroke-width="{CELL}" '
      f'stroke-linecap="round" stroke-linejoin="round" filter="url(#snakeglow)" '
      f'stroke-dasharray="{dashes[0]}" stroke-dashoffset="{offsets[0]}">')
    a(f'<animate attributeName="stroke-dashoffset" values="{";".join(offsets)}" '
      f'keyTimes="{";".join(keys)}" dur="{dur:.2f}s" repeatCount="indefinite"/>')
    a(f'<animate attributeName="stroke-dasharray" values="{";".join(dashes)}" '
      f'keyTimes="{";".join(keys)}" dur="{dur:.2f}s" repeatCount="indefinite"/>')
    a(fade(1))
    a('</path>')

    # ---- eyes, riding the same path. Constant speed and equal-length hops
    # mean distance is linear in time, so two keyPoints cover the whole walk.
    a('<g fill="#ffffff">'
      f'<circle cx="1.2" cy="-2.6" r="1.25"/><circle cx="1.2" cy="2.6" r="1.25"/>'
      f'{fade(0.92)}'
      f'<animateMotion dur="{dur:.2f}s" repeatCount="indefinite" rotate="auto" '
      f'keyPoints="0;1;1" keyTimes="0;{fmt(kt(times[-1]))};1" calcMode="linear">'
      f'<mpath href="#route"/></animateMotion></g>')

    a('</svg>')
    return "\n".join(p)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = dict(a.lstrip("-").split("=", 1) for a in sys.argv[1:] if a.startswith("--"))
    login = args[0] if args else "chrisudf"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (or GH_TOKEN)")

    weeks = fetch(login, token)
    os.makedirs(os.path.join(root, "assets"), exist_ok=True)
    for theme, name in (("dark", "snake-dark.svg"), ("light", "snake.svg")):
        svg = build(login, token, theme, weeks=weeks, snake=flags.get("snake"))
        out = os.path.join(root, "assets", name)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg + "\n")
        print(f"wrote assets/{name} ({len(svg) / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
