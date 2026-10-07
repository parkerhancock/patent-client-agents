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
   Wildcards are not expanded inside double quotes: `"motion compensat$"` silently matches
   nothing. Chain the words with `ADJ` instead: `motion ADJ compensat$`.
4. **Exact phrases** go in double quotes _before_ the alias: `"solid state battery".TI.`
5. **Operators are case-insensitive.** `and`, `not`, `adj`, `same`, `with`, and the rest act as
   operators in any case, so those words can't be searched as text (quoting doesn't help).
   An operator can't start a group (except `NOT`), end one, or follow another operator.
   `search_biblio` rejects these patterns before calling PPUBS and names the token.
6. **Large wildcard expansions fail.** PPUBS answers HTTP 500 "Unable to Process" when the
   truncated terms in one query expand to too many words, especially across `SAME` or `AND`.
   It fails the same way every time, so retrying won't help. Replace some truncations with
   explicit words or split the query.
7. **Date filters:** Always use full `YYYYMMDD`. Wildcards like `2024?.PD.` trigger
   “Invalid date” errors. Prefer explicit ranges via `@PD>=...<=...` or post-filter results.
8. **Sort parameter quirks:** PPUBS intermittently returns HTTP 500 when custom `sort`
   strings are supplied via the API. Allow the default ordering and sort client-side instead.
9. **Pagination counts families.** Results are grouped by patent family, and `limit` and
   `start` count families, not documents. A 20-family page often holds 30-60 documents. The API
   caps `limit` at 20 reliably; advance `start` by the page's family count (`num_found`) until it
   reaches `num_families`. `num_documents` is the total document count.
10. **Handle error payloads:** Failures sometimes arrive as plain text (not JSON), which can break
   structured parsers. Wrap search calls to surface the underlying HTTP status message.

Official references:
• USPTO “Searchable Indexes” table (ppubs.uspto.gov/.../searchable-indexes.html)
• Patent Public Search FAQ → “How can I enter a query in Patent Public Search?”
• Internal resource: resource://uspto-publications/searchable-indexes
