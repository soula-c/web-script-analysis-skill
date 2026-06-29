# Yuce Login-State Guard

Use this workflow for `https://yuce.vsigo.cn` pages that must keep a stable
authenticated browser session for API-first data capture or scheduled work.

Yuce login policy is site-controlled. Do not try to bypass CAPTCHA, MFA,
device verification, password expiry, or other risk controls. The robust local
pattern is:

1. Reuse a dedicated Chrome profile and CDP port for all Yuce work on the same
   machine.
2. Run a login-state guard before business scripts call report APIs.
3. If the guard reports `manual_login_required`, open the visible Yuce page and
   ask the user to complete login in that browser.
4. After login, rerun the guard or use `--wait-for-manual-login` to continue
   automatically once the page no longer appears to be on the login surface.
5. Business scripts should fail early with a clear message instead of running
   partial reports when Yuce auth is unavailable.

## Helper

Use `scripts/yuce_auth_guard.py`.

Status check against an existing CDP Chrome:

```bash
python3 scripts/yuce_auth_guard.py --port 9222 --url https://yuce.vsigo.cn/
```

Open a Yuce page if no Yuce tab exists:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9222 \
  --url https://yuce.vsigo.cn/#/resource/report-view/dzKgpN3J9c \
  --open-if-missing
```

Start a separate Yuce Chrome only when the chosen port is not already running:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9222 \
  --profile-dir "$HOME/.codex/chrome-yuce" \
  --url https://yuce.vsigo.cn/ \
  --start-chrome \
  --open-if-missing
```

Scheduled tasks can use `--require-auth` so expired login exits nonzero before
the business script runs:

```bash
python3 scripts/yuce_auth_guard.py --port 9222 --require-auth
```

Business scripts may add an API probe when they have a cheap, known endpoint.
The probe runs inside the Yuce tab with browser credentials and prints only
sanitized response metadata:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9222 \
  --require-auth \
  --probe-path /api/reportForm/queryFormCards?formId=dzKgpN3J9c\&version=PROD \
  --probe-method POST \
  --probe-body '{}'
```

For a supervised run, let the browser stay open and wait for manual login:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9222 \
  --open-if-missing \
  --wait-for-manual-login 300 \
  --require-auth
```

The helper prints sanitized JSON only. It does not read or write passwords,
cookies, localStorage values, report data, or browser profile contents.

## Exit Codes

- `0`: login state appears usable, or status was reported without
  `--require-auth`.
- `1`: `--require-auth` was set and login appears unavailable.
- `2`: CDP/Chrome cannot be reached and `--start-chrome` was not requested or
  could not make the port ready.
- `3`: a CDP or page evaluation error occurred.

## Business Skill Integration

Before a Yuce business script calls report APIs, add a small preflight:

```bash
python3 "$WEB_SCRIPT_ANALYSIS_DIR/scripts/yuce_auth_guard.py" \
  --port "${YUCE_CHROME_PORT:-9222}" \
  --url "${YUCE_URL:-https://yuce.vsigo.cn/}" \
  --open-if-missing \
  --require-auth
```

If it fails with `manual_login_required`, notify the user and stop. Do not
generate stale, empty, or partial reports.
