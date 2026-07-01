---
name: web-script-analysis
description: Open web pages, inspect page scripts and network interfaces, capture reusable API request shapes, and perform fast data analysis from browser-authenticated web systems. Use when an agent needs to 打开网页, 自动抓取页面脚本, 分析页面接口, 复用接口查询数据, 导出/汇总后台数据, turn an authenticated business page into repeatable API-first analysis, or create/update a business skill that obtains data from web pages. Supports Codex Browser/Chrome, Playwright, Chrome DevTools Protocol, sanitized HAR files, and equivalent browser tools exposed by other agents without storing passwords, cookies, tokens, or secrets.
---

# Web Script Analysis

## Core Rule

Prefer API-first analysis over visible-page scraping. Use the page only to discover the real request shape, filters, auth context, and metric semantics; then replay the stable interface or exported network payload to calculate results.

Never store account names, passwords, cookies, authorization headers, tenant tokens, app secrets, private keys, or session snapshots in the skill, output files, commits, or memory.

## Browser Fallback Accountability

For recurring authenticated data tasks, opening or controlling Chrome/CDP is a fallback unless the task is explicitly UI-oriented. Before browser use, check for an existing script, request template, endpoint note, sanitized HAR summary, or business `data-source-map.md` entry. Use browser/CDP only when a direct API path is blocked by a missing or changed request shape, short-lived page-derived parameter, required manual verification, or explicit screenshot/UI debugging need.

When a task falls back to browser/CDP, state the reason, classify any no-response failure as port, target, login, page, endpoint, network, or timeout, and preserve non-secret request/validation notes so the next run can move back toward API-first execution.

## Vsigo ERP Default Auth Policy

For Vsigo ERP scenes under `*.vsigo.cn`, excluding `yuce.vsigo.cn`, default to environment-variable API login before using a manual browser login.

Required first path:

1. Read `references/vsigo-erp-login.md`.
2. Check `ERP_USER` and `ERP_PASSWORD`, including supported aliases `TMALL_DAILY_ERP_USER` and `TMALL_DAILY_ERP_PASSWORD`.
3. Run `python scripts/vsigo_erp_login.py --business-id sigo` to verify API login.
4. When a browser session is needed, run `python scripts/vsigo_erp_login.py --business-id sigo --port <cdp-port> --inject-browser-state` before opening ERP pages.

Manual login is a fallback only when credentials are missing, the helper fails, the page requires CAPTCHA/MFA/device trust/password change, or the user explicitly requests manual login. If credentials are missing, show the macOS/Linux, macOS launchd, and Windows PowerShell setup commands from `scripts/self_check.py` or `references/vsigo-erp-login.md` before asking the user to log in manually.

When credentials are missing, do not silently choose manual login. Ask the user to choose:

1. Set ERP environment variables now (Recommended): show exact commands for macOS/Linux, macOS launchd, and Windows PowerShell, then retry `python scripts/vsigo_erp_login.py --business-id sigo`.
2. Continue with manual browser login for this run only.

If the user does not explicitly choose manual login, keep the recommended path as environment-variable setup.

## Capability Detection

Inspect the tools available in the current agent before choosing an implementation:

- Use an agent-controlled browser or Playwright for public pages, local apps, files, and non-authenticated inspection.
- Use the user's real browser profile, Chrome extension bridge, or Chrome CDP when the page depends on an existing login, enterprise SSO, extensions, or authenticated tabs.
- Use a sanitized HAR or exported response for offline analysis when live browser control is unavailable.
- If no suitable browser or capture capability exists, state the missing capability and ask the user to install or enable the relevant browser integration. Do not silently install browser extensions or copy browser profiles.

For general setup and portability details, read `references/browser-setup.md`. When running in Codex, also read `references/codex-browser.md`.

For concrete adapter examples across Codex, Playwright/CDP-capable agents, and offline HAR workflows, read `references/tool-adapters.md`.

For Vsigo ERP pages (`*.vsigo.cn` except `yuce.vsigo.cn`), read `references/vsigo-erp-login.md` and use environment-variable API login as the default auth path before manual browser login.

For Yuce pages (`https://yuce.vsigo.cn`) used by multiple scheduled or ad hoc report tasks, read `references/yuce-auth-guard.md`. Prefer a stable dedicated Chrome profile plus login-state preflight; if CAPTCHA or verification appears, stop for manual completion instead of attempting to bypass site controls.

## Workflow

1. Identify the target page, date range, business scope, and final metric or artifact.
2. For non-Yuce Vsigo ERP pages, run the ERP default auth policy above before opening the page. For all other pages, open the page through the best available browser surface. If the user is already logged in, preserve that session and reuse the existing tab or dedicated profile when available.
3. Capture the interface evidence:
   - page URL and visible filters
   - relevant XHR/fetch endpoints
   - request method, path, query/body shape, pagination, sorting, and date fields
   - response fields used for metrics
   - console errors or duplicate snapshot clues when relevant
4. Reconstruct the smallest stable request. Preserve business filters exactly; remove volatile headers and secrets.
5. Pull the needed data through the discovered API, downloaded export, or sanitized HAR/network log.
6. Validate totals against one visible page value or a known exported total before reporting.
7. Explain the data rule briefly: dedupe keys, snapshot interpretation, date basis, currency/unit, and whether the result is current live data or a captured snapshot.

## Interface Discovery Notes

When browser tooling exposes network interception, capture requests directly. When it does not, use one of these fallbacks:

- Ask the user to export a HAR from DevTools and analyze the sanitized file.
- Use page scripts and app state only to find endpoint names and request constructors.
- Use visible UI only as a validation surface, not the primary data source, unless no interface is available.

For repeatable request templates and capture notes, read `references/interface-playbook.md`.

## Downstream Skill Contract

Business-specific skills may declare this skill as their shared web-data capability. When invoked from another skill:

1. Follow this skill for browser selection, login-state reuse, interface discovery, sanitization, and validation.
2. Follow the business skill for URLs, endpoint hints, profiles, ports, field mappings, metrics, schedules, and report rules.
3. If this skill is unavailable, do not pretend the dependency ran. Tell the user to install `web-script-analysis`, then use the business skill's minimal fallback only when it contains enough instructions to proceed safely.

When creating or maintaining business skills, read `references/business-skill-authoring.md`. Use `scripts/manage_business_skills.py` to scaffold new skills, synchronize the versioned minimum contract, and detect missing business configuration.

## Known Page Families

For the user's recurring analysis pages and endpoint hints, read `references/known-pages.md` before starting. Treat those entries as non-secret routing hints only; verify live request details every time because dashboards change.

## Optional Helper

Use `scripts/summarize_har.py` on a sanitized HAR file to list likely API endpoints:

```bash
python scripts/summarize_har.py path/to/sanitized.har --top 40
```

The script prints methods, hosts, paths, status codes, content types, and sample request/response keys. It does not require credentials and should only be run on files that have already been stripped of cookies and authorization headers.

Before sharing or installing on another machine, run:

```bash
python scripts/self_check.py .
```
