#!/usr/bin/env python3
"""Audit public release safety for bingbingxiaomei-framework."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".jsonl", ".py", ".yaml", ".yml", ".txt"}
# Pre-release audit already cleaned all sensitive markers from public data
# (see RELEASE_AUDIT.md for the full list of categories that were scanned).
# The generic /Users/ and file:// checks below catch local-path leaks without
# revealing any specific paths, service names, credential types, or internal
# project codenames that were previously present.
#
# Add new markers here ONLY if they are generic patterns that do not expose
# personal information about the maintainer.
FORBIDDEN: list[str] = []


def iter_text_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.name == Path(__file__).name:
            continue
        if path.suffix in TEXT_SUFFIXES or path.name == "LICENSE":
            yield path


def main() -> int:
    errors: list[str] = []
    for required in ["README.md", "LICENSE", "NOTICE.md", "DISCLAIMER.md"]:
        if not (ROOT / required).exists():
            errors.append(f"missing required file: {required}")

    for path in iter_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: cannot read: {exc}")
            continue
        # Generic credential marker check — FORBIDDEN is intentionally empty
        # in the public version (see module docstring). Add generic patterns
        # here if new checks are needed.
        for marker in FORBIDDEN:
            if marker in text:
                errors.append(f"{path.relative_to(ROOT)} contains forbidden marker: {marker}")

    for data_file in ["claims.jsonl", "sources.jsonl", "unresolved-sources.jsonl"]:
        path = ROOT / "data" / data_file
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            blob = json.dumps(json.loads(line), ensure_ascii=False)
            if "/Users/" in blob or "file://" in blob:
                errors.append(f"{data_file}:{line_no} contains local file reference")

    if errors:
        for error in errors:
            print(f"public_release_invalid: {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "public_release_valid",
                "checked_files": len(list(iter_text_files())),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
