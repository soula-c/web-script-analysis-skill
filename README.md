# Web Script Analysis Skill

Portable Agent Skill for opening web pages, discovering page scripts and data interfaces, reusing stable API request shapes, and performing API-first data analysis from authenticated web systems.

This repository is intentionally focused on one shared capability:

- `skills/web-script-analysis`: portable Agent Skill source.
- `plugins/web-script-analysis`: Codex plugin wrapper that contains the same skill.
- `dist/`: ZIP packages for people who do not use Git.

The skill does not contain passwords, cookies, tokens, browser profiles, HAR captures, private data exports, or user-specific account identifiers.

## Download Without A GitHub Account

If this repository is public, people do not need a GitHub account.

Options:

- Open the repository page and choose `Code` -> `Download ZIP`.
- Run `git clone https://github.com/soula-c/web-script-analysis-skill.git`.
- Download one of the ZIP packages from `dist/`.

## Install As A Portable Agent Skill

Copy the skill folder into the target agent's skill directory.

Codex on macOS/Linux:

```bash
mkdir -p ~/.codex/skills
cp -R skills/web-script-analysis ~/.codex/skills/
python ~/.codex/skills/web-script-analysis/scripts/self_check.py ~/.codex/skills/web-script-analysis
```

Optional ERP API login setup for Vsigo workflows:

```bash
export ERP_USER='your-erp-account'
read -s ERP_PASSWORD
export ERP_PASSWORD
python ~/.codex/skills/web-script-analysis/scripts/vsigo_erp_login.py --business-id sigo
```

For macOS jobs launched by `launchd`, store the values in the launchd environment instead of only the current shell:

```bash
launchctl setenv ERP_USER 'your-erp-account'
read -s ERP_PASSWORD
launchctl setenv ERP_PASSWORD "$ERP_PASSWORD"
unset ERP_PASSWORD
```

Codex on Windows PowerShell:

```powershell
$target = Join-Path $HOME ".codex\skills"
New-Item -ItemType Directory -Force $target | Out-Null
Copy-Item -Recurse -Force .\skills\web-script-analysis $target
python (Join-Path $target "web-script-analysis\scripts\self_check.py") (Join-Path $target "web-script-analysis")
```

Optional ERP API login setup for Vsigo workflows:

```powershell
[Environment]::SetEnvironmentVariable("ERP_USER", "your-erp-account", "User")
$erpPassword = Read-Host "ERP password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($erpPassword)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
[Environment]::SetEnvironmentVariable("ERP_PASSWORD", $plain, "User")
Remove-Variable plain, erpPassword
python (Join-Path $target "web-script-analysis\scripts\vsigo_erp_login.py") --business-id sigo
```

For other agents, import the `skills/web-script-analysis` folder according to that agent's skill or tool packaging mechanism.

## Install As A Codex Plugin

Use `plugins/web-script-analysis` when you want the Codex plugin wrapper. The wrapper is for Codex installation convenience only; the underlying portable skill remains `skills/web-script-analysis`.

If the Codex plugin workflow is unavailable on a target machine, install the portable skill folder instead.

## Supported Workflows

- Public or local pages through an agent-controlled browser.
- Authenticated systems through the user's browser profile, a real-browser bridge, or Chrome/Chromium CDP.
- Deterministic scheduled jobs through Chrome/Chromium DevTools Protocol.
- Offline analysis from sanitized HAR files, exported request samples, or sanitized JSON/CSV data.

The preferred analysis pattern is API-first:

1. Use the page to discover the real request shape and filters.
2. Reconstruct the smallest stable request.
3. Pull data through the API, export, or sanitized HAR.
4. Validate one API-derived total against the visible page or approved export.
5. Report date basis, units, dedupe rules, and whether the data is live or captured.

## Browser And Login Safety

- Open a visible browser only for first login, expired login, CAPTCHA, consent, or troubleshooting.
- Reuse a user-owned browser profile for authenticated pages.
- Do not copy browser profiles between machines.
- Do not serialize cookies, authorization headers, tokens, or local storage.
- Do not bundle browser extensions or silently install extensions.
- For Vsigo ERP scenes under `*.vsigo.cn`, excluding `yuce.vsigo.cn`, workflows default to environment-variable API login with `ERP_USER` and `ERP_PASSWORD` before manual browser login.
- If ERP credentials are missing, the workflow must ask the user to choose between setting environment variables now (recommended) or manual browser login for this run only.
- Manual login is a fallback only when the user chooses it, the API helper fails, CAPTCHA/MFA/device trust/password change appears, or the user explicitly asks for manual login.

## Creating Business Skills

Use the included tool to create business-specific skills that can use this shared web-data capability while still remaining usable on their own:

```bash
python skills/web-script-analysis/scripts/manage_business_skills.py new my-business-skill \
  --path skills \
  --title "My Business Skill" \
  --description "Analyze data from an authenticated business dashboard." \
  --page "https://example.com/report" \
  --interface "POST /api/report"
```

Check managed business skills:

```bash
python skills/web-script-analysis/scripts/manage_business_skills.py check skills
```

Synchronize only managed shared-contract blocks:

```bash
python skills/web-script-analysis/scripts/manage_business_skills.py sync skills
```

The sync command does not modify business URLs, endpoint hints, formulas, scripts, or report rules.

## Share Checklist

Before sharing a modified copy:

```bash
python skills/web-script-analysis/scripts/self_check.py skills/web-script-analysis
```

Also confirm:

- No credentials, cookies, tokens, browser profiles, private HAR files, or private response captures are included.
- Machine-specific values are documented as environment variables or command arguments.
- ZIP packages are regenerated after changes if you plan to share via `dist/`.

## Repository Maintenance

When updating the skill, keep these copies aligned:

- `skills/web-script-analysis`
- `plugins/web-script-analysis/skills/web-script-analysis`
- `dist/web-script-analysis-agent-skill.zip`
- `dist/web-script-analysis-codex-plugin.zip`

The plugin is an installation wrapper, not a separate implementation.
