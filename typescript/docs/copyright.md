# U.S. Copyright Office public records

October 21, 2026. `CopyrightClient` ([source](../packages/client/src/copyright.ts))
ports the Python `copyright` package: keyword, title and name search over
copyright registrations and recorded documents, and lookup of one record by
its Public Records id.

## Source

The office's public records site (https://publicrecords.copyright.gov) runs on
an undocumented JSON API. Every operation is one GET to
`https://api.publicrecords.copyright.gov/search_service_external/simple_search_dsl`
with `query`, `field_type` (`keyword`, `title` or `name`), `page_number`,
`records_per_page`, `sort_order` and an empty `model`. No key or cookie is
needed. There is no detail endpoint, so `getRecord` searches for the id and
keeps only an exact `public_records_id` match.

The Python docstrings say the server requires HTTP/2 and rejects HTTP/1.1
with a 500. That is not true now. On October 21, `curl --http1.1`, Bun 1.4.3
fetch and Node 24.13 fetch (both HTTP/1.1) all got HTTP 200 with the same
body as `curl --http2`, for several queries. The API does answer 500 to an
empty query, a page size of 0 or above 500, and any page past the
50,000-hit window, which may be what was seen. The client therefore uses the
shared Ky transport with no HTTP/2 dependency, and rejects those inputs before
sending them, so the transport does not retry a 500 that cannot succeed.

The API sends CORS headers only for `https://publicrecords.copyright.gov`,
so browsers cannot call it directly. `api.publicrecords.copyright.gov` is not
yet in the relay's `RELAY_HOSTS`; add it there to serve browsers.

## Record families

A search mixes four kinds of record with different shapes:

| `system_of_origin` | Records | Shape |
| --- | --- | --- |
| `card_catalog` | Pre-1978 registrations digitized from catalog cards | `title_of_work`, `claimant`, `claimants` and `registration_class` lists, card image URLs |
| `voyager`, `siebel` | Registrations since 1978 | `title_concatenated`, `claimants_list`, scalar `registration_number` and `registration_class` |
| `voyager`, `rmm_voyager` | Recorded documents (assignments, transfers) | `title_concatenated`, `party_1`/`party_2`, `recordation_*`, child `list_of_titles` |

The Python model reads only the card-catalog field names. For every
registration since 1978 and every recordation, its records (and so its lean
stubs) have no title or claimant; a live Python search for "Steamboat Willie"
returns `title_of_work: []` and `claimant: []` on all three top hits. The
TypeScript client fills the Python record fields for every family: titles fall
back to `title_concatenated`, claimants to `claimants_list`, scalar numbers and
classes become one-element lists, and card-catalog `cc_type_of_work` fills
`type_of_work`. All other upstream fields are kept as returned. Recordations
have no claimant or class; their parties are in `party_1` and `party_2`.

`hit_count` never exceeds 50,000 although `hit_count_relation` stays `eq`
(the facet counts for "Walt Disney" sum to 56,998). Python reports such a
result as exactly 50,000 hits. The client sets `hit_count_capped`, and the
tool summary says "at least 50000" and that only the first 50,000 can be paged.

## MCP tools

The full toolset serves `search_copyright` and `get_copyright_record` under
the `copyright:read` scope, with the Python parameter names. Lean stubs match
Python's `_stub_copyright` field for field. `full=true` on a search returns the
Python record fields plus the score, not the whole upstream hit: one
recordation with 40 child titles is about 90 KB. `get_copyright_record` takes
an id or a list of up to 50 and returns each complete upstream record, with
unmatched ids in `not_found`; a single unmatched id returns an empty list and a
"not found" summary, as in Python. Page size is capped at 100 in the tools
(Python says "max ~50" but does not enforce it). The `sort_order` parameter of
the Python client is accepted by the library but barely changes the
relevance order, so no tool exposes it. Python's `search_by_title` and
`search_by_name` wrappers are the `field` option here.

The curated facade's `copyright` tool routes `mode='search'` and `mode='get'`
to the same code.

## Tests

`bun run record:copyright` records one session ([recorder](../tests/copyright-recordings.ts)):
a keyword search (card catalog), a title search (Voyager and Siebel
registrations and recordations), a capped name search (recordations) and three
id lookups, one of them missing. The [tests](../tests/copyright.test.ts)
replay it offline and cover request parameters, input validation, malformed
responses and the full-toolset tools. [Facade tests](../tests/facade-copyright.test.ts)
route both modes through a synthetic API.
