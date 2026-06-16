#!/usr/bin/env python3
"""Scaffold, check, and synchronize web-data business skills."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


CONTRACT_VERSION = "1"
START = "<!-- web-script-analysis-contract:start -->"
END = "<!-- web-script-analysis-contract:end -->"
REQUIRED_LABELS = (
    "Target pages",
    "Interface hints",
    "Authentication",
    "Execution",
    "Validation",
    "Sensitive data",
)


def contract_block() -> str:
    return f"""\
{START}
## Shared Web Data Contract

Contract version: `{CONTRACT_VERSION}`

Prefer `$web-script-analysis` for browser capability detection, login-state reuse, interface discovery, request sanitization, and API validation.

If the shared skill is unavailable, continue only with this minimum independent workflow:

1. Detect an available browser, Playwright, CDP, or sanitized HAR path.
2. Reuse a user-owned authenticated profile; show the browser only for login, CAPTCHA, consent, or troubleshooting.
3. Prefer stable page APIs over visible-text scraping.
4. Never store passwords, cookies, tokens, authorization headers, private keys, or session snapshots.
5. Validate API-derived data against one visible or exported total.
6. State the date basis, units, dedupe rule, and whether data is live or captured.

If the minimum workflow is insufficient, tell the user to install the `web-script-analysis` skill or Codex plugin. Do not silently install browser extensions.
{END}"""


def skill_files(root: Path):
    if root.is_file() and root.name == "SKILL.md":
        yield root
        return
    for path in sorted(root.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if START in text or "## Business Web Configuration" in text:
            yield path


def replace_contract(text: str) -> tuple[str, bool]:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    block = contract_block()
    if pattern.search(text):
        updated = pattern.sub(block, text, count=1)
        return updated, updated != text
    return text, False


def inspect(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    if START not in text or END not in text:
        errors.append("missing managed contract markers")
    elif contract_block() not in text:
        errors.append("contract is stale")
    if "## Business Web Configuration" not in text:
        errors.append("missing Business Web Configuration section")
    for label in REQUIRED_LABELS:
        if f"- `{label}`:" not in text:
            errors.append(f"missing configuration label: {label}")
    return errors


def command_check(args) -> int:
    failures = 0
    for path in skill_files(args.root):
        errors = inspect(path)
        if errors:
            failures += 1
            print(f"FAIL {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK   {path}")
    return 1 if failures else 0


def command_sync(args) -> int:
    failures = 0
    for path in skill_files(args.root):
        text = path.read_text(encoding="utf-8")
        updated, changed = replace_contract(text)
        if START not in text or END not in text:
            failures += 1
            print(f"SKIP {path}: missing managed markers")
            continue
        if changed:
            path.write_text(updated, encoding="utf-8", newline="\n")
            print(f"SYNC {path}")
        else:
            print(f"OK   {path}")
    return 1 if failures else 0


def normalize_name(value: str) -> str:
    name = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not name or len(name) > 64:
        raise ValueError("skill name must normalize to 1-64 lowercase letters, digits, or hyphens")
    return name


def command_new(args) -> int:
    name = normalize_name(args.name)
    skill_dir = args.path / name
    if skill_dir.exists():
        print(f"Refusing to overwrite existing path: {skill_dir}", file=sys.stderr)
        return 1
    skill_dir.mkdir(parents=True)
    config = f"""\
## Business Web Configuration

- `Target pages`: {args.page}
- `Interface hints`: {args.interface}
- `Authentication`: {args.authentication}
- `Execution`: {args.execution}
- `Validation`: {args.validation}
- `Sensitive data`: Never store credentials or browser session material; list only business-safe identifiers and routing hints.
"""
    body = f"""\
---
name: {name}
description: {args.description}
---

# {args.title}

{contract_block()}

{config}
## Business Workflow

Define the domain filters, request fields, metric formulas, dedupe rules, outputs, and delivery behavior here.
"""
    (skill_dir / "SKILL.md").write_text(body, encoding="utf-8", newline="\n")
    print(skill_dir)
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check managed contracts and business configuration")
    check.add_argument("root", type=Path)
    check.set_defaults(func=command_check)

    sync = sub.add_parser("sync", help="Synchronize managed contract blocks")
    sync.add_argument("root", type=Path)
    sync.set_defaults(func=command_sync)

    new = sub.add_parser("new", help="Create a new web-data business skill")
    new.add_argument("name")
    new.add_argument("--path", type=Path, required=True)
    new.add_argument("--title", required=True)
    new.add_argument("--description", required=True)
    new.add_argument("--page", default="Discover from the user's target report")
    new.add_argument("--interface", default="Discover from live page network requests")
    new.add_argument("--authentication", default="User-owned authenticated browser profile")
    new.add_argument("--execution", default="Background reuse after one-time visible login")
    new.add_argument("--validation", default="Compare API-derived totals with one visible or exported total")
    new.set_defaults(func=command_new)
    return p


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
