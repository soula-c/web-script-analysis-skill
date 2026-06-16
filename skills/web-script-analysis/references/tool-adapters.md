# Tool Adapters

Use the strongest capability that is actually available in the current agent. Keep the business skill responsible for target pages and metric rules.

## Codex

Use the Codex in-app Browser for public pages, localhost, static files, and non-authenticated inspection. Use Codex Chrome only when the user's real Chrome profile, existing tabs, enterprise SSO, or extensions matter. If a business skill already has CDP scripts, prefer those deterministic scripts for scheduled jobs.

## Playwright-Capable Agents

Use Playwright or the agent's browser tool to:

1. open the target page,
2. let the user log in manually if needed,
3. capture network requests when the tool exposes them,
4. extract the smallest stable request shape,
5. replay or paginate the API outside the visible page when safe.

Avoid broad body-text scraping when an XHR/fetch endpoint contains the same data.

## Chrome DevTools Protocol

Use Chrome/Chromium CDP when a persistent authenticated browser profile is available:

```bash
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/.cache/web-script-analysis-profile" \
  "https://example.com/report"
```

Then connect to `http://127.0.0.1:9222/json/list`, choose the target page, evaluate authenticated `fetch()` calls in the page, and keep secrets inside the browser session. Do not serialize cookies or auth headers.

## Offline HAR

When live browser control is unavailable:

1. Ask the user to export a HAR from DevTools.
2. Ask them to sanitize cookies, authorization headers, tokens, and private response data.
3. Run `scripts/summarize_har.py sanitized.har`.
4. Build the analysis from endpoint shape, request fields, response keys, and exported/sanitized rows.

Offline mode can discover request structure, but live totals still need validation against the current page or an approved export.

## Minimum Handoff

When the selected tool cannot complete live capture, ask for one of:

- a sanitized HAR,
- a copied request as cURL with secrets removed,
- a sanitized JSON response sample,
- a CSV/XLSX export plus the visible filters used.
