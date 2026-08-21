#!/usr/bin/env python3
"""Render a self-hosted neon stats card from the GitHub GraphQL API.

Third-party README widgets (github-readme-stats, streak-stats, profile-trophy)
go down constantly. This one lives in the repo, so it can't 503.

Usage:  GITHUB_TOKEN=... python scripts/gen_stats.py chrisudf assets/stats.svg
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = "https://api.github.com/graphql"

QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    createdAt
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions
      restrictedContributionsCount
      totalPullRequestContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar { totalContributions }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false,
                 orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Neon ramp, brightest first — overrides GitHub's language colors so the card
# reads as one palette instead of a fruit salad.
NEON = ["#00f0ff", "#ff00a0", "#f7ff00", "#7b2fff", "#00ff9d", "#ff6b1a"]

BG, DIM, TEXT = "#0d1117", "#7d8590", "#e6edf3"
CYAN, MAGENTA, YELLOW = "#00f0ff", "#ff00a0", "#f7ff00"


def fetch(login, token):
    req = urllib.request.Request(
        API,
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-readme-stats",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def crunch(user):
    c = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]

    sizes = {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            sizes[edge["node"]["name"]] = sizes.get(edge["node"]["name"], 0) + edge["size"]
    total_bytes = sum(sizes.values()) or 1
    top = sorted(sizes.items(), key=lambda kv: -kv[1])[:6]

    return {
        "login": user["login"],
        "since": user["createdAt"][:4],
        "commits": c["totalCommitContributions"] + c["restrictedContributionsCount"],
        "contributions": c["contributionCalendar"]["totalContributions"],
        "prs": c["totalPullRequestContributions"],
        "reviews": c["totalPullRequestReviewContributions"],
        "issues": c["totalIssueContributions"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "repos": user["repositories"]["totalCount"],
        "followers": user["followers"]["totalCount"],
        "langs": [(name, 100 * size / total_bytes) for name, size in top],
    }


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(d):
    W, H = 900, 300
    mono = "'Courier New',ui-monospace,monospace"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")

    # Last slot goes to whichever number is actually worth showing — a hard 0
    # on a profile card reads worse than no row at all.
    if d["stars"]:
        last = ("STARS EARNED", d["stars"], YELLOW)
    elif d["reviews"]:
        last = ("CODE REVIEWS", d["reviews"], YELLOW)
    else:
        last = ("UPTIME", f'{datetime.now(timezone.utc).year - int(d["since"])} YRS', YELLOW)

    rows = [
        ("COMMITS  [12M]", d["commits"], CYAN),
        ("CONTRIBUTIONS", d["contributions"], CYAN),
        ("PULL REQUESTS", d["prs"], MAGENTA),
        ("PUBLIC REPOS", d["repos"], MAGENTA),
        ("FOLLOWERS", d["followers"], YELLOW),
        last,
    ]

    p = []
    a = p.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-label="GitHub stats for {esc(d["login"])}">')
    a('<defs>'
      '<filter id="g" x="-50%" y="-50%" width="200%" height="200%">'
      '<feGaussianBlur stdDeviation="2.4" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
      f'<clipPath id="card"><rect x="0" y="0" width="{W}" height="{H}" rx="10"/></clipPath>'
      '</defs>')
    a(f'<g clip-path="url(#card)"><rect width="{W}" height="{H}" fill="{BG}"/>')

    # header
    a(f'<text x="28" y="38" font-family="{mono}" font-size="17" font-weight="bold" fill="{CYAN}" '
      f'filter="url(#g)" letter-spacing="2">&#9670; SYSTEM READOUT // @{esc(d["login"])}'
      f'<tspan fill="{YELLOW}"> &#9608;'
      '<animate attributeName="opacity" values="1;1;0;0" dur="1.1s" repeatCount="indefinite"/>'
      '</tspan></text>')
    a(f'<text x="{W - 28}" y="38" text-anchor="end" font-family="{mono}" font-size="12" fill="{DIM}" '
      f'letter-spacing="1">SYNC {now} &#183; ONLINE SINCE {d["since"]}</text>')
    a(f'<rect x="28" y="52" width="{W - 56}" height="1" fill="{MAGENTA}" opacity=".55"/>')

    # left column — stat readouts
    for i, (label, value, color) in enumerate(rows):
        y = 92 + i * 34
        a(f'<g opacity="0"><animate attributeName="opacity" values="0;1" dur=".35s" '
          f'begin="{0.09 * i:.2f}s" fill="freeze"/>')
        a(f'<text x="30" y="{y}" font-family="{mono}" font-size="13" fill="{DIM}" '
          f'letter-spacing="1.5">{label}</text>')
        a(f'<text x="410" y="{y}" text-anchor="end" font-family="{mono}" font-size="20" '
          f'font-weight="bold" fill="{color}" filter="url(#g)">{esc(value)}</text>')
        a(f'<rect x="30" y="{y + 8}" width="380" height="1" fill="{color}" opacity=".16"/>')
        a('</g>')

    # divider
    a(f'<rect x="446" y="66" width="1" height="{H - 108}" fill="{CYAN}" opacity=".3"/>')

    # right column — language distribution
    a(f'<text x="474" y="88" font-family="{mono}" font-size="13" fill="{DIM}" '
      f'letter-spacing="1.5">LANGUAGE DISTRIBUTION</text>')
    bar_x, bar_max = 474, W - 474 - 28
    for i, (name, pct) in enumerate(d["langs"]):
        y = 118 + i * 29
        color = NEON[i % len(NEON)]
        w = max(3.0, bar_max * pct / 100.0)
        a(f'<text x="{bar_x}" y="{y}" font-family="{mono}" font-size="13" fill="{TEXT}">{esc(name)}</text>')
        a(f'<text x="{W - 28}" y="{y}" text-anchor="end" font-family="{mono}" font-size="12" '
          f'fill="{color}">{pct:.1f}%</text>')
        a(f'<rect x="{bar_x}" y="{y + 6}" width="{bar_max}" height="6" rx="3" fill="{color}" opacity=".12"/>')
        a(f'<rect x="{bar_x}" y="{y + 6}" width="0" height="6" rx="3" fill="{color}" filter="url(#g)">'
          f'<animate attributeName="width" values="0;{w:.1f}" dur="1.1s" '
          f'begin="{0.12 * i:.2f}s" fill="freeze" calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/>'
          '</rect>')

    # scanlines + sweep + frame
    a(f'<g fill="#000000" opacity=".13">')
    for y in range(0, H, 4):
        a(f'<rect y="{y}" width="{W}" height="1.5"/>')
    a('</g>')
    a(f'<rect x="0" y="-70" width="{W}" height="70" fill="{CYAN}" opacity=".05">'
      f'<animate attributeName="y" values="-70;{H}" dur="6s" repeatCount="indefinite"/></rect>')
    a(f'<g stroke="{YELLOW}" stroke-width="2" fill="none" opacity=".9">'
      f'<path d="M12 40 V12 H40"/><path d="M{W-40} 12 H{W-12} V40"/>'
      f'<path d="M12 {H-40} V{H-12} H40"/><path d="M{W-40} {H-12} H{W-12} V{H-40}"/></g>')
    a(f'<rect x="1" y="1" width="{W-2}" height="{H-2}" rx="10" fill="none" stroke="{MAGENTA}" '
      'stroke-width="2" opacity=".6">'
      '<animate attributeName="opacity" values=".3;.75;.3" dur="3.2s" repeatCount="indefinite"/></rect>')
    a('</g></svg>')
    return "\n".join(p)


def main():
    login = sys.argv[1] if len(sys.argv) > 1 else "chrisudf"
    out = sys.argv[2] if len(sys.argv) > 2 else "assets/stats.svg"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN (or GH_TOKEN)")

    data = crunch(fetch(login, token))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(data) + "\n")
    print(f"wrote {out}: {data['commits']} commits, {data['stars']} stars, "
          f"{len(data['langs'])} languages")


if __name__ == "__main__":
    main()
