# WIPO Lex legislation

October 21, 2026. `WipoLexClient` ([source](../packages/client/src/wipo-lex.ts))
ports the Python `wipo_lex` package: search and detail for the WIPO Lex
legislation collection. Treaties and judgments are not ported, as in Python.

## Source

WIPO Lex has no API. Both operations read server-rendered pages on
www.wipo.int with a plain fetch and the Python user agent; no cookie, session
or browser is needed. Pages are parsed with linkedom, so the client runs in
Bun, Node and browsers (browsers need the relay, since WIPO sends no CORS
headers).

Search is `GET /wipolex/en/legislation/results` with repeated `countryOrgs`,
`subjectMatter` and `typeOfText` keys, `keywords`, `sDate`/`eDate` and `last`.
The site returns every match in one page, together with matching treaties and
judgments. The client reads only legislation rows and checks their number
against the page's "Laws (N)" tab, so a changed layout fails with
`INVALID_RESPONSE` rather than returning a short list. When nothing but
treaties or judgments match, the laws tab is absent and the result is empty.
Broad searches are large: trade secrets alone (`subject_matter=[9]`) returns
489 current laws in a 2.9 MB page.

Detail is `GET /wipolex/en/legislation/details/{id}`. Title, jurisdiction and
summary come from the OpenGraph title and description, file links from the
anchors to `.pdf`, `.doc` and `.docx` files. An unknown ID is an HTTP 404,
reported as `NOT_FOUND`.

## Python bugs fixed here

These were found by probing the live site and the search form's own script
(`/wipolex/nestjs-public/js/search.js`) on October 21, 2026.

1. `include_historical` was inverted. The form's "Include supplemental and
   historical laws" sends `last=false` for yes and `last=true` for no (the
   default). Python sent `last=false` by default, so every search returned
   superseded versions too (eleven Canadian main patent laws instead of the
   current Patent Act). The TypeScript client sends `last=true` unless
   `include_historical` is set.
2. Dates were sent as ISO strings. The site accepts only `DD/MM/YYYY`; an ISO
   `sDate` gets a 503 "website temporarily unavailable" page. The client takes
   `YYYY-MM-DD` and converts it.
3. The site ignores the date filter whenever a jurisdiction is set (Canada's
   patent laws, the United States' laws: same count with or without dates).
   Rather than silently return undated results, the client rejects
   `start_date`/`end_date` combined with `country_codes`.
4. A search with no filter is a 404 upstream; the client asks for a filter
   instead.
5. The jurisdiction came from the last comma of `og:title`, so the Hong Kong
   Patents Ordinance read as title "Patents Ordinance, Hong Kong" and
   jurisdiction "China". The client takes the jurisdiction from the start of
   the description ("Hong Kong, China - Year of Version: ...") when the title
   ends with it, and falls back to the Python split otherwise.

Attachment URLs are CloudFront links signed for five minutes from page
retrieval; the bare path redirects to the detail page. Python returned them
without saying so. Each file now carries `expires_at` (from the `Expires`
parameter), and the tool description tells agents to fetch the entry again for
fresh links. File types are decided by the URL path's extension rather than a
substring anywhere in the URL.

## MCP tools

The full toolset serves `search_wipo_lex_legislation` and
`get_wipo_lex_legislation` under the `wipo:read` scope; the curated facade
serves the same two tools under `tools:read`, with the Python parameter names.
Search returns lean stubs (`legislation_id`, `title`, `url`), the same as the
`full=true` row, as in Python. Its summary also says whether historical texts
are included. Get accepts one ID or up to 50, fetched five at a time in input
order; a missing single ID is an error, and missing list members are named in
`not_found`. IDs must be numeric.

Python's `resource://wipo_lex/usage` is a library helper that no MCP server
registers, so it is not ported.

## Tests

`bun run record:wipo-lex` records one session ([recorder](../tests/wipo-lex-recordings.ts)):
current and historical Canadian main patent laws, trade-secret laws dated
2020, the Canadian Patent Act and a nonexistent ID. Link signatures in the
cassette read `REDACTED`. Archived pages in
[fixtures](../tests/fixtures/wipo-lex/README.md) cover a treaties-only page, an
empty page and the Hong Kong ordinance. The [client tests](../tests/wipo-lex.test.ts)
replay the session offline and cover parsing, loud failures, request encoding,
input validation and the full-toolset tools; the
[facade tests](../tests/facade-wipo-lex.test.ts) route both facade tools to a
synthetic site built from the fixtures.

Live check on October 21, 2026: through the curated server, United Kingdom
enforcement laws returned 76 current texts, a three-ID get returned two
entries and named the nonexistent one in `not_found`, and trade secrets
returned 489 laws.
