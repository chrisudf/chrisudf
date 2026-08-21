#!/usr/bin/env python3
"""Build assets/header.svg.

Palette, typography and glitch treatment mirror chrisudf/cq-portfolio
(src/app/globals.css): Orbitron 900 for the name, JetBrains Mono for the HUD
type, cyan/magenta/yellow/neon-green on near-black.

Fonts are embedded as base64 woff2 so the banner renders identically on
GitHub — an SVG served through camo can't fetch anything external, but a
data: URI @font-face inside it works fine.

Usage:  python scripts/build_header.py [out.svg]
"""

import base64
import os
import re
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FONT_DIR = os.path.join(ROOT, "assets", "fonts")

GF_CSS = ("https://fonts.googleapis.com/css2"
          "?family=Orbitron:wght@900&family=JetBrains+Mono:wght@400;700&display=swap")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

# --- cq-portfolio palette -------------------------------------------------
BG      = "#07070d"
CYAN    = "#00f0ff"
MAGENTA = "#ff2a6d"
YELLOW  = "#fcee0a"
NEON    = "#19f6a4"
MUTED   = "#6b7a8d"

NAME    = "CHENG QIU"
EYEBROW = "SYSTEM ONLINE"
STATUS  = "BRISBANE // UTC+10"
ROLE_A  = "QUANT TOOLING"
ROLE_B  = "APPLIED AI"
ROLE_C  = "夜之城"
HUD     = "LAT -27.47 // LON 153.02"

W, H = 1000, 300

# --- vertical rhythm ------------------------------------------------------
# Everything stacks against HORIZON. The sun's cap has to clear RULE_Y or it
# eats the role line, so SUN_TOP is derived rather than eyeballed.
EYEBROW_Y = 44
NAME_Y    = 126        # baseline
CAP_H     = 43         # Orbitron cap height at font-size 62
SPLIT_Y   = NAME_Y - CAP_H + int(CAP_H * 0.45)   # magenta above, cyan below
ROLE_Y    = 158
RULE_Y    = 168
HORIZON   = 214
SUN_R     = 76
SUN_TOP   = 178        # 10px of air under the rule
SUN_CY    = SUN_TOP + SUN_R
MONO = "'JetBrains Mono','Cascadia Code',Consolas,monospace"
DISP = "'Orbitron','Segoe UI',Impact,sans-serif"
ADV = 0.6  # JetBrains Mono advance width, in em


def _fetch(url, **headers):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **headers})
    return urllib.request.urlopen(req, timeout=30).read()


def font_b64(family, cache_name):
    """Latin-basic woff2 subset, cached under assets/fonts/."""
    path = os.path.join(FONT_DIR, cache_name)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    css = _fetch(GF_CSS).decode()
    for block in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
        fam = re.search(r"font-family: '([^']+)'", block)
        rng = re.search(r"unicode-range: ([^;]+);", block)
        url = re.search(r"url\((https[^)]+)\)", block)
        if fam and rng and url and fam.group(1) == family and "U+0000-00FF" in rng.group(1):
            data = _fetch(url.group(1))
            os.makedirs(FONT_DIR, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return base64.b64encode(data).decode()
    raise SystemExit(f"no latin-basic woff2 found for {family}")


def build():
    orbitron = font_b64("Orbitron", "orbitron-900-latin.woff2")
    jetbrains = font_b64("JetBrains Mono", "jetbrains-mono-latin.woff2")

    p = []
    a = p.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-label="{NAME} — {ROLE_A} // {ROLE_B}">')

    # ---- embedded fonts + the one CSS animation SMIL can't express nicely
    a('<style>'
      f'@font-face{{font-family:"Orbitron";font-weight:900;font-style:normal;'
      f'src:url(data:font/woff2;base64,{orbitron}) format("woff2");}}'
      f'@font-face{{font-family:"JetBrains Mono";font-weight:100 800;font-style:normal;'
      f'src:url(data:font/woff2;base64,{jetbrains}) format("woff2");}}'
      '</style>')

    a('<defs>')
    a(f'<radialGradient id="glowA" cx="20%" cy="30%" r="60%">'
      f'<stop offset="0%" stop-color="{CYAN}" stop-opacity=".13"/>'
      f'<stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>')
    a(f'<radialGradient id="glowB" cx="85%" cy="72%" r="58%">'
      f'<stop offset="0%" stop-color="{MAGENTA}" stop-opacity=".16"/>'
      f'<stop offset="100%" stop-color="{MAGENTA}" stop-opacity="0"/></radialGradient>')
    a('<radialGradient id="vig" cx="50%" cy="45%" r="78%">'
      '<stop offset="55%" stop-color="#000000" stop-opacity="0"/>'
      '<stop offset="100%" stop-color="#000000" stop-opacity=".72"/></radialGradient>')
    a(f'<linearGradient id="sun" x1="0" y1="0" x2="0" y2="1">'
      f'<stop offset="0%" stop-color="{YELLOW}"/>'
      f'<stop offset="48%" stop-color="{MAGENTA}"/>'
      f'<stop offset="100%" stop-color="#7a1140"/></linearGradient>')
    a(f'<linearGradient id="rule" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0%" stop-color="{CYAN}" stop-opacity="0"/>'
      f'<stop offset="50%" stop-color="{CYAN}" stop-opacity=".85"/>'
      f'<stop offset="100%" stop-color="{CYAN}" stop-opacity="0"/></linearGradient>')
    a('<filter id="glow" x="-60%" y="-60%" width="220%" height="220%">'
      '<feGaussianBlur stdDeviation="5" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>'
      '</filter>')
    a('<filter id="soft" x="-60%" y="-60%" width="220%" height="220%">'
      '<feGaussianBlur stdDeviation="2" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    # 46px grid, matching .grid-bg
    a(f'<pattern id="flat" width="46" height="46" patternUnits="userSpaceOnUse">'
      f'<path d="M46 0 H0 V46" fill="none" stroke="{CYAN}" stroke-opacity=".07" stroke-width="1"/>'
      f'</pattern>')
    a(f'<clipPath id="frame"><rect width="{W}" height="{H}" rx="6"/></clipPath>')
    a(f'<clipPath id="floor"><rect y="{HORIZON}" width="{W}" height="{H - HORIZON}"/></clipPath>')
    a(f'<clipPath id="above"><rect width="{W}" height="{HORIZON}"/></clipPath>')
    # split-glitch clips — .glitch::before takes the top 45%, ::after the bottom
    a(f'<clipPath id="gtop"><rect x="0" y="{NAME_Y - CAP_H - 10}" width="{W}" '
      f'height="{SPLIT_Y - (NAME_Y - CAP_H - 10)}"/></clipPath>')
    a(f'<clipPath id="gbot"><rect x="0" y="{SPLIT_Y}" width="{W}" '
      f'height="{NAME_Y + 8 - SPLIT_Y}"/></clipPath>')
    a('</defs>')

    a('<g clip-path="url(#frame)">')
    a(f'<rect width="{W}" height="{H}" fill="{BG}"/>')
    a(f'<rect width="{W}" height="{H}" fill="url(#flat)"/>')
    a(f'<rect width="{W}" height="{H}" fill="url(#glowA)"/>')
    a(f'<rect width="{W}" height="{H}" fill="url(#glowB)"/>')

    # ---- starfield
    for cx, cy, r, dur in ((118, 40, 1.2, 3.1), (302, 26, 1.0, 4.3), (676, 44, 1.3, 2.6), \
                           (862, 30, 1.0, 3.7), (938, 64, 1.1, 5.2), (62, 82, 1.0, 4.9)):
        a(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#ffffff" opacity=".5">'
          f'<animate attributeName="opacity" values=".15;.85;.15" dur="{dur}s" '
          f'repeatCount="indefinite"/></circle>')

    # ---- sun, cut off at the horizon
    a('<g clip-path="url(#above)">')
    a(f'<circle cx="500" cy="{SUN_CY}" r="{SUN_R}" fill="url(#sun)" opacity=".9" '
      f'filter="url(#glow)"/>')
    a(f'<g fill="{BG}">')
    for off, th in ((8, 4), (19, 5), (32, 7)):
        a(f'<rect x="424" y="{SUN_TOP + off}" width="152" height="{th}"/>')
    a('</g></g>')

    # ---- perspective floor, scrolling toward the viewer (cf. @keyframes gridmove)
    a('<g clip-path="url(#floor)">')
    a(f'<g stroke="{CYAN}" stroke-opacity=".28" stroke-width="1">')
    for x in range(-1400, 2500, 190):
        a(f'<line x1="{x}" y1="{H}" x2="{500 + (x - 500) * 0.055:.0f}" y2="{HORIZON}"/>')
    a('</g>')
    a(f'<g stroke="{MAGENTA}" stroke-opacity=".5" stroke-width="1.1">')
    for i, off in enumerate((2, 11, 23, 39, 61, 91)):
        base = HORIZON + off
        travel = H + 24 - base
        a(f'<line x1="0" y1="{base}" x2="{W}" y2="{base}">'
          f'<animate attributeName="y1" values="{base};{base + travel}" dur="6s" '
          f'begin="{-1.0 * i:.2f}s" repeatCount="indefinite"/>'
          f'<animate attributeName="y2" values="{base};{base + travel}" dur="6s" '
          f'begin="{-1.0 * i:.2f}s" repeatCount="indefinite"/>'
          f'<animate attributeName="stroke-opacity" values=".12;.6" dur="6s" '
          f'begin="{-1.0 * i:.2f}s" repeatCount="indefinite"/></line>')
    a('</g>')
    a(f'<line x1="0" y1="{HORIZON}" x2="{W}" y2="{HORIZON}" stroke="{CYAN}" '
      f'stroke-opacity=".55" stroke-width="1.2"/>')
    a('</g>')

    # ---- eyebrow: a 40px yellow rule, then the label (.eyebrow::before)
    a(f'<rect x="46" y="{EYEBROW_Y - 5}" width="40" height="1" fill="{YELLOW}" '
      f'filter="url(#soft)"/>')
    a(f'<text x="98" y="{EYEBROW_Y}" font-family="{MONO}" font-size="12" fill="{YELLOW}" '
      f'letter-spacing="4">{EYEBROW}</text>')

    # ---- status pill (.status + .dot)
    pill_w = int(len(STATUS) * 11 * ADV + 34)
    pill_x = W - 46 - pill_w
    a(f'<rect x="{pill_x}" y="34" width="{pill_w}" height="22" rx="2" '
      f'fill="{NEON}" fill-opacity=".06" stroke="{NEON}" stroke-opacity=".4"/>')
    a(f'<circle cx="{pill_x + 14}" cy="45" r="4" fill="{NEON}" filter="url(#soft)">'
      '<animate attributeName="opacity" values="1;.22;1" dur="1.4s" repeatCount="indefinite"/>'
      '</circle>')
    a(f'<text x="{pill_x + 24}" y="49" font-family="{MONO}" font-size="11" fill="{NEON}" '
      f'letter-spacing="1">{STATUS}</text>')

    # ---- the name, with cq-portfolio's split glitch
    def name_text(fill, extra=""):
        return (f'<text x="500" y="{NAME_Y}" text-anchor="middle" font-family="{DISP}" '
                f'font-size="62" font-weight="900" letter-spacing="3" fill="{fill}"{extra}>'
                f'{NAME}</text>')

    a(f'<g filter="url(#soft)">{name_text("#ffffff")}</g>')
    a(f'<g clip-path="url(#gtop)" filter="url(#glow)" opacity=".92">{name_text(MAGENTA)}'
      '<animateTransform attributeName="transform" type="translate" '
      'values="0 0;0 0;-4 -2;3 1;0 0" keyTimes="0;.90;.93;.96;1" dur="3.2s" '
      'repeatCount="indefinite"/></g>')
    a(f'<g clip-path="url(#gbot)" filter="url(#glow)" opacity=".92">{name_text(CYAN)}'
      '<animateTransform attributeName="transform" type="translate" '
      'values="0 0;0 0;4 2;-3 -1;0 0" keyTimes="0;.88;.91;.97;1" dur="2.6s" '
      'repeatCount="indefinite"/></g>')

    # ---- role line — separators in magenta, like .role b
    a(f'<text x="500" y="{ROLE_Y}" text-anchor="middle" font-family="{MONO}" font-size="14" '
      f'font-weight="700" fill="{CYAN}" letter-spacing="6" filter="url(#soft)">'
      f'{ROLE_A}<tspan fill="{MAGENTA}"> // </tspan>{ROLE_B}'
      f'<tspan fill="{MAGENTA}"> // </tspan>'
      f'<tspan font-family="{MONO},\'Microsoft YaHei\',\'Noto Sans SC\',sans-serif">'
      f'{ROLE_C}</tspan></text>')

    a(f'<rect x="330" y="{RULE_Y}" width="340" height="1.5" fill="url(#rule)">'
      '<animate attributeName="opacity" values=".4;1;.4" dur="2.4s" repeatCount="indefinite"/>'
      '</rect>')

    # ---- side HUD (.side-hud), rotated against the right edge
    a(f'<text transform="translate({W - 22},{H // 2}) rotate(90)" text-anchor="middle" '
      f'font-family="{MONO}" font-size="10" fill="{CYAN}" fill-opacity=".4" '
      f'letter-spacing="3">{HUD}</text>')
    a(f'<text transform="translate(22,{H // 2}) rotate(-90)" text-anchor="middle" '
      f'font-family="{MONO}" font-size="10" fill="{MUTED}" letter-spacing="3">'
      f'GITHUB.COM/CHRISUDF</text>')

    # ---- corner brackets (.corner, cyan @ 50%)
    a(f'<g stroke="{CYAN}" stroke-width="2" fill="none" opacity=".5">'
      f'<path d="M16 42 V16 H42"/><path d="M{W-42} 16 H{W-16} V42"/>'
      f'<path d="M16 {H-42} V{H-16} H42"/><path d="M{W-42} {H-16} H{W-16} V{H-42}"/></g>')

    # ---- scanlines (4px period, flickering) + sweep
    a('<g fill="#000000" opacity=".18">')
    for y in range(0, H, 4):
        a(f'<rect y="{y + 2}" width="{W}" height="1"/>')
    a('<animate attributeName="opacity" values=".18;.16;.24;.18" dur="4s" '
      'repeatCount="indefinite"/></g>')
    a(f'<rect x="0" y="-80" width="{W}" height="80" fill="{CYAN}" opacity=".05">'
      f'<animate attributeName="y" values="-80;{H}" dur="6.5s" repeatCount="indefinite"/></rect>')

    a(f'<rect width="{W}" height="{H}" fill="url(#vig)"/>')
    a(f'<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="6" fill="none" '
      f'stroke="{CYAN}" stroke-opacity=".22" stroke-width="1.5"/>')
    a('</g></svg>')
    return "\n".join(p)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "assets", "header.svg")
    svg = build()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg + "\n")
    print(f"wrote {out} ({len(svg) / 1024:.1f} KB)")
