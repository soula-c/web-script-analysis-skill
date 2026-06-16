# Share Checklist

Before sharing this skill or a business skill built on it:

- Run `python scripts/self_check.py .`.
- Confirm no credentials, cookies, tokens, browser profiles, raw HARs, private response captures, or personal local paths are included.
- Confirm recipient-specific values are documented as environment variables or command arguments.
- Confirm the receiving machine has Python 3.10+ and a browser/control option appropriate for the target page.
- Include the matching business skills if the user expects ready-to-run workflows.
- For Codex users, include the plugin folder only as an installation wrapper; the portable skill remains under `skills/web-script-analysis`.

Recommended recipient onboarding:

1. Install `web-script-analysis`.
2. Run `python scripts/self_check.py .`.
3. Open one harmless public page with the target agent's browser tool.
4. Configure a dedicated browser profile for authenticated systems.
5. Run one live API capture and validate one total.
6. Only then enable scheduled jobs.
