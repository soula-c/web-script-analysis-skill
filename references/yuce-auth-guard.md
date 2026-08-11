# Yuce Login-State Guard

Use this workflow for `https://yuce.vsigo.cn` pages that must keep a stable
authenticated browser session for API-first data capture or scheduled work.

Yuce login policy is site-controlled. Use environment credentials only for the
normal account/password login surface. Do not try to bypass CAPTCHA, SMS code,
MFA, slider verification, device verification, password expiry, or other risk
controls. The robust local pattern is:

1. Reuse CDP port `9224` and the dedicated profile
   `~/.codex/chrome-yuce-tmall-review` for all Yuce work on this machine.
2. Store `YUCE_USER` and `YUCE_PASSWORD` in the machine-local environment.
3. Run a login-state guard before business scripts call report APIs. The guard
   reads `YUCE_USER` / `YUCE_PASSWORD` from the process environment or macOS
   `launchctl getenv`, and attempts password login with CDP trusted keyboard
   input when the page is on a simple login form. Trusted input is required:
   assigning `input.value` can change the visible text without updating the
   current Yuce frontend state, so clicking login sends no request.
4. If the guard reports `manual_login_required`, open the visible Yuce page and
   ask the user to complete login or verification in that browser.
5. After login, rerun the guard or use `--wait-for-manual-login` to continue
   automatically once the page no longer appears to be on the login surface.
6. Business scripts should fail early with a clear message instead of running
   partial reports when Yuce auth is unavailable.

If the credential fields visibly contain values but no login request is sent,
treat that as an outdated guard/frontend event compatibility failure. Update or
repair `yuce_auth_guard.py`; do not ask the user to re-enter configured
credentials. Manual action remains appropriate only for a real security
challenge, absent credentials, or a rejected credential response.

## Environment Variables

Default names:

```bash
YUCE_USER
YUCE_PASSWORD
```

Supported aliases:

```bash
YUCE_USERNAME
YUCE_PASS
```

For macOS launchd jobs and GUI-launched Codex sessions:

```bash
launchctl setenv YUCE_USER 'account'
read -s YUCE_PASSWORD
launchctl setenv YUCE_PASSWORD "$YUCE_PASSWORD"
unset YUCE_PASSWORD
```

For an interactive macOS/Linux shell:

```bash
export YUCE_USER='account'
read -s YUCE_PASSWORD
export YUCE_PASSWORD
```

For Windows PowerShell user-level variables:

```powershell
[Environment]::SetEnvironmentVariable("YUCE_USER", "account", "User")
$yucePassword = Read-Host "Yuce password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($yucePassword)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
[Environment]::SetEnvironmentVariable("YUCE_PASSWORD", $plain, "User")
Remove-Variable plain, yucePassword
```

Never echo the password. The helper prints only whether auto-login was
attempted and the sanitized outcome.

## Helper

Use `scripts/yuce_auth_guard.py`.

Status check against an existing CDP Chrome:

```bash
python3 scripts/yuce_auth_guard.py --port 9224 --url https://yuce.vsigo.cn/
```

Open a Yuce page if no Yuce tab exists:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9224 \
  --url https://yuce.vsigo.cn/#/resource/report-view/dzKgpN3J9c \
  --open-if-missing
```

Start a separate Yuce Chrome only when the chosen port is not already running:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9224 \
  --profile-dir "$HOME/.codex/chrome-yuce-tmall-review" \
  --url https://yuce.vsigo.cn/ \
  --start-chrome \
  --open-if-missing
```

Scheduled tasks can use `--require-auth` so expired login exits nonzero before
the business script runs. If `YUCE_USER` and `YUCE_PASSWORD` are available and
the page shows a normal password form, the guard tries to log in automatically:

```bash
python3 scripts/yuce_auth_guard.py --port 9224 --require-auth
```

Disable environment password login for a diagnostic manual-only run:

```bash
python3 scripts/yuce_auth_guard.py --port 9224 --require-auth --no-auto-login
```

Business scripts may add an API probe when they have a cheap, known endpoint.
The probe runs inside the Yuce tab with browser credentials and prints only
sanitized response metadata:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9224 \
  --require-auth \
  --probe-path /api/reportForm/queryFormCards?formId=dzKgpN3J9c\&version=PROD \
  --probe-method POST \
  --probe-body '{}'
```

For a supervised run, let the browser stay open and wait for manual login:

```bash
python3 scripts/yuce_auth_guard.py \
  --port 9224 \
  --open-if-missing \
  --wait-for-manual-login 300 \
  --require-auth
```

The helper prints sanitized JSON only. It reads passwords from environment
variables for form submission but never prints them. It does not read or write
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
  --port "${YUCE_CHROME_PORT:-9224}" \
  --url "${YUCE_URL:-https://yuce.vsigo.cn/}" \
  --open-if-missing \
  --require-auth
```

If it fails with `manual_login_required`, notify the user and stop. Do not
generate stale, empty, or partial reports. If the failure reason mentions
missing credentials, show the environment variable commands above. If it
mentions a security challenge, leave the browser open for manual completion.
