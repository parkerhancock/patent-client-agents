## USPTO Patent Public Search Guide

Use these tips whenever you call `publications.search`:

1. **Field aliases require trailing periods.** Format is `<term>.<ALIAS.>`
   - Publication numbers: `7664130.PN.` (UI buttons insert uppercase aliases).
   - Application numbers: `15375362.APNR.` or `13/965626.APP.`
   - Dates: `20240115.AD.` or ranges like `@PD>=20240101<=20240131`.
   - Other common aliases: `.TI.` (title), `.AB.` (abstract), `.CPC.`, `.AINM.` (inventor).
2. **Boolean/proximity logic mirrors EAST/WEST.** Capitalized `AND/OR/NOT`, parentheses for
   grouping, and proximity operators such as `ADJ<n>`, `NEAR<n>`, `SAME`.
3. **Wildcards:** `$` = multi-character, `?` = single character. Example: `lithium$.TI.`
4. **Exact phrases** go in double quotes _before_ the alias: `"solid state battery".TI.`
5. **Date filters:** Always use full `YYYYMMDD`. Wildcards like `2024?.PD.` trigger
   “Invalid date” errors. Prefer explicit ranges via `@PD>=...<=...` or post-filter results.
6. **Sort parameter quirks:** PPUBS intermittently returns HTTP 500 when custom `sort`
   strings are supplied via the API. Allow the default ordering and sort client-side instead.
7. **Pagination limits:** The API caps `limit` at 20 reliably. Iterate `start` in increments of
   20 to harvest deeper result sets.
8. **Handle error payloads:** Failures sometimes arrive as plain text (not JSON), which can break
   structured parsers. Wrap search calls to surface the underlying HTTP status message.

Official references:
• USPTO “Searchable Indexes” table (ppubs.uspto.gov/.../searchable-indexes.html)
• Patent Public Search FAQ → “How can I enter a query in Patent Public Search?”
• Internal resource: resource://uspto-publications/searchable-indexes
