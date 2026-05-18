# Swiss Federal Institute of Intellectual Property (CH/IPI) — Patents, Trademarks, Designs, SPC API Discovery

**Date:** 2026-05-18
**Scope:** Determine whether the **Swiss Federal Institute of Intellectual
Property** (Eidgenössisches Institut für Geistiges Eigentum / Institut Fédéral
de la Propriété Intellectuelle / IPI / IGE) exposes a public, queryable
REST/JSON/XML API that we can proxy at runtime, with zero infrastructure on
our side. Bulk dumps and HTML-only surfaces are a **red** verdict.

**TL;DR: yellow_byok.** IPI runs a real, well-documented, **XML-over-HTTPS**
data-delivery API at [`https://www.swissreg.ch/public/api/v1`](https://www.swissreg.ch/public/api/v1)
fronted by a Keycloak OIDC identity provider at
[`https://idp.ipi.ch/auth/realms/egov`](https://idp.ipi.ch/auth/realms/egov),
documented in full at
[`https://www.swissreg.ch/public/apidocs/`](https://www.swissreg.ch/public/apidocs/)
(last updated 2026-03-02). It covers **trademarks, patents, patent
publications, SPCs, and SPC publications** — but **not designs** (designs are
in the new web-client register at `database.ipi.ch` and exposed through WIPO
Designview; no datadelivery API action exists yet). The API is **free of
charge** ("electronic delivery of IP data is available free of charge to
anyone interested" —
[IPI data-delivery-api page](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api)).
The blockers for zero-infra hosted-proxy operation are two: (1) **registration
requires signing the Terms of Use PDF and mailing it to a postal address in
Bern** —
[Terms_of_Use_for_the_Delivery_of_Data.pdf](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/e/Terms_of_Use_for_the_Delivery_of_Data.pdf),
section 2 — not a self-service portal flow; (2) the ToU prohibits passing
access credentials to third parties ("It is prohibited to pass on the access
details to third parties") and limits use to the stated purpose. Quota is
generous (**2 GiB / 24-hour rolling window** of response data, 12 concurrent
requests). The right shape is **BYOK** — each user signs their own ToU, gets
their own credentials, and we accept them as env vars. This mirrors the
JPO/INPI BYOK pattern, not the IP Australia OAuth-client-credentials pattern.

---

## 1. Endpoint

IPI exposes two layered surfaces. The bulk surface is a CSV file republished
every six months. The live surface is the IPI datadelivery API.

### 1.1 IPI datadelivery API (the real REST/XML surface)

**Base host:** `https://www.swissreg.ch/public/api/v1`

**Method:** POST. The request body is an XML `ApiRequest` document. Multiple
`Action` elements may be wrapped in one `ApiRequest`. The response is either
an XML `ApiResponse` document (Accept: `application/xml`) or a ZIP bundle
(Accept: `application/zip`) containing `/response.xml` plus any images or
item facets. Source:
[Getting Started — basics](https://www.swissreg.ch/public/apidocs/getting-started/basics.html),
[Reference — Endpoints](https://www.swissreg.ch/public/apidocs/reference/requests.html).

**Documented action types** (from the single-page LLM-friendly docs at
[`/public/apidocs/singlehtml/index.html`](https://www.swissreg.ch/public/apidocs/singlehtml/index.html)):

| Action | Right | Notes |
|---|---|---|
| `TrademarkSearch` | trademark | National CH trademarks + Madrid IRs designating CH (per Swissreg DB scope, see [trade mark database help](https://www.ige.ch/en/services/digital-resources/databases-and-directories/swissreg/trade-mark-database)) |
| `PatentSearch` | patent | National CH patents + EP validations effective in CH (CH is an EPC contracting state) |
| `PatentPublicationSearch` | patent | Publication events (A1/A8/B1 etc.) — published-document slice |
| `SPCSearch` | patent (extension) | Supplementary Protection Certificates + paediatric SPCs (CH paediatric extension live since 2019-01-01, see [IPI paediatric extensions](https://www.ige.ch/en/protecting-your-ip/patents/after-your-patent-has-been-granted/the-supplementary-protection-certificate-spc/paediatric-extensions)) |
| `SPCPublicationSearch` | patent (extension) | SPC publication events |
| `UserQuota` | meta | Returns remaining quota for the calling user |
| `Echo` | meta | Diagnostic |

**No `DesignSearch` action** is documented. The IPI's data-delivery landing
explicitly says "Currently, trademark and patent data records can be
obtained via API" —
[IPI — Data delivery via API](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api).
Swiss design data is published via the Swissreg web client
([design database help page](https://www.ige.ch/en/services/digital-resources/databases-and-directories/swissreg/design-database))
and is also available through **WIPO Designview** as of 2017-11-20
([IPI news — Swiss design data now available in Designview](https://www.ige.ch/en/services/newsroom/news/news-details/swiss-design-data-now-available-in-designview)).

### 1.2 Raw patent CSV bulk

[`https://www.ige.ch/en/services/digital-resources/ip-data/patent-data`](https://www.ige.ch/en/services/digital-resources/ip-data/patent-data)
publishes CSV files containing CH publications with filing date from
1978-01-01 onwards, "updated every six months." Free, no signup required.
Distinct from the API.

### 1.3 Swissreg web client (`database.ipi.ch` / swissreg.ch UI)

[`https://www.swissreg.ch/database-client/`](https://www.swissreg.ch/database-client/)
is the public-facing register UI for trademarks, patents, designs, SPCs,
protected topographies, and protected emblems. No documented public web
endpoint for programmatic use; the datadelivery API is the supported path.

### 1.4 opendata.swiss

Probe 2026-05-18 against
[`https://opendata.swiss/api/3/action/package_search?fq=organization:eidgenoessisches-institut-fuer-geistiges-eigentum`](https://opendata.swiss/api/3/action/package_search?fq=organization:eidgenoessisches-institut-fuer-geistiges-eigentum)
returns `count: 0`. IPI **does not publish to opendata.swiss**; the only IPI
channels for programmatic data are the datadelivery API and the raw CSV
bulk. This is a noteworthy structural choice for a federal-administration
agency — most other Swiss federal bodies (BFS / Federal Statistical Office,
Swisstopo, etc.) do publish through opendata.swiss.

---

## 2. Auth

The IPI datadelivery API uses **OpenID Connect / OAuth 2.0 Resource Owner
Password Credentials grant** against a Keycloak realm.

### 2.1 Token endpoint

`POST https://idp.ipi.ch/auth/realms/egov/protocol/openid-connect/token`

Form-encoded body parameters
([Reference — Authentication](https://www.swissreg.ch/public/apidocs/reference/authentication.html)):

| Parameter | Value |
|---|---|
| `grant_type` | `password` (initial), `refresh_token` (refresh) |
| `client_id` | `datadelivery-api-client` (public constant) |
| `username` | the user's IPI Data account email |
| `password` | the user's IPI Data account password |

Response (200): JSON with `access_token` (JWT), `expires_in` (≈720 s),
`refresh_token`, `refresh_expires_in` (≈360 s). The API recommends reusing
tokens until expiry and using refresh rather than re-authenticating —
"Failing to reuse tokens appropriately may result in penalties"
([Reference — Authentication, "Get initial tokens"](https://www.swissreg.ch/public/apidocs/reference/authentication.html)).

Total session lifetime capped at **600 minutes (10 hours)** — after that, a
fresh `password` grant is required.

### 2.2 Per-call auth

Bearer JWT in `Authorization: Bearer <access_token>` header. Image and
document resources at `/public/api/v1/resources/img/...` and
`.../resources/doc/...` require the same bearer; the docs recommend
**pre-authenticating** (send the Authorization header on the initial request,
not after a redirect) to avoid round-tripping back to the IDP.

### 2.3 Registration — the friction point

This is the critical operational fact for our connector decision.

Per [IPI — Data delivery via API](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api):

> "The electronic delivery of IP data is available free of charge to
> anyone interested. The only requirement is that you first sign the Terms
> of Use. Once you have done this, please send them to the following
> address: **Swiss Federal Institute of Intellectual Property, Digital
> services and processes, Stauffacherstrasse 65/59g, 3003 Bern**"

The
[Terms of Use PDF (2024-10-31)](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/e/Terms_of_Use_for_the_Delivery_of_Data.pdf)
confirms in §2:

> "Another condition for using the online service is that you must have a
> user account. To this end, you need to register with the IPI and confirm
> that you will comply with these Terms of use by signing and returning
> them to the following address: Swiss Federal Institute of Intellectual
> Property, Contact Centre, Stauffacherstrasse 65/59g, 3003 Bern. **It is
> prohibited to pass on the access details to third parties.**"

And the API docs note ([Reference — Authentication, "Registration"](https://www.swissreg.ch/public/apidocs/reference/authentication.html)):

> "Currently, even if you plan to use the API service for other data
> domains than trade mark, please sign up for a trade mark data account.
> Usage is not restricted to trade mark data."

So the registration flow is **paper/PDF, postal mail to Bern**, not a
self-service web form. The ToU does not state a Swiss-residency or
Swiss-nationality requirement on its face — the bar is signing the
document and returning it. But the agreement is a written contract with a
Bern-jurisdiction clause (§5: Swiss law applies; disputes go to Bern
courts).

**Foreign-developer accessibility:** no primary source states a residency
requirement. The ToU is published in English. The contact email
(`datenabgabe@ipi.ch`) and phone (+41 31 377 77 77) accept international
inquiries. Realistically, a US-based developer can sign and return the
ToU and obtain credentials. The friction is the wet-signature step itself
plus the postal latency, not nationality.

---

## 3. Query language

The query language is **structured XML, document-shaped, not URL
parameters**. Searches are nested element queries with `Require`, free-text
`Any`, and domain-specific fields. Documentation at
[How-To — Building Search Queries](https://www.swissreg.ch/public/apidocs/how-to/building-queries.html).

Each right type extends `AbstractDefinedFieldsQuery` with right-specific
fields. For trademarks the namespace is
`urn:ige:schema:xsd:datadeliverytrademark-1.0.0`; for patents
`urn:ige:schema:xsd:datadeliverypatent-1.0.0`; etc. Example: filter
trademarks by `<tm:FeatureCategory>Combined</tm:FeatureCategory>` for
combined word+figurative marks. Quoted from the basics example
([Getting Started — basics](https://www.swissreg.ch/public/apidocs/getting-started/basics.html)):

```xml
<Query>
  <Require>
    <tm:FeatureCategory>Combined</tm:FeatureCategory>
  </Require>
</Query>
```

`<LastUpdate/>` matches all records that have a LastUpdate field — i.e. the
universe — and is the canonical pattern for full traversals.

Sort criteria are domain-specific elements like
`<LastUpdateSort>Ascending</LastUpdateSort>`,
`<spcpub:PublicationDateSort>Descending</spcpub:PublicationDateSort>`, etc.

XML output conforms to **WIPO ST.96** with Swiss-Interoperable-Superset
extensions ([Deep Dive — XML Schemas](https://www.swissreg.ch/public/apidocs/deep-dive/xml-schemas.html)).

---

## 4. Pagination

Cursor-style via `<Continuation>` elements. Pattern:

1. Initial request includes `<Page size="64"/>` (or any size up to the
   per-action max).
2. Response includes a `<Result>` containing a `<Continuations>` wrapper
   with one or more `<Continuation name="NextPage">...</Continuation>`
   elements.
3. To get page 2, copy the entire unmodified `<Continuation>` element into
   the next `ApiRequest`. The `name` attribute must not be altered.

The `<Meta>` block reports `<db:TotalItemCount>`, `<db:ItemCountOffset>`,
`<db:ItemCount>` (counts of the current page and the offset within the
full result set). No hard upper bound on traversal length is documented.

Worked-example XSDs:
[Getting Started — full traversal](https://www.swissreg.ch/public/apidocs/getting-started/full-traversal.html).

---

## 5. Response shape

XML, ST.96 + IPI Swiss-superset extensions. Each `Action` in the request
produces a matching `ApiResult` in the response, in document order.

A `Result` contains:

- `<Log>` — diagnostic LogEntry elements
- `<Continuations>` — pagination cursors (see §4)
- `<ResultData>` — the actual content
  - `<Meta>` — paging counts
  - `<DataBag>` — wraps result items
  - per-item: ST.96-shaped XML payload + optional `image` and `document`
    resource references

For ZIP bundles (`Accept: application/zip`), the response is `response.xml`
at the bundle root plus images/documents as separate files. The Representation
element lets the client specify `Resource action="Bundle|Link|Embed|DataURL|Skip"`
per role (item, image, document, item-facet).

A no-action request (`<ApiRequest .../>`) is the documented health-check.

Schema catalog: [https://schema.ige.ch/xml/](https://schema.ige.ch/xml/) —
`datadelivery-core-1-0-0.xsd`, `datadelivery-common-1-0-0.xsd`,
plus per-action XSDs.

---

## 6. Coverage scope

| Right | Coverage | Comments |
|---|---|---|
| **CH national trademarks** | Active + cancelled CH national TMs + Madrid IRs designating CH | The Swissreg trademark DB scope, surfaced through `TrademarkSearch` |
| **CH national patents** | Active CH national applications + grants + EP validations | CH is an EPC contracting state, and a London Agreement country — EP grants are automatically effective in CH+LI as a unitary patent territory ([Wikipedia — Unitary patent (Switzerland and Liechtenstein)](https://en.wikipedia.org/wiki/Unitary_patent_(Switzerland_and_Liechtenstein))); ground truth in the IPI register is the IPI's, not EPO INPADOC's |
| **CH SPCs + paediatric SPCs** | All registered, since the Swiss SPC regime + paediatric extension since 2019-01-01 | Unique to IPI; EPO does not register national SPCs |
| **CH designs** | NOT on the API — register UI only, plus WIPO Designview since 2017-11-20 | Gap vs. trademarks + patents |

**Backfile depth:** Raw patent CSV starts at 1978-01-01 filings
([patent-data page](https://www.ige.ch/en/services/digital-resources/ip-data/patent-data)).
The API itself does not document an explicit lower bound; trademark
backfile in the Swissreg register is "active and cancelled."

**Volume signal:** No published total record counts from primary IPI sources.
A traversal-example response in the docs shows `<db:TotalItemCount>27707</db:TotalItemCount>`
for one specific query slice ([Getting Started — full traversal, "The Meta Element"](https://www.swissreg.ch/public/apidocs/getting-started/full-traversal.html))
— that's not the universe size, it's a probe.

**Liechtenstein angle.** Under the 1978 CH-LI Patent Treaty, CH and LI form
a unified patent territory ([IPI — Unitary EU patent system page](https://www.ige.ch/en/law-and-policy/international-ip-law/ip-organisations/epo/unitary-eu-patent-system)).
A national CH patent or an EP validated in CH automatically covers LI. The
IPI register is the canonical register for both jurisdictions on the
patent side. LI trademarks and designs go through a separate Liechtenstein
Office of Economic Affairs (out of scope for this synopsis).

---

## 7. Rate limits / quotas

Documented at
[Reference — Usage Limits](https://www.swissreg.ch/public/apidocs/reference/limits.html).

| Limit | Value |
|---|---|
| Response data transfer quota | **2 GiB / user / 24-hour rolling window** |
| Concurrency | **12 simultaneous requests** per user |
| Penalty cap | **2048 penalties** then 15-minute hard cooldown |
| Penalty inflation | Each 4xx/5xx response adds a penalty; semaphore-permit release delay scales up to 15 s, concurrency scales down to 1, before the cap |
| Penalty reset | Idle for 15 minutes resets penalty count to zero |

Headers emitted on every response:
- `Ratelimit-Weight` — bytes counted against quota for this response
- `X-IPI-PENALTY` — current penalty count
- `Retry-After` — when present, the client MUST honor it (the ToU is
  explicit on this: "respect the Retry-After response headers")
- `X-IPI-SUCCESS`, `X-IPI-CONTINUATION-NAME`, `X-IPI-ACQUIRE`,
  `X-WAF-SUPPORT-ID`

Quota self-introspection: the `UserQuota` action returns the calling
user's current quota state in XML
([Reference — Special Actions, UserQuota](https://www.swissreg.ch/public/apidocs/reference/actions.html)).

ZIP bundle responses are compressed and count fewer bytes against the
quota, and images are content-addressed (same URI ⇒ same content) so
clients can cache aggressively. The docs explicitly recommend a connection
pool of 12 HTTP/1.1 keep-alive connections for concurrency-optimal
throughput.

**Verdict on quotas for a hosted shared key:** 2 GiB/day is *generous* — at
~50 KB per typical TM hit, that's ~40k responses/day, plenty for a
moderate-traffic hosted proxy. The binding constraint is not bandwidth but
the **ToU clause forbidding sharing credentials** (§2: "It is prohibited
to pass on the access details to third parties"), which forecloses a
shared-technical-account pattern even if the bandwidth were a fit.

---

## 8. Terms of service

Two stacked documents control:

1. The
   [Terms of use for the online data delivery service (2024-10-31)](https://www.ige.ch/fileadmin/user_upload/schuetzen/marken/e/Terms_of_Use_for_the_Delivery_of_Data.pdf)
   — the wet-signed account agreement.
2. The IPI
   [general Legal notice](https://www.ige.ch/en/legal-notice) — applies to
   all of `ige.ch` and is incorporated by reference in the apidocs
   ([Terms of use — General Legal Notice](https://www.swissreg.ch/public/apidocs/terms-of-use/_terms-of-use.html)).

Key clauses from the ToU (verbatim or paraphrased per §):

- **§1 Purpose.** The IPI aims to make IP information available to a wider
  public to better disseminate knowledge about IP. Use is restricted to
  this purpose.
- **§2 Access.** Wet-signed ToU + postal return required. No-self-service
  signup. **"It is prohibited to pass on the access details to third
  parties."**
- **§3 Use.** "It is specifically forbidden to use the data for mailings"
  (anti-spam clause). "If you provide third parties with some or all of
  the raw data you obtain from the online service, you must also pass on
  all rights and obligations arising from these Terms of use to these
  third parties" — i.e. the ToU runs with redistribution; you cannot
  silently re-distribute. Re-use cannot give the impression of being
  official IPI data.
- **§3 IPI rights.** "The IPI reserves the right to change, restrict or
  block access to some or all of the data at any time without providing
  reasons."
- **§5 Jurisdiction.** Bern, Swiss law.

**Proxy posture.** Strictly read: §2 forbids "passing on the access
details" but does **not** forbid offering a value-added service that
proxies the data on the user's behalf, as long as the credentials remain
with the registered party. A hosted-proxy-with-shared-credentials is
clearly off-spec. A **BYOK** model — the end user signs the ToU
themselves, gets their own credentials, and our connector reads them from
env vars — is the closest fit, since the registered party (the end user)
is the one whose credentials are being used and the obligation runs with
them.

---

## 9. Operational notes

- **Language.** API docs are English-only and high-quality (Sphinx, MyST
  markdown). The IPI website is German/French/Italian/English; the ToU is
  available in English. Internal field semantics and data are
  multilingual where applicable (TMs have DE/FR/IT/EN class headings).
- **Last-updated.** API docs page footer reads
  "Last updated on 2026-03-02" ([apidocs index](https://www.swissreg.ch/public/apidocs/)) —
  ~10 weeks old as of today (2026-05-18), the API surface is in active
  maintenance.
- **Geofencing.** No primary source documents IP-based geo-restriction on
  the endpoints. The IDP is hosted on `idp.ipi.ch` and the API on
  `swissreg.ch`; both resolve from outside Switzerland.
- **WAF.** Rejected requests get `403 Forbidden` plus an `X-WAF-SUPPORT-ID`
  token for network-admin escalation. There is a WAF in front of the
  endpoint. Not aggressively probed in this discovery.
- **Migration note.** The classic `swissreg.ch` HTML UI is being retired
  in favor of `database.ipi.ch` (the "new online registers"). Search
  results note "Swissreg has technically reached 'end of life'" — but the
  API host stays at `swissreg.ch/public/api/v1` and the apidocs at
  `swissreg.ch/public/apidocs/` are live and current. The API surface
  appears to be the long-term plan; the HTML retirement does not
  contraindicate building on it.
- **Bulk side channel.** Six-monthly CSV at
  [patent-data page](https://www.ige.ch/en/services/digital-resources/ip-data/patent-data)
  is freely downloadable, no ToU signing required for the CSV — that's a
  separate offering with a separate licensing track (the page is silent on
  redistribution licence; treat as default ige.ch legal-notice copyright).
- **opendata.swiss absence.** IPI does not publish to the federal
  open-data portal. The datadelivery API and the patent CSV are the only
  programmatic channels.
- **Designs gap.** No `DesignSearch` API action exists. CH designs are
  reachable via WIPO Designview
  ([Designview](https://www.tmdn.org/tmdsview-web/welcome) carries CH
  national designs since 2017) and the WIPO Global Design Database.
- **Penalty model is unusual.** Unlike a token-bucket rate limiter,
  IPI's design accumulates penalties for 4xx/5xx that *slow down* and
  *narrow concurrency* before triggering a hard 15-min lockout at 2048
  penalties. Clients with sloppy error handling can dig themselves into a
  hole. Adds operational risk for an unattended proxy.

---

## 10. Verdict

**🟡 Yellow — BYOK.**

The technical surface is clean, well-documented, in active maintenance,
and free. The blockers for our zero-infra hosted-proxy model are not
technical but contractual: (i) registration requires a wet signature
posted to Bern, not self-service; (ii) the ToU forbids passing access
details to third parties; (iii) the agreement runs with redistribution.
A BYOK connector — `ip_australia` template, but with user-supplied
`IPI_DATA_USERNAME` + `IPI_DATA_PASSWORD` env vars — is the fit.
Skipping CH/IPI is not warranted: the unique-here slice (CH national
trademarks not in Madrid; SPCs; the CH+LI patent territory's authoritative
register; CH-language full text) is real, and the surface is good enough
that future-us will want it once a user actually asks for CH-specific work.
Designs are a gap and remain web-UI-only or via Designview.
