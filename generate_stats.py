#!/usr/bin/env python3
"""Self-hosted stats card — metrics and language distribution as SVG.

Replaces github-readme-stats and github-profile-trophy, both of which are public
Vercel deployments that 503 under load or return 402 when their quota runs out.
A profile should not break because someone else's free tier did.

Language shares come from real byte counts per repository, not the single
`language` field, which only reports the largest language in a repo.

Usage:
    GH_USER=HariKarthick22 GITHUB_TOKEN=$(gh auth token) python generate_stats.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from lib.inferno import inferno
from lib.textpath import FONTS, advance_width, text_to_path

OWNER = os.environ.get("GH_USER", "HariKarthick22")
W, H = 1180, 330
PAD = 44
BAR_Y = 214.0
BAR_H = 16.0
MAX_LANGS = 7

THEMES = {
    "dark": {"page": "#0B0A09", "border": "#2A241E", "text": "#F5EFE7",
             "muted": "#9C9186", "accent": "#F98E08", "track": "#221D18"},
    "light": {"page": "#FAF7F2", "border": "#E6DFD4", "text": "#16130F",
              "muted": "#6E655C", "accent": "#C2410C", "track": "#EFE9DF"},
}


def _api(path: str, token: str | None) -> dict | list:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "agent-surface-profile"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"https://api.github.com/{path}", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gather(owner: str, token: str | None) -> dict:
    user = _api(f"users/{owner}", token)
    repos = _api(f"users/{owner}/repos?per_page=100", token)
    public = [r for r in repos if not r.get("private")]

    totals: dict[str, int] = {}
    for r in public:
        if r.get("fork"):
            continue
        try:
            for lang, n in _api(f"repos/{owner}/{r['name']}/languages", token).items():
                totals[lang] = totals.get(lang, 0) + n
        except urllib.error.HTTPError:
            continue          # a single unreadable repo must not kill the card

    commits = None
    try:
        q = urllib.parse.quote(f"author:{owner}")
        commits = _api(f"search/commits?q={q}&per_page=1", token).get("total_count")
    except Exception:
        pass                  # search API is rate-limited harshly; degrade quietly

    return {
        "repos": len([r for r in public if not r.get("fork")]),
        "stars": sum(r.get("stargazers_count", 0) for r in public),
        "followers": user.get("followers", 0),
        "commits": commits,
        "languages": sorted(totals.items(), key=lambda kv: -kv[1]),
    }


def _mono(text: str, x: float, y: float, size: float, fill: str,
          anchor: str = "start") -> str:
    if not text:
        return ""
    width = advance_width(text, FONTS["mono"], size)
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    a = "" if anchor == "start" else f' text-anchor="{anchor}"'
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" fill="{fill}"'
            f' textLength="{width:.1f}" lengthAdjust="spacing"{a}'
            f' font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'
            f' xml:space="preserve">{esc}</text>')


def build_svg(stats: dict, theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; expected 'dark' or 'light'")
    t = THEMES[theme]

    parts = [
        f'<rect width="{W}" height="{H}" rx="14" fill="{t["page"]}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="13.5"'
        f' fill="none" stroke="{t["border"]}" stroke-width="1"/>',
        _mono("TRAINING METRICS", PAD, 42, 11.0, t["accent"]),
        _mono("self-hosted · no external service", W - PAD, 42, 9.5, t["muted"],
              anchor="end"),
        f'<line x1="{PAD}" y1="58" x2="{W - PAD}" y2="58"'
        f' stroke="{t["border"]}" stroke-width="1"/>',
    ]

    cells = [
        ("REPOSITORIES", f'{stats["repos"]}'),
        ("TOTAL STARS", f'{stats["stars"]}'),
        ("FOLLOWERS", f'{stats["followers"]}'),
        ("COMMITS", f'{stats["commits"]:,}' if stats["commits"] else "—"),
        ("LANGUAGES", f'{len(stats["languages"])}'),
    ]
    step = (W - PAD * 2) / len(cells)
    for i, (label, value) in enumerate(cells):
        cx = PAD + step * i
        parts.append(_mono(label, cx, 96, 9.0, t["muted"]))
        parts.append(
            f'<path d="{text_to_path(value, FONTS["display"], 40, cx, 142)}"'
            f' fill="{t["text"]}"/>')

    parts.append(_mono("LANGUAGE DISTRIBUTION", PAD, 188, 9.5, t["muted"]))

    langs = stats["languages"][:MAX_LANGS]
    total = sum(n for _, n in stats["languages"]) or 1
    bar_w = W - PAD * 2

    parts.append(f'<rect x="{PAD}" y="{BAR_Y}" width="{bar_w}" height="{BAR_H}"'
                 f' rx="{BAR_H / 2}" fill="{t["track"]}"/>')

    x = float(PAD)
    parts.append(f'<clipPath id="barclip"><rect x="{PAD}" y="{BAR_Y}"'
                 f' width="{bar_w}" height="{BAR_H}" rx="{BAR_H / 2}"/></clipPath>')
    parts.append('<g clip-path="url(#barclip)">')
    for i, (name, n) in enumerate(langs):
        seg = bar_w * (n / total)
        colour = inferno(0.22 + 0.68 * (i / max(1, len(langs) - 1)), theme)
        parts.append(f'<rect x="{x:.1f}" y="{BAR_Y}" width="{seg:.1f}"'
                     f' height="{BAR_H}" fill="{colour}">'
                     f'<animate attributeName="width" from="0" to="{seg:.1f}"'
                     f' begin="{0.06 * i:.2f}s" dur="0.6s"'
                     f' calcMode="spline" keySplines="0.16 1 0.3 1"'
                     f' keyTimes="0;1" fill="freeze"/></rect>')
        x += seg
    parts.append("</g>")

    ly = 268.0
    lx = float(PAD)
    for i, (name, n) in enumerate(langs):
        pct = 100.0 * n / total
        colour = inferno(0.22 + 0.68 * (i / max(1, len(langs) - 1)), theme)
        label = f"{name} {pct:.1f}%"
        parts.append(f'<circle cx="{lx + 4:.1f}" cy="{ly - 4:.1f}" r="4"'
                     f' fill="{colour}"/>')
        parts.append(_mono(label, lx + 15, ly, 10.0, t["text"]))
        lx += advance_width(label, FONTS["mono"], 10.0) + 40

    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"'
            f' width="{W}" height="{H}" role="img"'
            f' aria-label="GitHub statistics and language distribution">'
            + "".join(parts) + "</svg>")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    try:
        stats = gather(OWNER, token)
    except urllib.error.HTTPError as e:
        print(f"GitHub API {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"cannot reach GitHub: {e.reason}", file=sys.stderr)
        return 1

    for theme in ("dark", "light"):
        with open(f"stats-{theme}.svg", "w") as f:
            f.write(build_svg(stats, theme))

    top = ", ".join(f"{n} {100.0 * v / max(1, sum(x for _, x in stats['languages'])):.0f}%"
                    for n, v in stats["languages"][:4])
    print(f"stats-*.svg  {stats['repos']} repos · {stats['stars']} stars · {top}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
