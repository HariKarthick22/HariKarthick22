#!/usr/bin/env python3
"""Agent roster — repos rendered as a Keras model.summary() table.

Projects are framed as layers in an architecture: each carries an agent role, an
output shape derived from its task type, and its stars as the parameter count.
Role and shape come from repo topics, so a newly-topiced repo lands in the right
place without touching this file.

Usage:
    GH_USER=HariKarthick22 GITHUB_TOKEN=$(gh auth token) python generate_repos.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

from lib.inferno import inferno
from lib.textpath import FONTS, advance_width

OWNER = os.environ.get("GH_USER", "HariKarthick22")
MODEL_NAME = "karthick_ar"
W = 1180
PAD = 44
# Must exceed the public repo count, or the lowest-ranked project is silently
# dropped from a section whose prose promises every repo appears.
MAX_AGENTS = 12

# Role assignment, most specific first. A repo carrying both `nlp` and
# `machine-learning` is a perception agent, not a generic inference one.
ROLE_TOPICS = [
    ("PERCEPTION", {"nlp", "sentiment-analysis", "text-classification",
                    "named-entity-recognition", "biobert", "distilbert",
                    "transformers", "computer-vision", "ocr",
                    "medical-imaging"}),
    ("INFERENCE", {"machine-learning", "deep-learning", "online-learning",
                   "binary-classification", "ensemble-methods",
                   "adaptive-algorithms", "keras", "tensorflow",
                   "scikit-learn"}),
    ("ORCHESTRATION", {"automation", "web-scraping", "multi-agent",
                       "multi-agent-systems", "lead-generation", "selenium"}),
    ("INTERFACE", {"react", "realtime-dashboard", "fastapi", "express",
                   "typescript", "postgresql", "firebase"}),
]

ROLE_BY_LANGUAGE = {"TypeScript": "INTERFACE", "JavaScript": "INTERFACE",
                    "Python": "INFERENCE", "Jupyter Notebook": "INFERENCE"}

# Where each role sits on the inferno ramp.
ROLE_T = {"PERCEPTION": 0.74, "INFERENCE": 0.52,
          "ORCHESTRATION": 0.34, "INTERFACE": 0.88}

SHAPE_TOPICS = {
    "binary-classification": "(None, 2)",
    "text-classification": "(None, 2)",
    "sentiment-analysis": "(None, 2)",
    "multi-agent": "(None, n)",
    "multi-agent-systems": "(None, n)",
}

THEMES = {
    "dark": {"page": "#0B0A09", "border": "#2A241E", "text": "#F5EFE7",
             "muted": "#9C9186", "accent": "#F98E08", "rule": "#221D18"},
    "light": {"page": "#FAF7F2", "border": "#E6DFD4", "text": "#16130F",
              "muted": "#6E655C", "accent": "#C2410C", "rule": "#EFE9DF"},
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def fetch(owner: str, token: str | None) -> list:
    url = f"https://api.github.com/users/{owner}/repos?per_page=100&sort=pushed"
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "agent-surface-profile"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def select(repos: list, limit: int = MAX_AGENTS) -> list:
    keep = [r for r in repos
            if not r.get("fork")
            and not r.get("archived")
            and not r.get("private")
            and r["name"] != OWNER]
    # Stars first, then most recently pushed.
    keep.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    keep.sort(key=lambda r: -r.get("stargazers_count", 0))
    return keep[:limit]


def agent_role(repo: dict) -> str:
    topics = set(repo.get("topics") or [])
    for role, keys in ROLE_TOPICS:
        if topics & keys:
            return role
    return ROLE_BY_LANGUAGE.get(repo.get("language") or "", "ORCHESTRATION")


def output_shape(repo: dict) -> str:
    for t in repo.get("topics") or []:
        if t in SHAPE_TOPICS:
            return SHAPE_TOPICS[t]
    return "(None,)"


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------
def _mono(text: str, x: float, y: float, size: float, fill: str,
          opacity: float = 1.0) -> str:
    if not text:
        return ""
    width = advance_width(text, FONTS["mono"], size)
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    op = "" if opacity >= 1.0 else f' opacity="{opacity}"'
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" fill="{fill}"'
            f' textLength="{width:.1f}" lengthAdjust="spacing"'
            f' font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"'
            f' xml:space="preserve"{op}>{esc}</text>')


def _truncate(text: str, size: float, max_px: float) -> str:
    if advance_width(text, FONTS["mono"], size) <= max_px:
        return text
    out = text
    while out and advance_width(out + "…", FONTS["mono"], size) > max_px:
        out = out[:-1]
    return out.rstrip() + "…"


def build_summary_svg(repos: list, theme: str) -> str:
    if theme not in THEMES:
        raise ValueError(f"unknown theme {theme!r}; expected 'dark' or 'light'")
    t = THEMES[theme]

    row_h = 44.0
    head_h = 116.0
    foot_h = 70.0
    height = head_h + max(1, len(repos)) * row_h + foot_h

    x_name, x_shape, x_role, x_param = PAD + 16, 646.0, 800.0, 1024.0

    parts = [
        f'<rect width="{W}" height="{height:.0f}" rx="14" fill="{t["page"]}"/>',
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{height - 1:.0f}"'
        f' rx="13.5" fill="none" stroke="{t["border"]}" stroke-width="1"/>',
        _mono("AGENT ROSTER", PAD, 42, 11.0, t["accent"]),
        _mono(f'Model: "{MODEL_NAME}"', PAD, 64, 10.0, t["muted"]),
        _mono("regenerated nightly", 992, 42, 9.5, t["muted"]),
    ]

    hy = 94.0
    parts += [
        _mono("Layer (project)", x_name, hy, 9.5, t["muted"]),
        _mono("Output Shape", x_shape, hy, 9.5, t["muted"]),
        _mono("Role", x_role, hy, 9.5, t["muted"]),
        _mono("Param #", x_param, hy, 9.5, t["muted"]),
        f'<line x1="{PAD}" y1="{hy + 13}" x2="{W - PAD}" y2="{hy + 13}"'
        f' stroke="{t["border"]}" stroke-width="1"/>',
    ]

    y = head_h + 26
    for r in repos:
        role = agent_role(r)
        colour = inferno(ROLE_T[role], theme)
        desc = _truncate(r.get("description") or "— no description —", 9.0, 548)

        parts += [
            f'<rect x="{PAD}" y="{y - 15:.1f}" width="3" height="24" rx="1.5"'
            f' fill="{colour}"/>',
            _mono(r["name"], x_name, y, 12.5, t["text"]),
            _mono(desc, x_name, y + 16, 9.0, t["muted"]),
            _mono(output_shape(r), x_shape, y, 11.0, t["text"]),
            _mono(role, x_role, y, 9.5, colour),
            _mono(f'{r.get("stargazers_count", 0):>5,}', x_param, y, 11.0,
                  t["text"]),
            f'<line x1="{PAD}" y1="{y + 28:.1f}" x2="{W - PAD}"'
            f' y2="{y + 28:.1f}" stroke="{t["rule"]}" stroke-width="1"/>',
        ]
        y += row_h

    roles = sorted({agent_role(r) for r in repos})
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    fy = height - 38
    parts += [
        _mono(f"Total agents: {len(repos)}      Trainable: {len(repos)}"
              f"      Params: {stars:,}", PAD, fy, 10.0, t["text"]),
        _mono(" · ".join(roles), PAD, fy + 17, 9.0, t["muted"]),
    ]

    return (f'<svg xmlns="http://www.w3.org/2000/svg"'
            f' viewBox="0 0 {W} {height:.0f}" width="{W}"'
            f' height="{height:.0f}" role="img"'
            f' aria-label="Agent roster of public repositories">'
            + "".join(parts) + "</svg>")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    try:
        raw = fetch(OWNER, token)
    except urllib.error.HTTPError as e:
        print(f"GitHub API {e.code}: {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"cannot reach GitHub: {e.reason}", file=sys.stderr)
        return 1

    repos = select(raw)
    if not repos:
        print("no eligible repositories", file=sys.stderr)
        return 1

    for theme in ("dark", "light"):
        with open(f"repos-{theme}.svg", "w") as f:
            f.write(build_summary_svg(repos, theme))
    print(f"repos-*.svg  {len(repos)} agents: "
          f"{', '.join(r['name'] for r in repos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
