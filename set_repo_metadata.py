#!/usr/bin/env python3
"""Apply reviewed descriptions and topics to GitHub repos via the gh CLI.

Two-phase by design: --dry-run prints exactly what would change so it can be
read before anything touches a public account.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

import yaml

OWNER = "HariKarthick22"


def load_metadata(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def apply(repo: str, meta: dict, dry_run: bool) -> str:
    desc = meta["description"]
    topics = meta["topics"]

    if dry_run:
        return (f"{repo}\n"
                f"    description: {desc}\n"
                f"    topics:      {', '.join(topics)}")

    subprocess.run(
        ["gh", "repo", "edit", f"{OWNER}/{repo}", "--description", desc],
        check=True, capture_output=True,
    )
    topic_args = []
    for t in topics:
        topic_args += ["--add-topic", t]
    subprocess.run(
        ["gh", "repo", "edit", f"{OWNER}/{repo}", *topic_args],
        check=True, capture_output=True,
    )
    return f"{repo}: applied ({len(topics)} topics)"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--metadata", default="metadata.yml")
    args = ap.parse_args()

    failures = 0
    for repo, meta in load_metadata(args.metadata).items():
        try:
            print(apply(repo, meta, args.dry_run))
        except subprocess.CalledProcessError as e:
            failures += 1
            err = e.stderr.decode().strip() if e.stderr else str(e)
            print(f"{repo}: FAILED — {err}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
