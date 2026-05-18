# US/USCO — wave file (2026-05-18 priority-1 shipped)

Distillation note for the **U.S. Copyright Office** (a service unit of
the Library of Congress) backing the synopsis at
[`research/national/us-usco.md`](../../national/us-usco.md). This is a
writeup-only sweep — the connector is already shipped as
[`patent_client_agents.copyright`](../../../src/patent_client_agents/copyright/).
Goal: capture the operational truth into the atlas drawer so a future
builder doesn't have to re-read the source.

Right covered: **copyright** (registration + recordation register, plus
periodic bulk data dumps).

---

## 1. Endpoint

- **Public Records System (PRS) search API:**
  `https://api.publicrecords.copyright.gov/search_service_external/simple_search_dsl`
  (verified in [`copyright/client.py`](../../../src/patent_client_agents/copyright/client.py)
  line 44).
  Backs the consumer-facing
  [publicrecords.copyright.gov](https://publicrecords.copyright.gov/) UI.
  No published OpenAPI spec; endpoint is undocumented but stable.
- **Bulk data:** [copyright.gov/data](https://www.copyright.gov/data/) —
  periodic register and recordation dumps. Static files, not a query
  API.
- **eCO** (filing portal at [eco.copyright.gov](https://eco.copyright.gov/))
  is out of scope — write surface, not read.

## 2. Auth

**None.** The PRS endpoint is anonymous-public. Connector ships no
auth-related env vars and the test suite at
[`tests/copyright/test_client.py`](../../../tests/copyright/test_client.py)
exercises it with no credentials. Public records under
[17 USC § 705](https://www.govinfo.gov/link/uscode/17/705).

## 3. Query language

GET-only with `field_type` switch:
`keyword` (all fields), `title`, `name`. Plus `page_number`,
`records_per_page`, `sort_order`. No DSL, no boolean operators in the
documented param set — keyword text only. Convenience wrappers
`search_by_title` and `search_by_name` expose the field switch as named
methods.

## 4. Pagination

Numeric `page_number` (1-based) + `records_per_page` (default 10, no
documented ceiling). Response metadata carries `hit_count` +
`hit_count_relation` (`eq` or estimated). Facet histogram is returned
in the same envelope (filtered + unfiltered slots) for client-side
refinement.

## 5. Response shape

JSON envelope with three top-level keys:

- `metadata` — `took_ms`, `hit_count`, `max_score`, query echo, plus a
  `histogram.filtered` map with six facet buckets (`type_of_record`,
  `type_of_work`, `registration_class`, `registration_status`,
  `system_of_origin`, `recordation_item_type`).
- `data[]` — each item is `{score, hit}`. `hit` is the record body.
- Record body carries `public_records_id`, `registration_number[]`,
  `copyright_number_for_display`, `type_of_record`
  (`registration` | `recordation`), `registration_status`
  (`published` | `unpublished`), `registration_class[]`, `claimant[]`
  + structured `claimants[]`, `publisher_name[]`, `type_of_work`,
  `system_of_origin` (`voyager` post-1978; `card_catalog` pre-1978),
  multiple date fields, and `link_to_image_url[]` for digitized cards.

**Gotcha (encoded in the connector):** the API returns scalar strings
for fields typed as `list[str]` on some rows — SR-prefix sound-recording
registrations are the canonical example. The
[`_coerce_to_list`](../../../src/patent_client_agents/copyright/models.py)
field validator wraps scalars into single-element lists; without this,
Pydantic rejects whole rows of older sound-recording data. Future
builders should preserve this coercer.

## 6. Coverage scope

- **Post-1978 register:** complete in the `voyager` system.
- **Pre-1978 register:** **partial** via the digitized Card Catalog;
  `link_to_image_url` points at the Library of Congress tile server for
  scanned cards. Many pre-1978 records remain paper-only at the
  Copyright Office Records Research and Certification Section (see
  [Circular 22](https://www.copyright.gov/circs/circ22.pdf) and
  [Circular 23](https://www.copyright.gov/circs/circ23.pdf) on
  staff-mediated searches).
- **Recordations (assignments, security interests, terminations):**
  surfaced alongside registrations; facet `type_of_record` splits the
  two.

## 7. Rate limits / quotas

Undocumented. No published throttle on PRS. Connector defaults to
30-second timeout and runs under the standard
[`law_tools_core`](../../../src/law_tools_core/) retry + cache stack
(hishel + tenacity). No rate-limit response seen in the test cassettes.

## 8. Terms of service

Public-records statute: [17 USC § 705](https://www.govinfo.gov/link/uscode/17/705)
makes the register a public record. The PRS portal carries standard
government-records terms ([publicrecords.copyright.gov](https://publicrecords.copyright.gov/)).
No primary source found that prohibits programmatic access.

## 9. Operational notes

- **HTTP/2 is mandatory.** The server rejects HTTP/1.1 requests with a
  500 error. The connector sets `HTTP2: bool = True` on the class
  (see [`client.py`](../../../src/patent_client_agents/copyright/client.py)
  line 47). Any reimplementation must use an HTTP/2 client. This is the
  single most-important operational fact about this connector.
- **Browser-style `Accept` header required.** The connector sets
  `Accept: application/json, text/plain, */*` explicitly — httpx's
  default `*/*` happens to work too, but the explicit value documents
  intent and survives any future server tightening.
- **No detail endpoint.** `get_record(public_records_id)` re-searches
  by the keyword field and filters client-side. If volume grows, this
  is a place to lobby USCO for a proper `/record/{id}` shape during
  the [ECS](https://www.copyright.gov/copyright-modernization/) rollout.
- **ECS migration is the ambient risk.** USCO has been modernizing its
  systems under the [Copyright Modernization](https://www.copyright.gov/copyright-modernization/)
  program for several years. PRS is the current public-search system;
  the broader ECS rollout could change the API surface. Re-verify
  endpoint stability against [USCO NewsNet](https://www.copyright.gov/newsnet/)
  release notes.

## 10. Rating

**Rating: 🟢 green — shipped, operational, free.**

PRS is anonymous, well-shaped (faceted JSON), and stable enough to
ship without BYOK. The HTTP/2 requirement is a real but trivial
implementation detail. The §411/§412 statutory-damages link makes this
register **strategically load-bearing** for U.S. copyright litigation
diligence — agents that screen U.S. copyright enforcement readiness
need to hit this surface.

Manifest fact (`coverage/sources.yaml` row `US/USCO/Registrations`):
`rights: [copyright]`, `data_types: [bibliographic, assignments,
legal_status]`, `access.method: rest_api`, `access.auth: none`,
`status: active`, `connector.module: patent_client_agents.copyright`,
`category: registered_ip`, `transport: mcp_proxy`. Synopsis matches the
manifest with no drift.

---

## Sources (primary)

- [Public Records System portal](https://publicrecords.copyright.gov/)
- [copyright.gov main site](https://www.copyright.gov/)
- [copyright.gov/data — bulk](https://www.copyright.gov/data/)
- [Copyright Modernization / ECS](https://www.copyright.gov/copyright-modernization/)
- [17 USC on govinfo](https://www.govinfo.gov/app/collection/uscode/title17)
- [37 CFR Part 201 on eCFR](https://www.ecfr.gov/current/title-37/chapter-II/subchapter-A/part-201)
- [Compendium (Third Edition)](https://www.copyright.gov/comp3/)
- Connector: [`patent_client_agents.copyright`](../../../src/patent_client_agents/copyright/)
- Tests: [`tests/copyright/test_client.py`](../../../tests/copyright/test_client.py)
