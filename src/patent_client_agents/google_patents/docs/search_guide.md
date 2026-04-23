# Google Patents Search Guide

Use this reference when calling `google_patents.search`. It mirrors the filters available in the Google Patents advanced-search UI.

## Filters and how they map to query parameters

| Field | Query parameter | Notes |
| --- | --- | --- |
| `keywords` | `q` | Each entry becomes its own `q=` parameter; Boolean operators (AND/OR/NOT) and quoted phrases are supported. |
| `cpc_codes` | `cpc` | Comma-separated CPC symbols (e.g., `H04L9/32`). |
| `inventors` / `assignees` | `inventor` / `assignee` | Comma-separated names (wrap multi-word names in quotes for clarity). |
| `country_codes` | `country` | Publication country filters (two-letter codes). |
| `language_codes` | `language` | Language filters (`en`, `de`, etc.). |
| `date_type` + `filed_after` / `filed_before` | `after=<type>:YYYY-MM-DD`, `before=<type>:YYYY-MM-DD` | `date_type` defaults to `priority`; set to `filing` or `publication` as needed. Dates must be ISO formatted. |
| `status` | `status` | Google Patents status buckets (`ACTIVE`, `PENDING`, etc.). |
| `patent_type` | `type` | `PATENT`, `DESIGN`, etc. |
| `litigation` | `litigation` | Mirrors the UI’s litigation toggle (`true`/`false`). |
| `include_patents` | `patents=false` (when disabled) | Set `false` to exclude patents (NPL-only searches). |
| `include_npl` | `scholar` flag | When `true`, adds the `scholar` flag so non-patent literature is included. |
| `sort` | `sort=new` or `sort=old` | `new` sorts by newest first; `old` sorts oldest first. |
| `dups` | `dups=<value>` | Rare duplicate-grouping knob; leave unset unless you rely on it in the UI. |
| `page_size` | `num` | Defaults to 10; Google caps at 100. |
| `page` | `page=<zero-based>` | The MCP converts the 1-indexed `page` you supply into the zero-based value Google expects. |
| `cluster_results` | `clustered=true` | Matches the UI’s “group by family” toggle. |
| `local` | `local=<value>` | Advanced/undocumented flag surfaced by the Polymer bundle (rarely needed). |

## Example query strings

```
q=solid+state+battery&assignee=Toyota&after=filing:2020-01-01
cpc=H04L9/32&country=US,EP&language=en
q=blockchain&inventor=Satoshi+Nakamoto&scholar
```

## Tips

- Provide at least one keyword, CPC symbol, inventor, assignee, country, or language filter.
- Dates must be `YYYY-MM-DD`; the MCP validates them before sending the request.
- Google may return an HTML "Sorry" page if it detects too many automated queries; wait a moment or narrow the search if that happens.
- Combining textual, classification, and date filters yields the most precise result sets and reduces throttling risk.
