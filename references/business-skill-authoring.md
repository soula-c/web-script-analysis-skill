# Business Skill Authoring

## Division of Responsibility

Keep detailed and frequently evolving web mechanics in `web-script-analysis`:

- browser/tool selection
- visible login versus background reuse
- interface discovery and HAR analysis
- request sanitization
- generic validation and troubleshooting

Keep domain ownership in each business skill:

- target pages and report names
- endpoint/card/form hints
- Chrome profile and CDP port when deterministic scripts require them
- request filters and field mappings
- dedupe and snapshot rules
- metric formulas, output format, scheduling, and recipients

Every business skill must also embed the versioned minimum contract so it remains usable when distributed alone.

## Required Structure

Each web-data business skill must contain:

1. The exact marker-delimited contract managed by `scripts/manage_business_skills.py`.
2. A `## Business Web Configuration` section.
3. These configuration labels:
   - `Target pages`
   - `Interface hints`
   - `Authentication`
   - `Execution`
   - `Validation`
   - `Sensitive data`

The values may point to a business reference file when details are extensive.

## Commands

Create a new business skill:

```bash
python scripts/manage_business_skills.py new my-business-analysis \
  --path path/to/skills \
  --title "My Business Analysis" \
  --description "Analyze authenticated business data from the target dashboard." \
  --page "https://example.com/report" \
  --interface "POST /api/report" \
  --authentication "Persistent user-owned browser profile" \
  --execution "Background after one-time visible login" \
  --validation "Compare API total with the visible report total"
```

Check a collection without changing files:

```bash
python scripts/manage_business_skills.py check path/to/skills
```

Directory checks inspect only skills already marked as managed web-data business skills. To strictly test one candidate that may be missing the contract, pass its `SKILL.md` path directly.

Synchronize contract blocks after the base contract changes:

```bash
python scripts/manage_business_skills.py sync path/to/skills
```

`sync` changes only text between the managed markers. It does not edit business configuration, scripts, formulas, or references.
