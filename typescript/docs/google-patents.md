# Google Patents

October 21, 2026. `GooglePatentsClient` ports the Python `google_patents`
connector and is the reference for scraping data out of whole HTML pages. It is
unofficial: it reads `patents.google.com/patent/{number}/en` and the site's own
JSON search backend (`/xhr/query`), so Google's markup changes break it. The
deployed facade tools never call Google Patents; this connector serves the
full tool set and browser use.

## The HTML pattern

- **One portable DOM.** `linkedom` 0.18.13, a pure-JavaScript DOM, runs the
  same parsers in Bun, Node and browsers (smoke-tested in all three). A 537 KB
  page parses in about 30 ms. Google marks data with schema.org microdata, so
  [the helpers](../packages/client/src/google-patents/dom.ts) are CSS
  `[itemprop=…]` selectors plus lxml equivalents: `text()` (own text nodes),
  `text_content()`, following-sibling and `<dt>`/`<dd>` lookup.
- **Archived pages pin the structure.** [Fixtures](../tests/fixtures/google-patents/README.md)
  store six real pages gzip-compressed and unmodified (US grant, US pre-grant,
  EP, WO, and machine-translated JP and CN), plus a not-found page and a search
  response. Tests assert specific values from them.
- **Fail loudly on drift.** A page without a recognizable title is
  `INVALID_RESPONSE`, not an empty record. Search payloads are validated with
  Zod. Fallbacks for markup changes are commented where they occur.
- **Throttling is shared state.** Google returns 503 after a few quick
  requests. One limiter per process spaces requests 4 seconds apart; after a
  503 it fails fast with `RATE_LIMITED` and a retry-after hint for 90 seconds
  instead of holding callers, and transport retries are off.

## Corrections to the Python connector

Porting against current pages found these. The Python package still has them.

| Area | Python | TypeScript |
| --- | --- | --- |
| Date filters | Sends `YYYY-MM-DD`, which Google now rejects with HTTP 500 | Sends `YYYYMMDD` |
| Not found | Looks for "Sorry, we couldn't find this patent" text; Google now returns 404, which Python retries four times | 404 is `NOT_FOUND` immediately; the old text is still recognized |
| Legal events | Reads `section[itemprop=events]`, which no longer exists, so events, and grant and expiration dates taken from them, come back empty | Also reads `dd[itemprop=events]` |
| Citation titles, abstracts, prior-art keywords | Old selectors return nothing on current pages | Fallbacks for the current markup |
| Translated claims | `structured_limitations` mixes in the original-language text | Translation only; the original stays in `original_limitations` |
| Claim dependency | Only `claim-ref` markup, so EP, JP, CN and WO claims all look independent | Falls back to the claim's words ("of claim 1", "of one or more of the preceding claims") |
| `<claim-text>` elements | Nested limitations repeat inside their parent | Each level once |
| Claim numbers | "1 ." survives when the number is its own element | Stripped |
| Non-US application numbers | Any 8+ digit number gets US serial formatting | Only US numbers |

`description_markdown` reproduces the Python markdownify output byte for byte
on the four golden descriptions (EP, US with headings and lists, US with
tables). Expiration falls back to priority date + 20 years, flagged
`expiration_estimated`, as in Python.

## Library and MCP

`getPatent` returns metadata, claims with dependencies, structured and
original-language limitations, description Markdown, figures with callouts,
citations, family, legal events and the expiration estimate in one parse;
`parsePatent` does the same for HTML already in hand. `search` builds Google's
query string; `downloadPdf` fetches from `patentimages.storage.googleapis.com`
only and checks the PDF signature.

MCP adds `search_google_patents` (cursor paging), `get_google_patent` (views:
summary, claims, description, citations, family, figures, full; up to five
numbers, fetched one at a time) and `download_google_patent_pdf`, under the
`patents:read` scope. Both Google hosts are on the browser relay allowlist.

## Verification

Live recordings on October 21, 2026: a US grant page, a translated JP page and
the 404, plus a real 503 captured while Google was throttling this machine,
which now tests the rate-limit path. [Tests](../tests/google-patents.test.ts),
[metadata tests](../tests/google-patents-metadata.test.ts) and
[Markdown tests](../tests/google-patents-markdown.test.ts) cover the parsers,
query building, normalization, the limiter, PDF checks and the MCP tools.
