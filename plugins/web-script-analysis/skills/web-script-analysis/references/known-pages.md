# Known Page Families

These are non-secret routing hints from recurring work. Verify live request details before every analysis.

## Vsigo / Yuce Reports

- `https://yuce.vsigo.cn` login-state management
  - Use for Yuce scheduled tasks and report pages that need a durable authenticated Chrome/CDP session.
  - Read `references/yuce-auth-guard.md` before adding preflight checks to a Yuce business workflow.
  - Do not store Yuce passwords, cookies, localStorage values, session snapshots, or raw report payloads in skills or logs.
  - If CAPTCHA, MFA, device verification, or password expiry appears, leave the browser open and require manual completion.

- `https://a.vsigo.cn/login` and Vsigo ERP-backed pages
  - For `*.vsigo.cn` ERP scenes excluding `yuce.vsigo.cn`, default to environment-variable API login before manual browser login.
  - Read `references/vsigo-erp-login.md` before attempting credential-based recovery.
  - First run `python scripts/vsigo_erp_login.py --business-id sigo`; add `--port <cdp-port> --inject-browser-state` when a browser session is required.
  - Credentials must come from local environment variables or private secret storage; never store them in scripts, skills, logs, or generated artifacts.
  - If credentials are missing, show setup commands for macOS/Linux, macOS launchd, and Windows PowerShell before falling back to manual login.
  - If CAPTCHA, MFA, password expiry, device trust, or tenant ambiguity appears, stop and require manual login.

- `https://yuce.vsigo.cn/#/resource/report-view/dzKgpN3J9c`
  - Use for 万相台低效计划监控 and similar resource report pages.
  - Known API family: `getCardData`.
  - Pay attention to `QUERY_CONDITION`, report card ids, duplicated snapshot rows, `数据创建时间`, and task instance fields.

- Vsigo 利润报表 and 商品看板 pages
  - Use for GMV, gross margin, promotion fee/rate, pretax profit, budget-vs-actual, platform/store/brand/product drilldown.
  - Known API family: `querybidataV2`.
  - Validate scope, store naming, month coverage, and metric definitions before producing PDF or numeric conclusions.

## Qianchuan / Douyin

- `https://qianchuan.jinritemai.com/`
  - Use for 巨量千川 / 智投星 authenticated pages.
  - Recurring target: 同行优秀素材, 同行TOP视频参考, 素材榜单, video links, cover urls, awemeId/videoId.
  - Account routing may use an `aavid`/advertiser id. Read it from the current page, a command argument, or a machine-local environment variable; do not hardcode a user's account id in a shared skill.
  - Prefer captured page APIs and response data over visible cards.

## Feishu / Open Platform

- `https://open.feishu.cn/`
  - Use only for API documentation or app/admin verification when the user is logged in.
  - Never store `FEISHU_APP_ID`, `FEISHU_APP_SECRET`, tenant tokens, access tokens, webhook URLs, or table tokens in the skill.

## Handling Changes

If a known endpoint no longer appears:

1. Trigger the UI action that changes the target data.
2. Watch the new XHR/fetch request set.
3. Search response keys for visible metric names.
4. Update only local working notes unless the user asks to update this skill.
