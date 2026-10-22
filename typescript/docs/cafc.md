# Federal Circuit opinions

October 21, 2026. `CafcClient` ([source](../packages/client/src/cafc.ts))
ports the Python `cafc` package: search over the court's opinions and orders
index, a heuristic patent-case classifier, and opinion PDF downloads.

## Source

The court publishes no API. Its opinions page
(https://www.cafc.uscourts.gov/home/case-information/opinions-orders/) is a
WordPress DataTables widget that posts to
`/wp-admin/admin-ajax.php?action=get_wdtable&table_id=1`. Each request carries
a ten-character nonce read from a hidden input on that page; no cookie is
needed. The client caches the nonce for an hour and, if WordPress answers a
stale nonce with a bare `-1` or `0`, fetches the page again once.

The index matches free text across appeal number, case name and the other
columns. Origins (`PTO`, `DCT`, `ITC`, `CFC`, `MSPB`, ...) and the release-date
range are column filters. Rows come back newest first. The client checks every
page against `recordsFiltered` and fails with `INVALID_RESPONSE` when a page is
malformed, oversized or contradicts the count, so a short result is never
mistaken for complete coverage.

Appeal numbers in the index use a two-digit year (`24-1945`). A search for the
four-digit form (`2024-1945`) finds nothing upstream, although the Python tool
descriptions offer that form. The client normalizes either form before
searching.

## Classifier

`classifyPatentCase` reproduces Python's `PatentClassifier` weights, keyword
lists, false-positive patterns and score adjustments. A
[parity fixture](../tests/fixtures/cafc/classifier-parity.json) of 426 inputs
(406 live case names and 20 crafted strings that hit every category) has
Python's verdict, score and keywords for each; the TypeScript classifier
matches all of them. It reads case names only, so it misses patent cases whose
names say nothing about patents. Of the 406 live names, six classify as patent
cases.

## MCP tools

The full toolset serves `search_cafc_opinions`, `search_cafc_patent_opinions`
and `download_cafc_pdf` under the `cafc:read` scope, with the Python parameter
names. Cursors are offsets, not snapshots. `download_cafc_pdf` accepts an
appeal number or `document_url`; when an appeal has several documents (an
order and an opinion, say) it lists their URLs instead of guessing. Only
`https://www.cafc.uscourts.gov/opinions-orders/*.pdf` URLs are fetched, and
the response must start with `%PDF-`.

The curated facade routes `search_litigation(forum='cafc')`,
`search_cafc_patent_opinions` and `download_document(source='cafc')` to the
same code. Because the facade has no `document_url` parameter,
`download_document` also accepts the opinion's PDF URL as `identifier`.

## Tests

`bun run record:cafc` records one session ([recorder](../tests/cafc-recordings.ts)):
four months of patent-origin opinions over two pages, a free-text search, a
four-digit appeal lookup and a PDF. The [tests](../tests/cafc.test.ts) replay
it offline and cover the classifier fixture, nonce refresh, request encoding,
input validation and the full-toolset tools. The live facade check
(`bun run verify:facade-live`) calls every CAFC facade route.

Browsers cannot call the court's site directly, because it sends no CORS
headers; the relay allows `www.cafc.uscourts.gov`, and the index answers
without the browser user agent and `X-Requested-With` header the client
sends directly.
