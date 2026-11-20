# Israeli trade-mark and patent registers (data.gov.il datastore)

October 27, 2026. `IlpoRegisterClient`
([source](../packages/client/src/ilpo-register.ts)) searches Israel's
trade-mark and patent registers in place. The Ministry of Justice
republishes them daily on data.gov.il, and CKAN's `datastore_search` answers
queries over every row without a download or a key. This connector is new:
Python only listed the files, through `list_ilpo_tm_releases`
([bulk register catalogs](ckan-catalogs.md)). The research notes rate
Israel's register "no API" because of the anti-automation front end at
trademarks.justice.gov.il, which this route doesn't touch.

The [MCP adapter](../packages/mcp/src/ilpo-register.ts) adds four tools under
`ilpo:read`, always registered:

| Tool | What it does |
| --- | --- |
| `search_ilpo_trademarks` | Words in the mark, owner name words, Nice class, status, route (national, Madrid, Madrid basis) |
| `get_ilpo_trademark` | Up to 50 marks, each with its priority claims, parties, change log, foreign registrations and conditions |
| `search_ilpo_patents` | Title words with status, or applicant name words, or IPC class prefix |
| `get_ilpo_patent` | Up to 50 applications, each with applicants, inventors and IPC classes |

## The ten tables

| Table | Rows (October 27) | Joined by |
| --- | --- | --- |
| trade marks | 363,800 | mark number |
| trade-mark priority claims | 149,214 | mark number |
| trade-mark change log | 1,703,997 | mark number |
| trade-mark holders and licensees | 381,210 | mark number |
| trade marks based on foreign registrations | 11,690 | mark number |
| trade-mark conditions and disclaimers | 124,938 | mark number |
| patent applications | 286,234 | application number |
| patent applicants | 288,950 | application number |
| patent inventors | 158,441 | application number |
| patent IPC classes | 791,200 | application number |

`ILPO_TABLES` pins each table's CKAN resource id and maps its Hebrew columns
to English keys, such as מספר הסימן to `mark_number`. The ids have been
stable across the daily refreshes. If the ministry replaces a resource,
requests fail with a datastore error rather than returning wrong data.

## Search behavior

- **Prefix word search.** Plain full-text search misses English words in
  patent titles: "battery" finds nothing, while Hebrew works. Prefix queries
  (`word:*`, sent with `plain=false`) find them; "graphene" matches 90
  applications. The client builds every word search that way. It keeps only
  letters and digits, so no query syntax passes through.
- **Choosing the column.** Bilingual columns are searched in the language
  of the query's script: Hebrew text searches the Hebrew column, anything
  else the English one.
- **Nice classes.** These are stored as tokens ("32; 33") and matched
  whole, so class 3 doesn't match 32.
- **Applicant and IPC searches.** These run over their own tables, whose
  matches are rows, so one application can appear under several applicants
  or classes. Each row carries the application's register record, and the
  matching row sits under `match`. They don't combine with title words or
  status, because the datastore can't join tables.
- **Filters** are exact, and an array matches any of its values.
  `get_ilpo_trademark` and `get_ilpo_patent` fetch each related table in one
  request for the whole list.

## Normalization

- **Dates:** `DD/MM/YYYY` becomes ISO. The `01/01/1900` placeholder becomes
  null.
- **Flags:** כן/לא (yes/no) become booleans, as does ראשי (main) on IPC
  classes.
- **Statuses** stay in Hebrew under `status`, with `status_en` added. The
  English renderings are ours, not the office's; פקיעת תוקף is given as
  "lapsed" and פג תוקף as "expired". The tools accept either language.
  Trade marks have 9 statuses and patents 10.
- **Tildes:** the export writes `~` where CSV quoting would need a
  character. That's the gershayim of Hebrew abbreviations (`בע~מ` for בע"מ,
  `ד~ר` for ד"ר) and the commas of goods lists (`software~ computers`), and
  the client restores both.
- **PCT publication numbers** are exported without their WO prefix
  (`/2013/119295`), and the client adds it.
- **Lean trade-mark rows** drop the customs-enforcement contact columns
  (representative, email, phone, address date) and the extract link, which
  is the same site root on every row. Pass `full` to keep them.

The data is as the register publishes it. Two quirks to know about:

- Inventor rows exist for about half the applications.
- Some second-publication dates precede the first.

## Evidence

[`scripts/record-ilpo-register.ts`](../scripts/record-ilpo-register.ts)
(`bun run record:ilpo-register`) records 13 cassettes:

- **Six library queries:** word, whole-token and exact searches, a prefix
  and an English title search, and an IPC join.
- **Seven tool calls:** a Hebrew owner search, a trade-mark list with an
  unknown number, a granted-patent search, applicant and IPC searches, and a
  patent list with an unknown number.

[Tests](../tests/ilpo-register.test.ts) check the recorded results,
normalization, query construction (unknown columns refused, syntax
stripped), the tools' joins and `not_found` lists, and `ilpo:read` on the
authenticated HTTP listener.
