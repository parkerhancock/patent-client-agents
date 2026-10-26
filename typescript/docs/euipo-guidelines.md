# EUIPO Guidelines

October 27, 2026. `EuipoGuidelinesClient`
([source](../packages/client/src/euipo-guidelines.ts)) reads the EUIPO's
Guidelines for examination: trade marks, registered Community designs, and
geographical indications for craft and industrial products. This connector
is new; Python had none.

The [MCP adapter](../packages/mcp/src/euipo-guidelines.ts) adds
`search_euipo_guidelines`, `browse_euipo_guidelines` and
`get_euipo_guidelines_page` under `euipo:read`, always registered.

## API

guidelines.euipo.europa.eu is an SDL Dynamic Documentation site. Its
browser app reads a JSON API that needs no credentials. The endpoints came
from the app's bundle; none is documented.

| Endpoint | Client method |
| --- | --- |
| `GET /api/publications`: every edition and language | `listPublications`, `publication` |
| `POST /api/search` with `PublicationId`, `Language`, `SearchQuery`, `SearchScopeObjects`, `StartIndex`, `Count` | `search` |
| `GET /api/toc/{publication}/{node}`: contents under a node | `contents` |
| `GET /api/page/{publication}/{page}`: one page's HTML and metadata | `getPage` |

What the recordings established:

- **Each language of each edition is its own publication**, with its own
  page ids. There are 357: 166 trade mark, 167 design and 24 craft GI,
  covering editions from 2017 to 2026. The client picks the latest edition
  in force for the guidelines and language asked for, or the edition named
  ("2023", "Legislative Reform I").
- **The contents root is `t1`.** The API answers an empty node id with a
  wrapper around `t1`, and rejects "root" and bare numbers.
- **Pages link their parent and children** in a related-links block. The
  client lifts those out as structured links and drops the block from the
  text. A section page often holds only its title.
- **Search scopes by part.** Trade mark parts are letters (A to E, M).
  Design parts are "EXA RCD" (examination of applications) and "INV RCD"
  (invalidity) plus the shared trade mark parts A, B and E. Common words
  such as "the" match nothing.
- **Search hits carry two titles.** `FTITLE` is the English logical title;
  `rawlanguagetitle` is the publication's own language, which the client
  prefers.
- **A missing page is HTTP 404** with a message, raised as `NOT_FOUND`.

## Evidence

[`scripts/record-euipo-guidelines.ts`](../scripts/record-euipo-guidelines.ts)
(`bun run record:euipo-guidelines`) records fifteen cassettes:

- **Twelve library calls:** the publication list, five searches (default,
  by part, designs by part, German, the 2023 design edition), three contents
  listings (root, Part A, craft GI) and three pages (a leaf, a section, a
  missing id).
- **Three tool calls.**

The publication list is 240 KB, so it's kept whole only in its own
cassette; the others keep its English and German entries. Search hits keep
only the five metadata fields the client reads; the rest is publishing
bookkeeping, and its DITA map GUIDs trip gitleaks' generic key rule. [Tests](../tests/euipo-guidelines.test.ts)
also check input validation and `euipo:read` on the authenticated HTTP
listener.
