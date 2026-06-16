# Codex Browser Routing

Use this reference only when the current agent is Codex.

## Preferred Surfaces

- Use the Codex in-app Browser for public pages, localhost, files, and non-authenticated inspection.
- Use the Codex Chrome integration when the task requires the user's existing Chrome tabs, cookies, extensions, enterprise SSO, or real browser profile.
- Use Chrome CDP when a business skill already provides deterministic CDP scripts or scheduled automation.

The Codex Chrome Extension and Chrome CDP are different mechanisms. A skill that uses `--remote-debugging-port` does not automatically depend on the Codex Chrome Extension.

## Missing Capability

If a business skill invokes `$web-script-analysis` but the skill is not installed, tell the user:

```text
This workflow uses the shared web-script-analysis skill for browser and API discovery. Install that skill or the web-script-analysis Codex plugin, then retry.
```

Do not silently install the Chrome extension. If the Codex Chrome integration is required but unavailable, follow the installed Chrome plugin's setup and repair instructions.

## Login and Background Operation

- Open a visible browser only for first login, expired login, CAPTCHA, consent, or troubleshooting.
- For repeat CDP jobs, prefer a dedicated persistent profile and background/headless execution when the target site supports it.
- If a site rejects headless execution, retain a minimized or hidden dedicated browser window and document that compatibility exception in the business skill.
