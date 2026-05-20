# Instituto Mexicano de la Propiedad Industrial (MX/IMPI) — national

**Layer:** national
**Jurisdiction:** MX (WIPO ST.3: MX)
**Issuing body:** Instituto Mexicano de la Propiedad Industrial (Mexican Institute of Industrial Property, IMPI)
**Rights administered:** patent, utility model (*modelo de utilidad*), industrial design, integrated-circuit layout design (*esquema de trazado de circuitos integrados*), trademark, distinctive sign (commercial slogan / trade name), denomination of origin (*denominación de origen*), geographic indication, trade secret
**Working languages:** Spanish (primary); some institutional pages have English versions
**Connector status:** **register: skipped (red — infrastructure-level geo-block); fees: ready to build (yellow — primary-source PDF reachable)**
**Last verified:** 2026-05-19
**Manifest entry:** not yet listed (register skipped — coverage flows transitively; fees scheduled for next build wave)

**Detail surveys:**
- [`waves/2026-05-18-secondary-nationals-wave/mx-impi.md`](../waves/2026-05-18-secondary-nationals-wave/mx-impi.md) — 2026-05-18 grounded API discovery

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** (via [`regional/epo.md`](../regional/epo.md)) — MX granted patents at biblio + family + legal-events fidelity per [Espacenet INPADOC help](https://worldwide.espacenet.com/help?locale=en_ep&method=handleHelpTopic&topic=legalstatusqh) and the [IFI CLAIMS legal-status reference](https://www.ificlaims.com/docs/legal-status.htm). IMPI and EPO have a [strategic cooperation MOU for pharma-patent prosecution per Uhthoff (MX firm) summary](https://uhthoff.com.mx/en/mexican-institute-of-industrial-property-impi-and-european-patent-office-epo-strategic-cooperation-enhancing-patent-prosecution-strategies-in-mexico-in-terms-of-pharmaceutical-patents/), which underpins INPADOC currency for MX.
- **Google Patents** (via [`patent_client_agents.google_patents`](../../src/patent_client_agents/google_patents)) — MX patents and trademarks the crawl picks up; no formal partnership.
- **WIPO Madrid Monitor** — Mexico [acceded to the Madrid Protocol effective 2013-02-19 (WIPO 2025 update)](https://www.wipo.int/en/web/madrid-system/w/news/2025/madrid-system-mexico-now-providing-trademark-registration-certificates); Madrid IRs designating MX flow through Madrid Monitor.
- **Hague Express** — Mexico [acceded to the Hague System effective 2020-06-06](https://www.wipo.int/hague/en/members/); Hague IRs designating MX flow through Hague Express.
- **WIPO Patentscope (transitively via EPO OPS)** — Mexico is a [PCT contracting state since 1995-01-01](https://www.wipo.int/pct/en/pct_contracting_states.html); PCT national-phase entries into MX flow through Patentscope and INPADOC.
- **USMCA — substantive law harmonization only.** Mexico is a [USMCA party (Chapter 20 IP)](https://ustr.gov/trade-agreements/free-trade-agreements/united-states-mexico-canada-agreement/agreement-between); the LFPPI (2020) implements USMCA IP commitments. USMCA does NOT create a data-sharing arrangement with USPTO/CIPO beyond a [USPTO-IMPI PPH pilot](https://www.uspto.gov/patents/basics/international-protection/patent-prosecution-highway/patent-prosecution-3) and ongoing cooperation programs — there is no analogue to EUIPO CTI or EPO Federated Register Service routing MX data into a higher layer.

---

## §1 Mission

IMPI is Mexico's sole national IP office — the registrar for MX
national patents, MX utility models, MX industrial designs, MX
integrated-circuit layouts, MX trademarks and distinctive signs,
MX denominations of origin and geographic indications, and the
administrative enforcement venue for trade-secret claims under
the LFPPI. Mexico is a member of WIPO Madrid (since 2013), Hague
(since 2020), and PCT (since 1995), and a [USMCA party (Chapter 20
IP)](https://ustr.gov/trade-agreements/free-trade-agreements/united-states-mexico-canada-agreement/agreement-between);
the LFPPI was [published in DOF 2020-07-01 and entered into force
2021-11-05](https://www.dof.gob.mx/nota_detalle.php?codigo=5596010&fecha=01%2F07%2F2020)
to harmonize Mexican substantive law with USMCA commitments,
replacing the 1991 *Ley de la Propiedad Industrial*.

Mexico has a notable patent volume — per IMPI's [2025 press
release](https://www.gob.mx/impi/prensa/presenta-impi-en-2025-record-historico-en-patentes-concedidas-a-mexicanos-y-registra-aumento-en-registros-marcarios),
IMPI received 21,265 invention applications and granted 14,828
inventions in 2025 (a record), and received 240,991 distinctive-
sign applications. The data exists at register fidelity; the
issue is access.

**The critical access reality:** IMPI's register infrastructure
is on a Telmex IP block (`187.130.250.0/24`) that **silently
drops** TCP connections from US-egress IPs across every IMPI
subdomain except `marcia.impi.gob.mx`. This is not a ToS / auth /
WAF block; it is an infrastructure-layer geo-filter. The zero-
infra proxy posture is not feasible for IMPI without a Mexican-
egress node, which violates the zero-infra constraint.

## §2 What's unique here

These data types live ONLY at IMPI and are not covered by any
higher layer at full fidelity:

- **MX national-only patents and patent applications** — filed
  directly at IMPI, not via PCT national-phase or EP. INPADOC
  covers granted MX patents at biblio + legal-events fidelity but
  not the full national prosecution file.
- **MX utility models (*modelo de utilidad*)** — 10-year national
  right per LFPPI Title II Chapter III. INPADOC coverage is
  thinner for utility models than for patents.
- **MX industrial designs (*diseño industrial*)** — Locarno-classed
  national designs under LFPPI Title II Chapter IV. Hague IRs
  designating MX are separate.
- **MX integrated-circuit layout designs (*esquemas de trazado*)** —
  national-only sui generis right under LFPPI Title II Chapter V.
- **MX national-only trademarks** — filed at IMPI, not via Madrid.
  IMPI is the [Madrid receiving office for MX, with full Madrid
  records as of 2025-11-15](https://www.wipo.int/en/web/madrid-system/w/news/2025/madrid-system-mexico-now-providing-trademark-registration-certificates).
- **MX denominations of origin / geographical indications** —
  national-only sui generis rights administered by IMPI under
  LFPPI Title VII (Tequila, Mezcal, Talavera, etc.).
- **MX commercial slogans (*avisos comerciales*) and trade names**
  — national-only distinctive-sign categories.
- **Electronic prosecution events (PASE platform)** — the [IMPI
  electronic prosecution portal launched 2020-06-08 per Lexology
  summary](https://www.lexology.com/library/detail.aspx?g=ed50e68f-7b97-4569-8cf2-47c7bfce665e)
  for patents/utility models/designs, supplementing the [2017
  Marcanet TM e-filing system per Lexology
  summary](https://www.lexology.com/library/detail.aspx?g=2fb8e12b-f0a6-44e0-836b-960191f8197d).
- **Gaceta de la Propiedad Industrial** — IMPI's daily official
  gazette, hosted on SIGA (unreachable from US egress).
- **MX trade-secret administrative enforcement** — IMPI is the
  administrative venue under LFPPI Title IV Chapter II.

## §3 Programmatic surfaces

### MARCia (`marcia.impi.gob.mx`) — Vue.js SPA + Spring Boot JSON backend

| Field | Value |
|---|---|
| Endpoint | [`https://marcia.impi.gob.mx/marcas/search`](https://marcia.impi.gob.mx/marcas/search) (UI); backend at `/marcas/search/internal/*` |
| Auth | none (anonymous session via JSESSIONID + HS512 SESSIONTOKEN JWT + XSRF-TOKEN cookie) |
| Format | JSON (UTF-8); POST with `Content-Type: application/json;charset=UTF-8` + `X-XSRF-TOKEN` header |
| Reachable from US? | ✅ — hosted on different infrastructure than other IMPI subdomains (CSP allows `*.tmv.io` for trademark images, suggesting tmv.io / tmvapi.com CDN edge) |
| Rate limit | not published, no rate-limit headers observed on probe |
| ToS posture | no published API ToS; no Aviso legal at the SPA layer |
| Rating (zero-infra proxy) | 🟡 **Yellow** in isolation — JSON IS reachable, but covers only the TM slice (~25% of the surface) and depends on a single un-blocked IMPI host |
| Primary source | reverse-engineered from [`search.prv.se`-style](https://search.prv.se/) bundle.js analysis 2026-05-18; SPA at [`marcia.impi.gob.mx/marcas/search`](https://marcia.impi.gob.mx/marcas/search) |

Probed endpoints (2026-05-18): `GET /marcas/search/internal/counts`
→ 200 JSON `{"records": 0, "extracts": 0}`. POST endpoints to
`/result/count`, `/result`, `/record`, `/extract` exist but
require an opaque query payload schema; structured probes
returned 500. Per third-party comparison sources MARCia updates
daily (vs. legacy Marcanet's 15-30 day lag). The SPA's hardcoded
`lastIndexingDate: '02 Feb 2020'` is a default fallback string,
**not** actual data currency. Caveats: undocumented, versionless,
no published ToS, no rate-limit headers. Covers TMs only — not
patents, designs, file histories, or gazette.

### SIGA / VIDOC / Marcanet legacy / datosabiertos / patenteslibres / eservicios / PASE / ClasNiza

| Field | Value |
|---|---|
| Endpoints | [`siga.impi.gob.mx`](https://siga.impi.gob.mx/), [`vidoc.impi.gob.mx`](https://vidoc.impi.gob.mx/), [`acervomarcas.impi.gob.mx:8181/marcanet/`](https://acervomarcas.impi.gob.mx:8181/marcanet/), [`datosabiertos.impi.gob.mx`](https://datosabiertos.impi.gob.mx/), [`patenteslibres.impi.gob.mx`](https://patenteslibres.impi.gob.mx/), [`eservicios.impi.gob.mx`](https://eservicios.impi.gob.mx/), [`pase.impi.gob.mx`](https://pase.impi.gob.mx/), [`clasniza.impi.gob.mx`](https://clasniza.impi.gob.mx/) |
| Auth | unknown (likely FIEL — *Firma Electrónica Avanzada* — for PASE; none for read surfaces) |
| Format | JSF (`/newSIGA/content/common/principal.jsf`), SharePoint `.aspx`, JSP, port-8181 servlet — mixed legacy stack |
| Reachable from US? | ❌ — all resolve to Telmex `187.130.250.0/24`, packet-level TCP timeout from US egress |
| Rating (zero-infra proxy) | 🔴 **Red** — infrastructure-level geo-block, not a ToS / auth issue |
| Primary source | gob.mx search results listing all subdomains; empirical probe 2026-05-18 |

These hosts collectively cover patents, designs, the Gaceta,
classification, electronic prosecution, the bulk open-data
catalog, and the public-domain patent browser. **None of them
respond from US egress.** The block is per-subnet, packet-level
DROP — not a WAF 403, not a geofence content page. This is the
decisive blocker for any zero-infra proxy posture.

### WIPO IP API Catalog — IMPI not listed

| Field | Value |
|---|---|
| Endpoint | [`apicatalog.wipo.int`](https://apicatalog.wipo.int/) |
| Result | **0 IMPI entries** as of 2026-05-18 (179 total across DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO) |
| Rating | informational — confirms IMPI has no cataloged API in WIPO's canonical inventory |

By contrast: the WIPO catalog also lacks INPI Brazil, INAPI
Chile, SIC Colombia, INPI Argentina, and INDECOPI Peru — IMPI's
absence reflects a Latin America-wide pattern, not an IMPI-
specific shortcoming.

### datos.gob.mx federal portal — aggregated statistics only

| Field | Value |
|---|---|
| Endpoint | [`www.datos.gob.mx/organization/?q=impi`](https://www.datos.gob.mx/organization/?q=impi); historical at [`historico.datos.gob.mx/busca/dataset/informacion-estadistica-de-invenciones-...`](https://historico.datos.gob.mx/busca/dataset/informacion-estadistica-de-invenciones-signos-distintivos-y-proteccion-a-la-propiedad-intelectu) |
| Auth | none |
| Format | HTML index, CSV / XML datasets at the resource layer |
| Reachable from US? | ✅ (Akamai-fronted) |
| License | [Libre Uso MX (datos.gob.mx/libre-uso-mx)](https://datos.gob.mx/libre-uso-mx) — permissive, commercial + non-commercial reuse with attribution |
| Rating | 🔴 Red — covers only aggregated invention / distinctive-sign / IP-protection statistics, not register-level data |

The federal portal indexes IMPI's *Inventario Institucional de
Datos* metadata pointer but the actual register catalogs are on
the unreachable `datosabiertos.impi.gob.mx`.

### Substantive-law sources — reachable

| Source | URL | Reachable |
|---|---|---|
| Diario Oficial de la Federación (DOF) | [`www.dof.gob.mx`](https://www.dof.gob.mx/) | ✅ Apache PHP, 200 |
| Cámara de Diputados (statutes consolidated) | [`www.diputados.gob.mx/LeyesBiblio/`](https://www.diputados.gob.mx/LeyesBiblio/ref/lfppi.htm) | ✅ nginx, 200 |
| LFPPI canonical PDF | [`portalhcd.diputados.gob.mx/.../LFPPI_010720.pdf`](https://portalhcd.diputados.gob.mx/LeyesBiblio/pdf/LFPPI_010720.pdf) | ✅ |

These are the right citation targets for substantive Mexican IP
law and fee-schedule references.

## §4 Fees

**Status (2026-05-19):** Reachable for an MX/IMPI fees connector.
Despite the register-host geo-block documented above, the binding
tariff text is published as a single consolidated PDF on the
**gob.mx CMS attachment endpoint** (Akamai-fronted) — and that
endpoint is anonymously fetchable from US egress. The "IMPI is
geo-blocked" finding above is correct for the SIGA / VIDOC /
datosabiertos register, **not** for the tariff document. Two
parallel routes both work:

1. **gob.mx CMS attachment route (primary, used for v1 connector
   build):** [`gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf`](https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf) — 22-page consolidated *Acuerdo*, three-column layout (Artículo | Concepto | Tarifa) parsing cleanly with `pypdf`. Self-declared version stamp on page 1: *"Última reforma publicada DOF: 12-05-2023"*.
2. **DOF citation route (authoritative version pin):** [DOF nota_detalle](https://www.dof.gob.mx/) entries — searchable via the on-page Google CSE. SSL note: `dof.gob.mx` ships an incomplete cert chain; clients hitting it need a current CA bundle or `verify=False`. The 12-05-2023 publication is the consolidated base; the only post-2023 modifying *Acuerdo* found as of 2026-05-19 is [March 15, 2024 (codigo=5720420)](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024).

**Scope of the schedule (MXN-denominated, Title-organized):**

- **Title II — Patents, utility models, industrial designs, integrated-circuit layouts.** Filing, PCT national-phase entry (Chapter I / Chapter II), per-page surcharge above 30 pages, anticipated publication, prosecution / annuity, grant title issuance, divisional, recordation. Arts. 1–8 (patents proper), Arts. 9–13 (UM / design / IC).
- **Title IV — Trademarks, commercial slogans, trade names.** Per-class filing & exam through grant (Art. 14a), opposition (Art. 14b), renewal (Art. 14c), recordation (Art. 14d).
- **Title VI / VII — Denominations of origin and geographic indications.** Application, modification, authorization-to-use.
- **General concepts** — certified copies, file inspection, priority documents, gazette publication, late-filing surcharges.

**Discount tiers (mapped to `EntityTier`):**

- **Small / independent inventor (50% reduction)** — patents, utility models, designs only, per LFPPI implementing tarifa standard practice. Maps to `EntityTier.small`.
- **Décima Primera Disposición General (full waiver)** — added by [March 15, 2024 Acuerdo (codigo=5720420)](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024). Waives fees for indigenous / Afro-Mexican peoples and communities filing **collective marks** or **certification marks** tied to geographic indications under LFPPI Art. 184, covering services in Arts. 14a–14d and 15a / 15b / 15d. Requires a *constancia de pertenencia indígena*. Maps to a connector-specific `indigenous_collective` tier with note.
- **USPTO-IMPI PPH pilot** — not a fee reduction per se, but reduces total prosecution cost via accelerated examination using USPTO work products: [USPTO Patent Prosecution Highway](https://www.uspto.gov/patents/basics/international-protection/patent-prosecution-highway/patent-prosecution-3).
- **EPO-IMPI cooperation (pharma)** — strategic cooperation per [Uhthoff summary](https://uhthoff.com.mx/en/mexican-institute-of-industrial-property-impi-and-european-patent-office-epo-strategic-cooperation-enhancing-patent-prosecution-strategies-in-mexico-in-terms-of-pharmaceutical-patents/); not a tariff line.

**April 2026 LFPPI reform — tariff impact: none yet.** Mexico
amended the LFPPI on April 3, 2026 (in force April 4, 2026) —
new registrable mark types (position, motion, multimedia),
indigenous / Afro-Mexican cultural-heritage refusal grounds,
oath against bad faith on TM filings / renewals, and 5-month
TM resolution deadlines (12-month patent deadline). See [EY
Law Flash on the reform](https://www.ey.com/es_mx/technical/tax/boletines-fiscales/ey-law-flash-reforma-lfppi).
**As of 2026-05-19 no post-reform tariff *Acuerdo* has been
published in DOF**, so the 2023 PDF + 2024 amendment remain the
consolidated binding state. Worth re-checking quarterly — fee
schedules typically follow substantive reform within months.

**Statutory basis:**

- [Ley Federal de Protección a la Propiedad Industrial — Diputados (consolidated)](https://www.diputados.gob.mx/LeyesBiblio/ref/lfppi.htm) · [LFPPI PDF (portalhcd)](https://portalhcd.diputados.gob.mx/LeyesBiblio/pdf/LFPPI_010720.pdf)
- [DOF 2020-07-01 LFPPI publication (codigo=5596010)](https://www.dof.gob.mx/nota_detalle.php?codigo=5596010&fecha=01%2F07%2F2020) — published 2020-07-01, in force 2021-11-05.
- [DOF — annual *tarifas IMPI* track](https://www.dof.gob.mx/) — *Acuerdos* on the IMPI tariff are published in DOF on an as-needed basis (the canonical 1995 *Acuerdo* has been modified periodically; "Última reforma publicada DOF: 12-05-2023" is the current consolidated stamp).

**v1 connector plan — `MX/IMPI/Fees/{Patent, UtilityModel, Design, IntegratedCircuit, Trademark}`:**

- **Source:** the gob.mx CMS attachment PDF (cached locally, re-fetched weekly + content-hash-pinned).
- **Parser pattern:** IPIN India / DPMA / INPI Brazil — `pypdf` column extraction with article-code regex (`\d+\s*[a-z]( bis)?`).
- **Currency:** MXN.
- **Provenance metadata:** `version_as_of = "2023-05-12"`, `last_modifying_acuerdo = "DOF 2024-03-15 codigo=5720420"`, `freshness_max_age = 14d`.
- **Freshness probe:** weekly check of (a) the gob.mx CMS PDF hash, (b) Google CSE on `dof.gob.mx` for `"Acuerdo" "Instituto Mexicano de la Propiedad Industrial" "tarifa"` filtered to post-2024.

## §5 Connector strategy

### What we cover today

- **MX granted patents at biblio / family / legal-events fidelity** — transitively via [`patent_client_agents.epo_ops`](../regional/epo.md) (country code `MX`). INPADOC is the canonical layer.
- **MX patents and TMs (web-crawl basis)** — transitively via `patent_client_agents.google_patents`.
- **Madrid IRs designating MX** — via planned WIPO Madrid Monitor connector. Mexico [accession effective 2013-02-19](https://www.wipo.int/en/web/madrid-system/w/news/2025/madrid-system-mexico-now-providing-trademark-registration-certificates).
- **Hague IRs designating MX** — via planned WIPO Hague Express connector. Mexico [accession effective 2020-06-06](https://www.wipo.int/hague/en/members/).
- **PCT national-phase entries into MX** — transitively via Patentscope / EPO OPS. Mexico [PCT contracting state since 1995-01-01](https://www.wipo.int/pct/en/pct_contracting_states.html).

### What we should NOT add

**Skip the IMPI connector entirely.** The blocker is structural,
not effort:

- **Infrastructure-level geo-block.** All `*.impi.gob.mx` hosts
  except `marcia.impi.gob.mx` resolve to Telmex
  `187.130.250.0/24` and packet-level-drop TCP connections from
  US-egress IPs. This is not a WAF 403, not a Cloudflare
  challenge, not a "content unavailable in your country" page —
  it is a packet-level filter that a zero-infra proxy from any
  cloud egress would hit identically. Per [MEMORY:
  project_cloud_run_egress], Mexican government infrastructure
  filters cloud-egress IPs more aggressively than USPTO TESS or
  unifiedpatentcourt.org, and the IMPI filter is whole-
  subdomain DROP.
- **MARCia alone is insufficient.** Even though the JSON layer at
  `/marcas/search/internal/*` is reachable and accepts structured
  POST queries, it covers only the TM slice and depends on a
  single un-blocked IMPI host. Building a connector against ~25%
  of the surface (TMs only) while admitting that 75% (patents,
  designs, file histories, gazette, electronic prosecution) is
  permanently inaccessible is not a coherent offering. The MARCia
  payload schema is also opaque without deep SPA-bundle replay.
- **No documented REST/JSON API anywhere.** IMPI is absent from
  the WIPO IP API Catalog (179 entries, 10 IPOs, IMPI not among
  them); there is no analogue to OEPM's WSDL bundle, PRV's
  SPA-backed JSON layer, or DPMA's bulk-publication pattern.
- **No published API ToS or reuse license** for the register
  data. Mexico's federal Libre Uso MX license applies to
  datos.gob.mx-indexed datasets (which are aggregated statistics
  only), not the IMPI register catalogs on the unreachable
  `datosabiertos.impi.gob.mx`.
- **PASE electronic prosecution likely requires FIEL.** PASE is
  the entry point for register-level electronic prosecution
  events; [FIEL — Firma Electrónica Avanzada](https://www.gob.mx/sat/acciones-y-programas/firma-electronica-fiel)
  is issued by SAT (Mexican tax authority) to Mexican
  residents/nationals only, mirroring the structural foreign-
  developer block in CN/CNIPA. Unverifiable from US egress.
- **Wrapping a commercial proxy** (e.g. mxmarks.com, bonamark.com,
  marcaria.com) adds a paid intermediary without upstream
  guarantees — the consistent anti-pattern across the wave.

### Next steps

1. **Document the gap.** MX national-only file histories,
   electronic prosecution events, the Gaceta, opposition / nullity
   proceedings, and the open-data register catalog are not
   covered and cannot be covered without Mexican egress.
2. **Monitor IMPI's e-office trajectory.** Per [Lexology 2020 IMPI
   paperless track](https://www.lexology.com/library/detail.aspx?g=2fb8e12b-f0a6-44e0-836b-960191f8197d),
   IMPI is moving toward full digital operation. Quarterly check
   of [gob.mx/impi/prensa](https://www.gob.mx/impi/prensa) for an
   API or reachable-bulk-data announcement.
3. **Empirical egress test from Cloud Run.** Confirm the
   infrastructure block from production-style egress (not just
   our analysis terminal); useful precedent for future Latin-
   American national offices.
4. **If IMPI publishes a proper API,** reopen this synopsis; the
   MARCia JSON layer at `/marcas/search/internal/*` is the
   starting point for a SE/PRV-shaped connector. The TM slice is
   already the most reverse-engineerable piece.

## §6 Open questions

- **Cloud-egress empirical confirmation.** Our probes were from a
  US residential IP. Cloud Run / Cloudflare Workers egress should
  hit the same block (or worse), but worth confirming.
- **MARCia data currency vs. SPA `lastIndexingDate`.** Third
  parties say daily updates; the SPA has `02 Feb 2020` baked in.
  An empirical probe with a registered search would settle this
  — requires extracting the opaque payload schema from
  `app.91d47144.js` first.
- **PASE FIEL requirement.** The consistent practice across
  Mexican gov electronic services (SAT, IMSS, Buzón Tributario)
  is FIEL gating. Unverified for IMPI specifically because
  `pase.impi.gob.mx` is unreachable.
- **Madrid + Hague IR ingestion into MARCia.** IMPI is the Madrid
  receiving office for MX — whether MARCia surfaces Madrid IRs
  alongside national TMs, and the discriminator field, is
  unknown without payload schema.
- **WIPO ST.36 / ST.66 / ST.86 compliance.** Whether IMPI's
  unreachable bulk distributions follow WIPO standards (as OEPM,
  DPMA, INPI France do) or proprietary formats. Unverifiable.
- **INDAUTOR (copyright) and SNICS (plant varieties)** — separate
  agencies, separate scope, separate synopsis if pursued.
- **EPO INPADOC currency for MX.** EPO-IMPI cooperation suggests
  good currency for granted MX patents; empirical probe of
  recent grants would quantify the lag.
- **`pase.impi.gob.mx/api/guide/getGuide`** — only `api`-pathed
  IMPI URL surfaced in search; likely an OpenAPI help endpoint,
  not a data API. Unverifiable from US egress.

## §7 References

Primary sources only — `gob.mx`, `impi.gob.mx`, `dof.gob.mx`,
`diputados.gob.mx`, `datos.gob.mx`, `apicatalog.wipo.int`, WIPO
treaty / system pages.

**IMPI service overviews:**
- [IMPI institutional landing (gob.mx)](https://www.gob.mx/impi)
- [MARCia institutional page (gob.mx)](https://www.gob.mx/impi/acciones-y-programas/marcia-265449)
- [MARCia SPA — Búsqueda rápida](https://marcia.impi.gob.mx/marcas/search/quick) · [MARCia root](https://marcia.impi.gob.mx/)
- [SIGA — Sistema de Información de la Gaceta de la Propiedad Industrial](https://siga.impi.gob.mx/) *(unreachable from US egress)*
- [ViDoc — Visor de Documentos de Propiedad Industrial](https://vidoc.impi.gob.mx/) *(unreachable)*
- [Marcanet legacy](https://acervomarcas.impi.gob.mx:8181/marcanet/) *(unreachable)*
- [Patentes Libres — public-domain patents](https://patenteslibres.impi.gob.mx/) *(unreachable)*
- [eServicios IMPI](https://eservicios.impi.gob.mx/) *(unreachable)*
- [PASE electronic prosecution](https://pase.impi.gob.mx/) *(unreachable)*
- [ClasNiza — Nice classification](https://clasniza.impi.gob.mx/) *(unreachable)*
- [Datos Abiertos IMPI portal](https://datosabiertos.impi.gob.mx/) *(unreachable)*

**Open data + licenses (reachable):**
- [datos.gob.mx — IMPI organization page (redirected)](https://www.datos.gob.mx/organization/?q=impi)
- [historico.datos.gob.mx — IMPI statistics dataset](https://historico.datos.gob.mx/busca/dataset/informacion-estadistica-de-invenciones-signos-distintivos-y-proteccion-a-la-propiedad-intelectu)
- [Libre Uso MX license](https://datos.gob.mx/libre-uso-mx) — federal open-data license

**Substantive law (Mexican statutes via Diputados / DOF):**
- [Ley Federal de Protección a la Propiedad Industrial — Diputados (consolidated)](https://www.diputados.gob.mx/LeyesBiblio/ref/lfppi.htm)
- [LFPPI PDF — portalhcd.diputados.gob.mx](https://portalhcd.diputados.gob.mx/LeyesBiblio/pdf/LFPPI_010720.pdf)
- [LFPPI DOF publication notice — codigo=5596010, 2020-07-01](https://www.dof.gob.mx/nota_detalle.php?codigo=5596010&fecha=01%2F07%2F2020)
- [Ley General de Transparencia y Acceso a la Información Pública — DOF 2015-05-04](https://www.dof.gob.mx/nota_detalle.php?codigo=5391143&fecha=04%2F05%2F2015)
- [Diario Oficial de la Federación](https://www.dof.gob.mx/) — annual *tarifas IMPI* publication track

**International framework:**
- [WIPO Madrid system — Mexico now provides TM registration certificates (2025)](https://www.wipo.int/en/web/madrid-system/w/news/2025/madrid-system-mexico-now-providing-trademark-registration-certificates)
- [WIPO Hague system members](https://www.wipo.int/hague/en/members/) (Mexico accession 2020-06-06)
- [WIPO PCT contracting states](https://www.wipo.int/pct/en/pct_contracting_states.html) (Mexico since 1995-01-01)
- [USMCA agreement text (USTR)](https://ustr.gov/trade-agreements/free-trade-agreements/united-states-mexico-canada-agreement/agreement-between)
- [USPTO — Mexico cooperation page](https://www.uspto.gov/learning-and-resources/pursuing-international-ip-protection/mexico)
- [USPTO-IMPI Patent Prosecution Highway pilot](https://www.uspto.gov/patents/basics/international-protection/patent-prosecution-highway/patent-prosecution-3)
- [EPO-IMPI strategic cooperation — Uhthoff summary](https://uhthoff.com.mx/en/mexican-institute-of-industrial-property-impi-and-european-patent-office-epo-strategic-cooperation-enhancing-patent-prosecution-strategies-in-mexico-in-terms-of-pharmaceutical-patents/)
- [Espacenet INPADOC legal-status help](https://worldwide.espacenet.com/help?locale=en_ep&method=handleHelpTopic&topic=legalstatusqh)
- [IFI CLAIMS legal-status coverage reference](https://www.ificlaims.com/docs/legal-status.htm)

**Cross-office context:**
- [WIPO IP API Catalog](https://apicatalog.wipo.int/) — probed 2026-05-18; 0 IMPI entries (179 total across 10 IPOs)
- [PCT Applicant's Guide — Mexico](https://pctlegal.wipo.int/eGuide/view-doc.xhtml?doc-code=MX&doc-lang=en)
- [IMPI 2025 patents press release](https://www.gob.mx/impi/prensa/presenta-impi-en-2025-record-historico-en-patentes-concedidas-a-mexicanos-y-registra-aumento-en-registros-marcarios)

**Background articles (cited for context, not as primary sources):**
- [Lexology — IMPI on the way to become paperless (2020)](https://www.lexology.com/library/detail.aspx?g=2fb8e12b-f0a6-44e0-836b-960191f8197d)
- [Lexology — Electronic prosecution of patents now available (2020)](https://www.lexology.com/library/detail.aspx?g=ed50e68f-7b97-4569-8cf2-47c7bfce665e)

**Detail surveys + waves:**
- [`waves/2026-05-18-secondary-nationals-wave/mx-impi.md`](../waves/2026-05-18-secondary-nationals-wave/mx-impi.md) — 2026-05-18 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-19 | **Fees re-rated yellow (ready to build).** The original "geo-blocked" finding applies to the SIGA / VIDOC / datosabiertos register subdomains on Telmex `187.130.250.0/24`, **not** to the binding tariff document. The consolidated *Acuerdo* PDF at [gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf](https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf) is anonymously fetchable from US egress (CMS attachment route is Akamai-fronted, unlike the register hosts) and parses cleanly with `pypdf` (3-column layout, 22 pages). DOF was misdiagnosed as gated — it's actually an SSL chain issue resolved with `verify=False` or a current CA bundle. The May 2023 PDF is consolidated through "Última reforma publicada DOF: 12-05-2023"; the only post-2023 modifying *Acuerdo* found is [March 15, 2024 (codigo=5720420)](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024), which adds a *Décima Primera Disposición General* fee waiver for indigenous / Afro-Mexican peoples and communities filing collective or certification marks under LFPPI Art. 184 (Arts. 14a–14d, 15a / 15b / 15d) and changes no article-level tariff amounts. The April 3, 2026 LFPPI substantive reform has not yet triggered a post-reform tariff *Acuerdo*; needs quarterly re-check. Register-side status (red) unchanged. | This session; [Acuerdo PDF](https://www.gob.mx/cms/uploads/attachment/file/824879/Acuerdo.Tarifa.12.05.23.pdf); [DOF March 2024 amendment](https://www.dof.gob.mx/nota_detalle.php?codigo=5720420&fecha=15/03/2024); [EY April 2026 reform brief](https://www.ey.com/es_mx/technical/tax/boletines-fiscales/ey-law-flash-reforma-lfppi) |
| 2026-05-18 | Initial synopsis; rating **`red`**. Findings: (a) IMPI publishes **no documented REST/JSON API**, no analogue to OEPM's WSDL bundle, no SE/PRV-style undocumented JSON layer; (b) **0 IMPI entries** in the [WIPO IP API Catalog](https://apicatalog.wipo.int/) probed 2026-05-18 (179 total across 10 IPOs — DPMA, EPO, EUIPO, IP Australia, JPO, MOIP KOREA, QAZ, UPRP, USPTO, WIPO); (c) **the decisive blocker is infrastructure-level**: all `*.impi.gob.mx` subdomains except `marcia.impi.gob.mx` (which appears to be on `tmv.io`/`tmvapi.com` CDN edge) resolve to Telmex `187.130.250.0/24` and packet-level-drop TCP connections from US egress — this includes SIGA (gazette), VIDOC (documents), legacy Marcanet, `datosabiertos.impi.gob.mx` (open data), `patenteslibres.impi.gob.mx`, `eservicios.impi.gob.mx`, `pase.impi.gob.mx` (electronic prosecution), and `clasniza.impi.gob.mx`; (d) MARCia IS reachable and exposes a Spring Boot JSON backend at `/marcas/search/internal/*` (verified: `GET /counts` returns `{"records":0,"extracts":0}`) with anonymous session via JSESSIONID + HS512 SESSIONTOKEN JWT + XSRF-TOKEN, but covers only the TM slice and the payload schema is opaque without further SPA bundle replay; (e) Mexico is a [USMCA party](https://ustr.gov/trade-agreements/free-trade-agreements/united-states-mexico-canada-agreement/agreement-between), [Madrid acceded 2013-02-19](https://www.wipo.int/en/web/madrid-system/w/news/2025/madrid-system-mexico-now-providing-trademark-registration-certificates), [Hague acceded 2020-06-06](https://www.wipo.int/hague/en/members/), [PCT contracting state since 1995-01-01](https://www.wipo.int/pct/en/pct_contracting_states.html) — but USMCA is substantive-law harmonization only, no data-sharing arrangement; (f) the [LFPPI](https://www.diputados.gob.mx/LeyesBiblio/ref/lfppi.htm) was [published in DOF 2020-07-01, in force 2021-11-05](https://www.dof.gob.mx/nota_detalle.php?codigo=5596010&fecha=01%2F07%2F2020) and replaced the 1991 Ley de la Propiedad Industrial to implement USMCA Chapter 20 IP commitments; (g) PASE electronic prosecution likely requires SAT-issued [FIEL](https://www.gob.mx/sat/acciones-y-programas/firma-electronica-fiel) (Mexican residents/nationals only), mirroring the CN/CNIPA structural foreign-developer block — unverifiable from US egress. Connector status: **skipped (red — infrastructure-level geo-block)**. Coverage of MX flows transitively through EPO INPADOC (granted patents, biblio + family + legal events), Google Patents (web-crawl coverage of MX patents + TMs), WIPO Madrid Monitor (Madrid IRs designating MX), Hague Express (Hague IRs designating MX), and Patentscope (PCT national-phase entries). Document gap explicitly: MX national-only file histories, electronic prosecution events, the Gaceta, opposition / nullity proceedings, and the open-data register catalog are not covered and cannot be covered without Mexican egress. | [waves/2026-05-18-secondary-nationals-wave/mx-impi.md](../waves/2026-05-18-secondary-nationals-wave/mx-impi.md) |
