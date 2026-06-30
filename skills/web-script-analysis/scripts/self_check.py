#!/usr/bin/env python3
"""Check a web-script-analysis skill folder before sharing or installing."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = [
    "SKILL.md",
    "references/browser-setup.md",
    "references/business-skill-authoring.md",
    "references/codex-browser.md",
    "references/interface-playbook.md",
    "references/known-pages.md",
    "references/yuce-auth-guard.md",
    "references/vsigo-erp-login.md",
    "references/tool-adapters.md",
    "references/share-checklist.md",
    "scripts/manage_business_skills.py",
    "scripts/summarize_har.py",
    "scripts/yuce_auth_guard.py",
    "scripts/vsigo_erp_login.py",
]

REQUIRED_POLICY_SNIPPETS = [
    "For Vsigo ERP scenes under `*.vsigo.cn`, excluding `yuce.vsigo.cn`, default to environment-variable API login",
    "Manual login is a fallback only",
    "When credentials are missing, do not silently choose manual login",
    "python scripts/vsigo_erp_login.py --business-id sigo",
]

REQUIRED_AGENT_SNIPPETS = [
    "default to environment-variable API login before manual browser login",
    "do not silently choose manual login",
    "setting ERP environment variables now (Recommended",
    "python scripts/vsigo_erp_login.py --business-id sigo",
    "Use manual login only if the user chooses it",
]

SENSITIVE_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
        r"C:\\Users\\[^\\\s]+",
        r"/Users/[^/\s]+",
        r"authorization\s*[:=]\s*['\"][^'\"]+",
        r"cookie\s*[:=]\s*['\"][^'\"]+",
        r"tenant_access_token\s*[:=]\s*['\"][^'\"]+",
        r"app_secret\s*[:=]\s*['\"][^'\"]+",
        r"smtp_password\s*[:=]\s*['\"][^'\"]+",
    ]
]


def iter_text_files(root: Path):
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".yaml", ".yml", ".json", ".txt"}:
            yield path


def launchctl_getenv(name: str) -> str:
    try:
        return subprocess.check_output(["launchctl", "getenv", name], text=True, stderr=subprocess.DEVNULL).strip("\n")
    except Exception:
        return ""


def has_env(name: str, aliases: tuple[str, ...]) -> bool:
    for key in (name, *aliases):
        if os.environ.get(key) or launchctl_getenv(key):
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", type=Path)
    args = parser.parse_args()

    root = args.skill_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            errors.append(f"missing required file: {rel}")

    skill_md = root / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        if "name: web-script-analysis" not in text:
            errors.append("SKILL.md frontmatter must contain name: web-script-analysis")
        if "web-script-analysis" not in text:
            errors.append("SKILL.md should mention web-script-analysis for downstream invocation")
        for snippet in REQUIRED_POLICY_SNIPPETS:
            if snippet not in text:
                errors.append(f"SKILL.md missing ERP default auth policy snippet: {snippet}")

    agent_yaml = root / "agents/openai.yaml"
    if agent_yaml.is_file():
        text = agent_yaml.read_text(encoding="utf-8")
        for snippet in REQUIRED_AGENT_SNIPPETS:
            if snippet not in text:
                errors.append(f"agents/openai.yaml missing ERP default auth prompt snippet: {snippet}")

    for path in iter_text_files(root):
        if path.name == "self_check.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible sensitive or machine-specific value in {path.relative_to(root)}")
                break

    for rel in (
        "scripts/manage_business_skills.py",
        "scripts/summarize_har.py",
        "scripts/yuce_auth_guard.py",
        "scripts/vsigo_erp_login.py",
    ):
        path = root / rel
        if path.is_file():
            compile(path.read_text(encoding="utf-8"), str(path), "exec")

    if not has_env("ERP_USER", ("TMALL_DAILY_ERP_USER",)) or not has_env("ERP_PASSWORD", ("TMALL_DAILY_ERP_PASSWORD",)):
        warnings.append(
            "optional Vsigo ERP API login is not configured on this machine.\n"
            "  macOS/Linux shell:\n"
            "    export ERP_USER='your-erp-account'\n"
            "    read -s ERP_PASSWORD\n"
            "    export ERP_PASSWORD\n"
            "  macOS launchd jobs:\n"
            "    launchctl setenv ERP_USER 'your-erp-account'\n"
            "    read -s ERP_PASSWORD\n"
            "    launchctl setenv ERP_PASSWORD \"$ERP_PASSWORD\"\n"
            "    unset ERP_PASSWORD\n"
            "  Windows PowerShell:\n"
            "    [Environment]::SetEnvironmentVariable(\"ERP_USER\", \"your-erp-account\", \"User\")\n"
            "    $erpPassword = Read-Host \"ERP password\" -AsSecureString\n"
            "    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($erpPassword)\n"
            "    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)\n"
            "    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)\n"
            "    [Environment]::SetEnvironmentVariable(\"ERP_PASSWORD\", $plain, \"User\")\n"
            "    Remove-Variable plain, erpPassword"
        )

    if errors:
        print("web-script-analysis self-check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"web-script-analysis self-check passed: {root}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
