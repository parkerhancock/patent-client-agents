# INPI France (FR) — national

**Layer:** national
**Jurisdiction:** FR (WIPO ST.3: FR)
**Issuing body:** Institut National de la Propriété Industrielle (INPI)
**Rights administered:** patent, utility certificate (certificat d'utilité), trademark, design, geographical indication (industrial/artisanal IGs)
**Working languages:** French (primary); English (thin — some service pages and high-level access docs)
**Connector status:** **statutes shipped** (`FR/Legifrance/IP`); **register APIs yellow** — defer hosted proxy, queue BYOK
**Last verified:** 2026-05-16
**Manifest entry:** [`coverage/sources.yaml` `FR/Legifrance/IP`](../../coverage/sources.yaml) (statutes via `patent_client_agents.legifrance` — Code de la propriété intellectuelle + Code de commerce L.151 trade secrets)

**Detail surveys:**
- [`connectors/inpi_france.md`](../connectors/inpi_france.md) — 2026-05 detail survey (269 lines; broad inventory including Légifrance, Judilibre, INPI PI APIs, PIBD, INPI directives, INAO)
- [`waves/2026-05-16-coverage-batch-2/fr-inpi.md`](../waves/2026-05-16-coverage-batch-2/fr-inpi.md) — 2026-05-16 grounded API discovery focused on whether INPI PI is a hostable proxy

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — FR patent biblio + family + legal events (national-route filings and EP designations of FR). This is the recommended substitute for INPI patent register data.
- **EUIPO** (via planned `regional/euipo.md`) — only for EU-level marks (EUTMs designating FR) and Community designs (RCDs). FR-national-only TMs and designs are NOT covered.
- **WIPO Madrid / Hague** — Madrid IRs designating FR / Hague IRs designating FR; national-only filings remain INPI-exclusive.

---

## §1 Mission

INPI is the French national IP office — the only authoritative registrar
for FR national patents (including utility certificates, *certificats
d'utilité*), FR national trademarks, FR national designs, and industrial/
artisanal geographical indications. It also operates the **Registre national
des entreprises (RNE)** (out of scope for IP).

Because France is an EPC contracting state and an EU member, most "French
patents" are EP-routed (covered by EPO OPS) and most "French trademarks"
are EUTMs (covered by EUIPO). INPI's genuine value-add for agents is the
**French-national-only slice** — ~190k active FR national TMs, FR
national designs, certificats d'utilité, and FR-language full-text fields.

INPI is **separate from Légifrance**, which publishes French primary law
(including the Code de la propriété intellectuelle and Code de commerce
L.151 trade-secret provisions). Légifrance is operated by **DILA**
(Direction de l'information légale et administrative) under the Prime
Minister, fronted by the **PISTE OAuth2 gateway** — that's the *only*
PISTE-fronted French IP-relevant API. The INPI Data PI APIs are on a
**separate authentication stack** at `api-gateway.inpi.fr` — they are
NOT on PISTE.

## §2 What's unique here
- **FR national trademarks** — ~190k active national TMs not registered as
  EUTMs and not visible in EUIPO eSearch. ([INPI marks search base](https://www.inpi.fr/ressources/propriete-intellectuelle/rechercher-une-marque-base-marques))
- **FR national designs** — filed directly with INPI, not via Hague IR or
  RCD; INPI publishes WIPO **ST.86 v1.0** XML — same standard as EUIPO RCD bulk.
- **Certificats d'utilité (utility certificate)** — distinct FR right
  (6-year term, no examination report), low volume (<1000/yr), partially
  in INPADOC but not always at full fidelity.
- **Pre-1978 FR patent backfile (1902-1977)** — published FR applications
  before EPO INPADOC's coverage window starts. Niche but real for
  prior-art searches in older art.
- **INPI Director-General decisions** — TM oppositions (2004+), nullity/
  revocation (2020+), patent oppositions (2020+); previously on
  [`pibd.inpi.fr`](https://pibd.inpi.fr/), now migrating to `data.inpi.fr`
  ([frozen 2026-03-11](https://pibd.inpi.fr/)).
- **Industrial/artisanal geographical indications** — distinct from
  agri/wine GIs (which go via INAO/eAmbrosia); INPI manages industrial
  IGs since 2014.

## §3 Programmatic surfaces

### INPI Data PI APIs (`api-gateway.inpi.fr`)

| Field | Value |
|---|---|
| Endpoint | `https://api-gateway.inpi.fr/services/apidiffusion/api/{brevets,marques,dessins}/search` |
| Auth | INPI Data account (free, email signup) → XSRF-TOKEN cookie → POST `/login` for access token + refresh token. **Not OAuth2 client_credentials.** |
| Format | JSON (search envelope) + XML (notice; ST.36 / ST.66 / **ST.86 v1.0**) + PDF (images) |
| Rate limit | 10,000 requests/day per account; 10 GB/day; **10 req/min** throughput; 10,000-result per-query cap; offset ≤ 500 |
| ToS posture | [Reuse licence](https://data.inpi.fr/content/editorial/licences_reutilisation_donnees_inpi) permits redistribution; [CGU](https://data.inpi.fr/content/editorial/cgu) "no obstruction of third-party access" clause is the friction point for hosted proxies |
| Verdict (zero-infra proxy) | 🟡 **Yellow** — clean technical surface; quota math + CGU push this to BYOK |
| Primary sources | [Accès aux API PI](https://data.inpi.fr/content/editorial/apis_pi) · [Swagger PI](https://data.inpi.fr/content/editorial/swagger-pi) · [Tech doc PDF](https://www.inpi.fr/sites/default/files/Inpi_doc_tech_API_PI_v1.0_0.pdf) |

This is **the cleanest national-IP REST surface we've seen** — SolR Lucene
query syntax, INID-coded field selection, JSON pagination — but the 10 req/
min throughput on a single technical account makes a hosted shared-key
proxy impractical for interactive agent UX.

### Légifrance API (via PISTE OAuth2)

| Field | Value |
|---|---|
| Endpoint | `https://api.piste.gouv.fr/dila/legifrance/...` |
| Auth | **PISTE OAuth2 client_credentials** — registration at [`piste.gouv.fr/registration`](https://piste.gouv.fr/registration), free, open to non-French developers |
| Format | JSON |
| Rate limit | Per-app PISTE limits (not publicly pinned; sandbox + prod separation) |
| ToS posture | [Open Licence 2.0](https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api) — permissive for redistribution |
| Verdict (zero-infra proxy) | 🟢 **Green** — already shipped as `FR/Legifrance/IP` |
| Primary source | [Open data et API - Légifrance](https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api) |

### data.inpi.fr web UI

| Field | Value |
|---|---|
| Endpoint | `https://data.inpi.fr/` |
| Auth | none (search); account required for downloads |
| Format | HTML |
| Verdict (zero-infra proxy) | 🔴 Red — HTML scrape; the JSON API above is the supported path |

### INPI FTP/SFTP bulk

| Field | Value |
|---|---|
| Endpoint | Per-account SFTP credentials issued via `data.inpi.fr` |
| Format | Weekly/bi-weekly ZIPs of XML + images; annual stock |
| Verdict (zero-infra proxy) | 🔴 Red — bulk violates the zero-infra constraint |

### PIBD jurisprudence (legacy, frozen)

| Field | Value |
|---|---|
| Endpoint | `https://pibd.inpi.fr/` |
| Status | **Frozen 2026-03-11**; migrating to `data.inpi.fr` with no published API yet |
| Verdict | 🔴 Red — moving target; route FR IP case law to **Judilibre** instead |

### API Entreprise INPI (PISTE / `entreprise.api.gouv.fr`)

| Field | Value |
|---|---|
| Endpoint | `https://entreprise.api.gouv.fr/v3/inpi/...` |
| Auth | **Gov-to-gov channel** — restricted to French public-sector users (prefectures, tax authorities, etc.) |
| Verdict (zero-infra proxy) | 🔴 Red — not open to private SaaS proxies |
| Primary source | [api.gouv.fr/producteurs/inpi](https://api.gouv.fr/producteurs/inpi) |

## §4 Fees

**Status (2026-05-19):** Three routes shipped on the bundled
`patent_client_agents.fees` connector — `FR/INPI/Fees/Patent`,
`FR/INPI/Fees/Trademark`, and `FR/INPI/Fees/Design`. INPI publishes
a consolidated French-language tariff covering patents (filing,
search report, grant, annuities yrs 2-20), trade marks (filing /
renewal per class on a 10-year cycle), and designs (filing,
prorogation per 5-year period).

- **Landing page (HTML, discovery point):** [Tarifs des procédures et prestations de l'INPI](https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi)
- **Patent + TM + design schedule (canonical fetch target):** ["Tarifs des procédures applicables au 27 avril 2026.pdf"](https://www.inpi.fr/inpi-block/download-document?id=20516) — anonymously accessible PDF, ~157 KB, 2 pages; covers all three rights under section headings BREVETS D'INVENTION / MARQUES / DESSINS ET MODÈLES.
- **Services schedule (out of v1 scope):** ["Tarifs des prestations applicables au 8 avril 2024.pdf"](https://www.inpi.fr/inpi-block/download-document?id=20514) — ancillary document copies.
- **Madrid international:** ["Tarifs pour le dépôt d'une marque internationale.pdf"](https://www.inpi.fr/inpi-block/download-document?id=20520) — Madrid-system fees in CHF; not modeled (WIPO Madrid covers).
- **Statutory basis:** Code de la propriété intellectuelle Articles R.411-17 et seq.; arrêtés fixant les redevances perçues par l'INPI; most recent effective date 2026-04-27.

Discount programs *(eligibility)*:

- **Tarif réduit** (typically 50%): natural persons (personnes
  physiques), non-profit research/education organisations, companies
  with <1000 employees AND <25% capital held by a non-qualifying
  entity. The scraper maps the PDF's "TARIFS RÉDUITS" column to
  `EntityTier.small`.

v1 GAPS (documented in the scraper's notes field):

- Annuity reduced rates are reliably captured by pypdf for years
  2-7 only; years 8-20 reduced rates exist in the source PDF but the
  second column drops out of text extraction for those rows.
- REGISTRES NATIONAUX admin fees, INDICATIONS GÉOGRAPHIQUES, and
  DROITS VOISINS (semiconductor topographies) are out of v1 scope.
- The Madrid international PDF (id=20520) is in CHF and overlaps with
  the WIPO Madrid international scraper; not loaded here.


## §5 Connector strategy

### What we cover today

- [`patent_client_agents.legifrance`](../../src/patent_client_agents/) — PISTE OAuth2 client over Légifrance for **Code de la propriété intellectuelle** (LEGITEXT000006069414, covering copyright L.111-1+, patents L.611-1+, TMs L.711-1+, designs L.511-1+, GIs L.722-1+) and **Code de commerce L.151-1 à L.154-1** (trade secrets). Manifest entry `FR/Legifrance/IP`.
- FR patent biblio + family via [`patent_client_agents.epo_ops`](../regional/epo.md) (transitive, country code `FR`).

### What we should add

**Queue (do not build now):**

- **`inpi_pi` — BYOK FR national TMs + designs.** Per-user credential model
  (each user signs up at `data.inpi.fr`, supplies their session credentials
  via env / config). Targets the two genuine coverage gaps — FR-only TMs
  (~190k active) and FR-only designs. Skip patents (EPO OPS covers them).
  Cross-reference: queue in [`BACKLOG.md`](../../BACKLOG.md) once the BYOK
  pattern is settled (JPO and DPMA per-user paths inform shape).
- **`judilibre`** — FR IP case law via PISTE OAuth (same client as
  Légifrance). Covers Tribunal judiciaire de Paris 3e chambre, Cour d'appel
  de Paris pôle 5, and Cour de cassation. **Highest-leverage FR IP module**
  per the [2026-05 connector survey](../connectors/inpi_france.md). Separate
  PR — does not depend on INPI PI resolution.
- **`inpi_directives`** — three INPI PDF manuals (patents, TM opposition,
  designs registration) into the `StaticLawCorpus` base. Half-day work each.

### What we should NOT add

- **Hosted-proxy INPI PI with a shared technical account.** Quota math
  (10 req/min, 10,000 req/day) and [CGU anti-obstruction clause](https://data.inpi.fr/content/editorial/cgu)
  push this off-spec. Even if the licence permits redistribution, the
  service-level obligation forbids "limiting third parties' access" —
  which a saturated shared key plausibly does.
- **INPI patent live proxy (any model).** Duplicates EPO OPS for the
  ~99% of FR-relevant patent coverage. Reserve API budget for the actual
  gaps (TMs, designs).
- **PIBD HTML scrape.** Frozen 2026-03-11, migration in progress, target
  schema not announced. Route FR IP case law to Judilibre instead.
- **API Entreprise INPI channel.** Gov-to-gov, not open to private SaaS.
- **INPI bulk SFTP.** Violates zero-infra-on-our-side constraint.

### Next steps

1. Design the BYOK pattern uniformly across JPO, DPMA, and now INPI —
   single env-var convention for user-supplied IP-office credentials.
2. Build `judilibre` on top of the existing PISTE OAuth client used for
   Légifrance. One-PR scope.
3. Watch the [PIBD migration target](https://data.inpi.fr/) for a
   documented case-law API surface — if INPI ships one with JSON
   responses, prefer it over a Judilibre-only path for INPI Director-
   General decisions.
4. Queue dedicated fee research for fr-inpi (split between patent, TM,
   design, plus the EUR-denominated reductions tier).

## §6 Open questions

- **PISTE registration accessibility for non-French developers.** [`piste.gouv.fr/registration`](https://piste.gouv.fr/registration) accepts name + email only on its face — no SIREN required for Légifrance/Judilibre apps. Confirm empirically when registering the Judilibre app.
- **INPI Data account accessibility for non-French registrants.** No primary source states a French-residency requirement, but the entire signup flow is French-only. Confirm empirically.
- **PIBD migration target schema.** When does the data.inpi.fr replacement for PIBD ship? Will it expose JSON/API or HTML only? No primary source found beyond the [2026-03-11 freeze notice](https://pibd.inpi.fr/).
- **Judilibre Tribunal judiciaire de Paris 3e chambre coverage depth.** "Lower courts civil since 2024-12-31" per the [Cour de cassation open-data page](https://www.courdecassation.fr/acces-rapide-judilibre/donnees-ouvertes-open-data-et-api) — is the IP trial chamber retrospectively indexed, or forward-looking only?
- **Certificats d'utilité coverage in EPO OPS / INPADOC.** Empirical test needed to confirm whether the INPI BYOK path is the only way to get full-fidelity utility-certificate data.
- **INPI PI quota semantics.** Are the 10,000/day and 10 GB/day caps per-account or per-key? Does SFTP bulk share the same quota? No primary source pins this precisely.
- **INPI reuse licence vs. Etalab 2.0 verbatim differences.** Primary source confirms it is "approved Etalab variant" but the redistribution-via-proxy permission needs a careful read against the [INPI reuse licence](https://data.inpi.fr/content/editorial/licences_reutilisation_donnees_inpi) text.

## §7 References

Primary sources only — `inpi.fr`, `data.inpi.fr`, `piste.gouv.fr`,
`legifrance.gouv.fr`, `courdecassation.fr`, `gouv.fr`, WIPO.

**Service overviews (INPI PI):**
- [Accès aux API - Propriété industrielle - Data INPI](https://data.inpi.fr/content/editorial/apis_pi)
- [Accès aux API et FTP | INPI](https://www.inpi.fr/ressources/propriete-intellectuelle/acces-aux-api-et-ftp)
- [Access to API and FTP | INPI (EN)](https://www.inpi.fr/en/resources/intellectual-property/access-to-API-and-FTP)
- [DATA INPI Portal — WIPO INSPIRE](https://inspire.wipo.int/data-inpi-portal-patent-database)

**Technical specs:**
- [INPI Doc Technique API PI v1.0 (PDF)](https://www.inpi.fr/sites/default/files/Inpi_doc_tech_API_PI_v1.0_0.pdf)
- [Swagger PI - Data INPI](https://data.inpi.fr/content/editorial/swagger-pi)
- [Doc tech Dessins & Modèles ST.86 (PDF)](https://www.inpi.fr/sites/default/files/doctech_dmfr_v1_3_.pdf)

**Legal terms:**
- [Conditions générales d'utilisation - Data INPI](https://data.inpi.fr/content/editorial/cgu)
- [Licences de réutilisation des données de l'INPI](https://data.inpi.fr/content/editorial/licences_reutilisation_donnees_inpi)
- [Mentions légales - Data INPI](https://data.inpi.fr/content/editorial/mentions_legales)

**Fees:**
- [Tarifs des procédures et prestations de l'INPI](https://www.inpi.fr/ressources/propriete-intellectuelle/tarifs-procedures-et-prestations-de-linpi)
- [Tarifs applicables au 27 avril 2026 (PDF)](https://www.inpi.fr/inpi-block/download-document?id=20516)

**Statutes (already shipped via FR/Legifrance/IP):**
- [Code de la propriété intellectuelle - Légifrance](https://www.legifrance.gouv.fr/codes/texte_lc/LEGITEXT000006069414/)
- [Code de commerce L.151-1 à L.154-1 (secret des affaires) - Légifrance](https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000005634379/LEGISCTA000037266547/)
- [Open data et API - Légifrance](https://www.legifrance.gouv.fr/contenu/pied-de-page/open-data-et-api)

**PISTE / Judilibre (separate workstream):**
- [PISTE — DILA registration](https://piste.gouv.fr/registration)
- [Catalogue des API publiques - api.gouv.fr](https://api.gouv.fr/producteurs/inpi)
- [Données ouvertes et API — Judilibre](https://www.courdecassation.fr/acces-rapide-judilibre/donnees-ouvertes-open-data-et-api)

**Case law (PIBD migration in progress):**
- [PIBD | INPI (frozen 2026-03-11)](https://pibd.inpi.fr/)
- [Consulter la base de jurisprudence en propriété industrielle | INPI](https://www.inpi.fr/ressources/propriete-intellectuelle/consulter-base-de-jurisprudence-en-propriete-industrielle)

**Detail survey + wave:**
- [`connectors/inpi_france.md`](../connectors/inpi_france.md) — full 269-line asset survey
- [`waves/2026-05-16-coverage-batch-2/fr-inpi.md`](../waves/2026-05-16-coverage-batch-2/fr-inpi.md) — 2026-05-16 grounded API discovery

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Reconciled the older "PISTE OAuth fronts INPI PI" framing — PISTE actually fronts Légifrance + Judilibre + (gov-to-gov) API Entreprise; the public INPI PI APIs are on `api-gateway.inpi.fr` with session-token auth. Verdict for hosted-proxy INPI PI: 🟡 Yellow (clean API, quota + CGU push to BYOK). Statutes (`FR/Legifrance/IP`) remain green and shipped. | [waves/2026-05-16-coverage-batch-2/fr-inpi.md](../waves/2026-05-16-coverage-batch-2/fr-inpi.md) |
