# Vsigo ERP Login Recovery

Use this reference only for user-approved local recovery of Vsigo ERP login state in authenticated browser/API workflows. Do not use it for unrelated sites, and do not store credentials, cookies, tokens, or session snapshots in the skill, repository, logs, or generated reports.

## When To Use

Prefer an existing logged-in dedicated Chrome profile. Use ERP login recovery only when all of these are true:

- The workflow targets Vsigo ERP pages such as `a.vsigo.cn`, `idata-dc-admin.vsigo.cn`, or `idata-platform.vsigo.cn`.
- The user has explicitly authorized using their ERP account for local automation.
- Credentials are supplied from machine-local environment variables or a private secret store.
- The login page does not require CAPTCHA, MFA, password change, or other interactive approval.

If CAPTCHA, MFA, device trust, password expiry, or tenant ambiguity appears, stop and ask for manual login. Do not attempt to bypass interactive security controls.

## Environment Variables

The helper reads credentials from environment variables and, on macOS, can fall back to `launchctl getenv` so `launchd` jobs can share the same values.

Default names:

```bash
ERP_USER
ERP_PASSWORD
```

Supported aliases:

```bash
TMALL_DAILY_ERP_USER
TMALL_DAILY_ERP_PASSWORD
```

Never echo the password. For macOS launchd testing:

```bash
launchctl setenv ERP_USER 'account'
read -s ERP_PASSWORD
launchctl setenv ERP_PASSWORD "$ERP_PASSWORD"
unset ERP_PASSWORD
```

For an interactive macOS/Linux shell:

```bash
export ERP_USER='account'
read -s ERP_PASSWORD
export ERP_PASSWORD
```

For Windows PowerShell user-level variables:

```powershell
[Environment]::SetEnvironmentVariable("ERP_USER", "account", "User")
$erpPassword = Read-Host "ERP password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($erpPassword)
$plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
[Environment]::SetEnvironmentVariable("ERP_PASSWORD", $plain, "User")
Remove-Variable plain, erpPassword
```

After installing the skill on another machine, run `scripts/self_check.py`.
If it reports that ERP environment variables are missing, API login recovery is not available on that machine yet and the workflow must use an existing browser login or manual login.

## Interface Contract

Live page inspection confirmed this current flow:

1. `POST https://erp-business-common-api.vsigo.cn/ums/account-login/login`
   - body: `{"username": "<user>", "password": "md5(<password>)"}`
   - success returns `account_token`.
2. `POST https://erp-business-common-api.vsigo.cn/ums/account/query-account-business`
   - header: `accountToken: <account_token>`
   - returns available business tenants.
3. `POST https://erp-business-common-api.vsigo.cn/ums/account/change-account-business`
   - headers: `accountToken: <account_token>`, `businessId: <business_id>`
   - returns app tokens; the ERP app token is the entry where `app_name == "ERP"`.

Use `business_id=sigo` by default only for this user's Vsigo workflows when it is present. Otherwise require an explicit business id.

## Helper

Run a sanitized API-only probe:

```bash
python scripts/vsigo_erp_login.py --business-id sigo
```

Inject recovered login state into a Chrome DevTools Protocol session after a successful API login:

```bash
python scripts/vsigo_erp_login.py --business-id sigo --port 9333 --inject-browser-state
```

The helper prints only status, selected tenant metadata, and boolean token presence. It must not print passwords, account tokens, app tokens, cookies, or raw response bodies.

## Validation

After recovery, validate the browser context through a harmless authenticated request or by resolving an ERP channel tree. For downstream report workflows, the business-specific skill should still validate one visible or known total before using API data.
