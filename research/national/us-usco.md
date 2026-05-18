# USCO United States (US) — national (copyright)

**Layer:** national
**Jurisdiction:** US (WIPO ST.3: US)
**Issuing body:** United States Copyright Office (a service unit of the [Library of Congress](https://www.loc.gov/))
**Rights administered:** copyright (registration, recordation, public catalog)
**Working languages:** English
**Connector status:** **active**
**Last verified:** 2026-05-18
**Manifest entry:** [`US/USCO/Registrations`](../../coverage/sources.yaml) — `patent_client_agents.copyright`

**Detail surveys:**
- [`waves/2026-05-18-priority-1-shipped/us-usco.md`](../waves/2026-05-18-priority-1-shipped/us-usco.md) — distillation note backing this synopsis

**Higher / sibling layers covering this office transitively:**
- *None.* The Berne Convention removed copyright registration as a precondition to copyright in member states; consequently there is no WIPO-system register that aggregates national copyright registers the way Madrid does for trademarks or Hague does for designs. The U.S. register is national-only.
- WIPO Lex carries the [U.S. Copyright Act (17 USC)](https://www.wipo.int/wipolex/en/legislation/details/15960) as a *statute text* layer, not register coverage.

---

## §1 Mission

The U.S. Copyright Office, a service unit of the [Library of Congress](https://www.loc.gov/), administers the federal copyright register established under Article I, § 8, cl. 8 of the U.S. Constitution and implemented by [17 USC](https://www.govinfo.gov/app/collection/uscode/title17) (Copyright Act of 1976, as amended). Its institutional role is set out at [copyright.gov/about](https://www.copyright.gov/about/).

The U.S. is unusual among major jurisdictions in **operating a federal copyright register at all**. The Berne Convention (to which the U.S. acceded in 1988) bars member states from making registration a condition of copyright subsistence, so most countries do not maintain a register. The U.S. retained one because it is **constitutive of remedies, not of the right**:

- [17 USC § 411(a)](https://www.govinfo.gov/link/uscode/17/411) — registration (or refusal of registration) is a prerequisite to filing an infringement suit for a U.S. work.
- [17 USC § 412](https://www.govinfo.gov/link/uscode/17/412) — statutory damages and attorneys' fees are unavailable for infringements that occur **before** registration (subject to a three-month grace window for published works).
- [17 USC §§ 504, 505](https://www.govinfo.gov/link/uscode/17/504) — what those remedies look like.

This means for U.S. copyright litigation diligence, registration date is a load-bearing fact: it determines whether statutory damages and fee-shifting are on the table. Agents asked about U.S. copyright enforcement readiness will need to hit the register; this is exactly the slice the connector covers.

## §2 What's unique here

- **The only federal copyright register** in the U.S. legal system — no state register, no private substitute carries this data with primary-source authority.
- **Type-of-record split: `registration` vs. `recordation`** — registrations cover the work; recordations cover post-registration documents (assignments, security interests, terminations) under [17 USC § 205](https://www.govinfo.gov/link/uscode/17/205). The PRS facets expose both in one query.
- **System-of-origin split: `voyager` vs. `card_catalog`** — post-1978 registrations live in the Voyager catalog; pre-1978 registrations are surfaced from the digitized Card Catalog with image links to LOC's tile server. Pre-1978 records are still partial; many remain paper-only in the [Card Catalog reading room](https://www.copyright.gov/circs/circ22.pdf).
- **Registration classes** — TX (literary), VA (visual art), PA (performing arts), SR (sound recording), SE (serial), MA (mask work), VR (vessel hull) etc. Cataloged as facets on every search response.
- **Claimant chains** — original claimant + transferee chain via recordations is the structured paper trail for U.S. copyright ownership disputes.

## §3 Programmatic surfaces

### Public Records System (PRS) — search API

| Field | Value |
|---|---|
| Endpoint | `https://api.publicrecords.copyright.gov/search_service_external/simple_search_dsl` |
| Auth | none |
| Format | JSON |
| Protocol | **HTTP/2 required** — HTTP/1.1 is rejected with `500` at the server |
| Rate limit | undocumented; no published throttle |
| ToS posture | Public records under [17 USC § 705](https://www.govinfo.gov/link/uscode/17/705); the [Public Records System UI ToS](https://publicrecords.copyright.gov/) carries standard government-records language |
| Rating (zero-infra proxy) | 🟢 **Green** — operational |
| Primary source | [Public Records System portal](https://publicrecords.copyright.gov/) |

Backs the consumer-facing [publicrecords.copyright.gov](https://publicrecords.copyright.gov/) UI. The endpoint is undocumented at the API level but stable — our connector has been tracking it since the PRS launch. Query parameters: `query`, `field_type` (`keyword` | `title` | `name`), `page_number`, `records_per_page`, `sort_order`. Faceted results include type-of-record, type-of-work, registration class, status, system-of-origin, and recordation-item-type histograms.

### Bulk data — copyright.gov/data

| Field | Value |
|---|---|
| Endpoint | [copyright.gov/data](https://www.copyright.gov/data/) |
| Auth | none |
| Format | various — typically pipe-delimited / fixed-width per dataset README |
| Rating | 🟡 **Yellow** — exists, but bulk-shape; not a query API |
| Primary source | [copyright.gov/data](https://www.copyright.gov/data/) |

Periodic register and recordation dumps suitable for offline indexing. The shape is bulk, not query, so it does not fit the zero-infra-proxy posture — covered as a downloadable artifact, not exposed as a live tool.

### eCO — electronic registration filing portal

| Field | Value |
|---|---|
| Endpoint | [eco.copyright.gov](https://eco.copyright.gov/) |
| Auth | account-based (filer-only) |
| Rating | 🔴 **Red** — out of scope; this is the filing portal, not a read API |
| Primary source | [eCO help](https://www.copyright.gov/eco/) |

For completeness only. Filing infrastructure, not a register read surface.

## §4 Fees

**Policy: link only.** USCO charges fees in USD across three principal categories: **registration** (electronic and paper, per [Circular 4](https://www.copyright.gov/circs/circ04.pdf)), **recordation** of transfers and other documents (per [Circular 12](https://www.copyright.gov/circs/circ12.pdf)), and **search & certification services** for register lookups performed by the office on demand.

- **Official schedule:** [Copyright Office fee schedule](https://www.copyright.gov/about/fees.html)
- **Statutory basis:** [17 USC § 708](https://www.govinfo.gov/link/uscode/17/708) (fee-setting authority); [37 CFR Part 201.3](https://www.ecfr.gov/current/title-37/chapter-II/subchapter-A/part-201/section-201.3) (current fee table by regulation).
- **Rate adjustment notices:** [Federal Register search — Copyright Office fee rules](https://www.federalregister.gov/agencies/copyright-office-library-of-congress).

The PRS API itself is **free** to query; the paid fee categories above relate to filing acts (registering, recording documents) and to staff-mediated search/certification services, not to programmatic register access.

## §5 Connector strategy

### What we cover today

[`patent_client_agents.copyright`](../../src/patent_client_agents/copyright/) — async client over the PRS `simple_search_dsl` endpoint. Surface is intentionally narrow:

- `search(query, field=…)` — generic search; `field` ∈ `{keyword, title, name}`
- `search_by_title(title)` / `search_by_name(name)` — convenience wrappers
- `get_record(public_records_id)` — fetch a specific record by its PRS ID (re-searches under the hood; the upstream API has no dedicated detail endpoint)

Response shape exposes the full record envelope: registration number(s), class, status, claimants (raw + structured), publisher, work type, system-of-origin, key dates, plus the facet histogram for query refinement. The scalar-vs-list coercer in the model layer handles SR-prefix sound-recording rows that return a single-element value where the schema expects a list.

Manifest row: `US/USCO/Registrations`, `access: rest_api`, `auth: none`, `category: registered_ip`, `transport: mcp_proxy`.

### What we could add

- **Recordation-side detail expansion** — recordations carry document text and reel/frame analogs that aren't fully decoded into the model today. The PRS search response carries the keys; a dedicated `get_recordation` shape could surface document images and the recorded-party chain.
- **Card Catalog image fetch** — `link_to_image_url` is populated for pre-1978 hits. A thin image-fetch surface (LOC tile server) would let agents render the digitized card without a separate scraping step.
- **Bulk data catalog connector** — Shape E catalog over [copyright.gov/data](https://www.copyright.gov/data/) (analogous to USPTO Bulk Data). Low priority — the live API covers most agent use cases.

### What we should NOT add

- **eCO filing automation** — filing portal, not a register API; out of scope for a read-only proxy.
- **Pre-1978 paper records that aren't in the Card Catalog digitization** — those are physically held in DC and require Office staff search via the paid certification service. Not a programmatic surface in any sense.

### Next steps

1. Watch the [ECS (Enterprise Copyright System) modernization program](https://www.copyright.gov/copyright-modernization/) — USCO has been migrating public-facing systems for several years; PRS is the current public-search system but the broader ECS rollout could change the API contract. Re-verify endpoint behavior on each major ECS release note.
2. Reconsider the bulk-data Shape E connector if user demand emerges for full-corpus copyright analysis.

## §6 Open questions

- **ECS migration status as of 2026-05-18** — the [Copyright Modernization](https://www.copyright.gov/copyright-modernization/) hub lists in-progress workstreams; whether ECS will change the `api.publicrecords.copyright.gov` contract or merely the front-end is not yet specified in any Federal Register notice we've found. Next action: subscribe to [USCO NewsNet](https://www.copyright.gov/newsnet/) and re-verify connector against the next ECS release.
- **PRS rate-limit ceiling** — no published throttle; aggressive volume could trip a rate-limit response we haven't seen. Next action: instrument retry metrics and surface limit responses if encountered.
- **Pre-1978 backfile completeness** — Card Catalog digitization is ongoing; primary-source coverage map is not published. Next action: file a USCO records inquiry if a specific pre-1978 gap blocks a deal.

## §7 References

Primary sources only.

**APIs / portals:**
- [Public Records System](https://publicrecords.copyright.gov/) — the public-facing UI over the PRS API
- [copyright.gov/data](https://www.copyright.gov/data/) — bulk datasets
- [eCO](https://eco.copyright.gov/) — electronic filing portal (out of scope)
- [Copyright Modernization](https://www.copyright.gov/copyright-modernization/) — ECS rollout hub

**Statutory + regulatory:**
- [17 USC (Copyright Act)](https://www.govinfo.gov/app/collection/uscode/title17) — on govinfo
- [17 USC § 411](https://www.govinfo.gov/link/uscode/17/411) — registration as litigation prerequisite
- [17 USC § 412](https://www.govinfo.gov/link/uscode/17/412) — statutory damages and fees gate
- [17 USC § 205](https://www.govinfo.gov/link/uscode/17/205) — recordation of transfers
- [17 USC § 705](https://www.govinfo.gov/link/uscode/17/705) — registers as public records
- [17 USC § 708](https://www.govinfo.gov/link/uscode/17/708) — fee-setting authority
- [37 CFR Part 201](https://www.ecfr.gov/current/title-37/chapter-II/subchapter-A/part-201) — Copyright Office regulations

**Office guidance:**
- [Compendium of U.S. Copyright Office Practices (Third Edition)](https://www.copyright.gov/comp3/) — the registration manual
- [Circular 1 — Copyright Basics](https://www.copyright.gov/circs/circ01.pdf)
- [Circular 4 — Copyright Fees](https://www.copyright.gov/circs/circ04.pdf)
- [Circular 12 — Recordation of Transfers](https://www.copyright.gov/circs/circ12.pdf)
- [Circular 22 — How to Investigate the Copyright Status of a Work](https://www.copyright.gov/circs/circ22.pdf)

**Fee + adjustment:**
- [Fee schedule](https://www.copyright.gov/about/fees.html)
- [Federal Register — Copyright Office](https://www.federalregister.gov/agencies/copyright-office-library-of-congress) (fee rulemaking notices)

**Connector:**
- [`patent_client_agents.copyright`](../../src/patent_client_agents/copyright/) — async client + models

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Documented HTTP/2 requirement at the PRS endpoint, the registration / recordation split, the pre-1978 Card Catalog backfile shape, and the §411/§412 strategic-damages link that makes the register load-bearing for U.S. copyright litigation diligence. Flagged ECS migration as the principal open question. | Connector source + primary sources above |
