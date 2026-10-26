# EUR-Lex: EU IP case law and legislation (CELLAR)

October 27, 2026. `EurlexClient` ([source](../packages/client/src/eurlex.ts))
reads CELLAR, the Publications Office repository behind EUR-Lex. It takes
metadata from the SPARQL endpoint (`publications.europa.eu/webapi/rdf/sparql`)
and documents from content negotiation on
`publications.europa.eu/resource/celex/{CELEX}`. No credentials are needed.
eur-lex.europa.eu itself answers plain requests with a bot challenge (HTTP
202); CELLAR doesn't. This connector is new; Python had none.

The [MCP adapter](../packages/mcp/src/eurlex.ts) adds three tools under
`eurlex:read`, always registered:

| Tool | What it does |
| --- | --- |
| `search_eu_ip_case_law` | Court of Justice and General Court IP case law by subject, court, document type, dates and title words, newest first |
| `get_eurlex_document` | Any document by CELEX number (judgment, order, opinion, act or consolidated version), with metadata and text; past 32,000 characters the text is an artifact |
| `list_eu_ip_legislation` | 20 core EU IP acts with title, date, in-force flag and latest consolidated version |

## Case-law search

Searches filter on CELLAR's case-law subject matters, which keeps them fast
(about 130 ms, against 19 s for a scan of titles):

| Subject | Code | Cases (October 27) |
| --- | --- | --- |
| trade marks | MARQ | 5,665 |
| designs | DEMO | 339 |
| copyright | DADV | 151 |
| patents (including SPCs) | BREV | 119 |
| intellectual property | PIIC | 88 |
| plant varieties | OBVE | 65 |

The court and document type come from the CELEX number. In `62025TJ0786`,
`T` is the General Court and `J` a judgment; `C` is the Court of Justice,
`O` an order and `C` in the second position an Advocate General's opinion.

Title words must all appear in the English title, which CELLAR writes as
heading, parties and subject keywords separated by `#`. The client splits
them apart. Words are reduced to letters and digits, and every other query
part comes from a fixed list, so no SPARQL can be injected.

## Documents

- **Formats.** Legislation usually comes as XHTML and case law as HTML;
  some have both. One request asks for `application/xhtml+xml, text/html`.
- **Redirects.** CELLAR answers 303 to a plain `http://` URL on its own
  host. The shared transport has a new `upgradeRedirects` option that
  follows such a redirect over HTTPS when it stays on an approved host.
- **Text.** It's extracted block by block, one paragraph per line, without
  scripts or styles.
- **Languages.** Any of the 24 EU languages can be requested. Some
  judgments exist only in some of them.

**Consolidated versions.** CELLAR links an act to consolidated versions of
the acts it amends, not only its own. Taking the latest link gave the GI
regulation 2023/2411 the trade mark regulation's consolidation, and the SPC
regulation its 1992 predecessor's. The client therefore accepts only
consolidations of the act itself (CELEX `0` plus the act's number). Some of
those exist only as PDF: `02016L0943-20160615` has no HTML, and fetching it
reports that.

**In force.** CELLAR's flag marks the Community Designs Regulation (6/2002)
as not in force, though it applies as amended by 2024/2822. The flag is
passed through as CELLAR records it, and the tools point to the consolidated
version for the text in force.

## Evidence

[`scripts/record-eurlex.ts`](../scripts/record-eurlex.ts) (`bun run
record:eurlex`, optionally with cassette names) records 13 cassettes:

- **Nine library calls:**
  - three searches;
  - an English and a French judgment;
  - a regulation, a consolidated version and an unknown CELEX number;
  - the legislation list.
- **Four tool calls.**

SPARQL requests are POSTs to one URL, so the cassettes match on the
request body. [Tests](../tests/eurlex.test.ts) check the filters, metadata,
consolidation matching, CELEX validation, text extraction, inline and
artifact delivery, and `eurlex:read` on the authenticated HTTP listener.
