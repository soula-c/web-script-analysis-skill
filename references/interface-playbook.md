# Interface Playbook

## What to Capture

For each promising request, record:

- page URL and user-visible report name
- endpoint path and method
- request body/query fields that define date, platform, shop, brand, product, pagination, sorting, and grouping
- response root path and data row path
- total fields and metric fields
- dedupe keys, snapshot fields, and timestamp fields
- one visible UI total used for validation

Avoid copying raw headers. Keep only header names that affect behavior, such as content type or tenant selector names, and redact values.

## Endpoint Triage

Prioritize requests with these signs:

- XHR/fetch endpoint returns JSON rows, cards, pivots, or chart series.
- Response contains the exact visible metric names or values.
- Request body includes the same filter names shown in the page.
- Endpoint is triggered when changing date, store, platform, brand, or pagination.

Deprioritize:

- tracking, log, beacon, perf, captcha, and static asset requests
- GraphQL introspection or unrelated menu/config calls
- large embedded app state unless it clearly contains the target dataset

## Replay Pattern

Use the smallest stable request:

```text
method: POST
url: https://example.com/api/report
body:
  dateRange: ...
  filters: ...
  page: 1
  pageSize: 1000
```

Then iterate pagination until no rows remain or the reported total is reached. Preserve request ordering and required wrapper fields from the page. If a server-side total differs from summed rows, report both and explain the likely aggregation rule.

## Validation Pattern

Before finalizing:

- Compare one API-derived total with the visible page/export total.
- Check date inclusivity and timezone.
- Confirm whether monetary values are yuan, cents, tax-included, or tax-excluded.
- Check whether repeated rows are snapshots, dimensions, or accidental duplicates.
- Deduplicate only after identifying a stable key such as record id, task instance id, order id, product id plus date, or latest creation time.

## HAR Summary

If using an exported HAR:

1. Ask for a sanitized HAR if possible.
2. Run `scripts/summarize_har.py`.
3. Inspect only the top candidate endpoints.
4. Build a replay or analysis script from the selected request schema, not from the whole HAR.
