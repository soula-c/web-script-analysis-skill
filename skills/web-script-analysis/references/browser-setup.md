# Browser Setup and Portability

## Dependency Decision

Chrome is not always required. Use this decision across agents:

- Public website, localhost, file, or non-login page: use the agent's browser or Playwright capability.
- Logged-in business system, existing browser tab, enterprise SSO, extension dependency, or cookies in the user's real profile: use an authorized real-browser bridge or Chrome CDP.
- API replay after request discovery: use local code or HTTP clients only if the required auth context can be provided safely without exposing secrets.

## Chrome Extension Boundary

Do not make a skill package silently install any browser extension. A skill is instruction and reusable resource content; extension installation changes the user's browser/profile and must remain an explicit user action.

Do not bundle a Chrome extension installer inside this skill unless all of these are true:

- the extension package is legally redistributable,
- the target organization owns the package and update policy,
- the user explicitly asks for an offline installer bundle,
- the bundle contains no account, profile, token, or machine-specific state.

For normal sharing, include only setup guidance. The receiving user should install or enable the browser integration supported by their agent, then verify that the agent can open or inspect a harmless page.

## Migration Checklist

When another agent receives this skill:

1. Put the folder under that machine's skill directory or import it through the skill installer.
2. Confirm the agent exposes a browser, Playwright, CDP, or equivalent web-control tool.
3. Confirm a real-browser bridge is available only if authenticated pages require it.
4. Have the user log in manually to protected sites in their own Chrome profile.
5. Run a harmless browser check before analysis: open a public page or list visible Chrome tabs.
6. Never copy cookies, local storage, browser profiles, passwords, or token files from the original machine.

## Safe Handling Rules

- Treat every `Cookie`, `Authorization`, `X-CSRF-Token`, `tenant_access_token`, `session`, `secret`, and `token` value as sensitive.
- Keep raw HAR files local and temporary unless the user explicitly asks to save them.
- Prefer sanitized derived artifacts: endpoint list, request schema, field map, and metric formulas.
- If a request cannot be replayed without secrets, use the authenticated browser session to trigger the request and collect only the response data needed for analysis.
