# Fees connector — top-30 coverage gap

Honest accounting of where `patent_client_agents.fees` stands against the
WIPO World IP Indicators 2024 ranking of patent offices by filing volume
(2023 data). Updated 2026-05-19 — TIPO Taiwan (`db91c5d`) and INPI Brazil
shipped; the Brazil unblock came from the user finding the English-PDF
mirror at `gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf`,
which is anonymously accessible while the pt-BR Plone tabela page is
auth-gated.

This doc exists so the next session doesn't have to re-discover what's
blocking each remaining office.

---

## §1 Coverage today: 12 of 30 offices

Routes already shipped on the fees connector
(`src/patent_client_agents/fees/registry.py`):

| Rank | Office | Routes | Patterns demonstrated |
|------|--------|--------|------------------------|
| 1    | CNIPA China        | P              | Hierarchical HTML state-machine walker |
| 2    | USPTO              | P / TM / D     | HTML × many sections; entity tiers (large/small/micro) |
| 3    | JPO Japan          | P              | Full Sec-Fetch fingerprint required; multi-cohort tagging |
| 4    | KIPO Korea         | P              | Per-claim row pairing; "N to M years" expansion |
| 5    | EPO                | P              | Hidden JSON BFF discovered via dev-browser |
| 6    | IPO India          | P              | Schedule_1.pdf via pypdf with column-alignment sanity check |
| 7    | DPMA Germany       | P              | PDF (pypdf) with 6-digit code prefix categorization |
| 9    | CIPO Canada        | P              | Multi-table HTML; English-word ordinal year-band expansion |
| 10   | IP Australia       | P              | Multi-table HTML, heading-walks-up-DOM |
| 11   | UKIPO              | P / TM         | gov.uk per-form fan-out (bounded concurrency = 5) |
| 12   | INPI Brazil        | P / TM         | PDF (pypdf) with backward code lookup; large/small tiers via "discounted" column |
| 13   | TIPO Taiwan        | P / TM         | HTML table + bilingual PDF curated catalog |

Plus 3 non-national routes:
* **EUIPO** (regional TM/D — Next.js SSR stream decoding for TM, HTML for D)
* **WIPO** PCT / Madrid / Hague (international systems)

**Total** = 16 offices on 22 routes; 12/30 of the WIPO national ranking,
or 12/27 if we exclude the offices below that are blocked on factors
outside our control (Russia + Iran sanctions, plus offices we have not
yet found a public route for).

---

## §2 Remaining offices (ranked 8-30) — blocker + unblock path

Probes were run with realistic browser UA + http2 between 2026-05-19
~13:00-14:00 UTC. Each "blocker" entry is what a plain `httpx` fetch
returned, not what the page would look like in a real browser.

| # | Office | Last-known fee URL | Probe result | Blocker class | Unblock path |
|---|--------|--------------------|--------------|---------------|--------------|
| 8 | **Rospatent** RU | rospatent.gov.ru | n/a (not probed) | Sanctions (OFAC/EU) | Defer pending compliance review. Schedule itself is informational only; the question is whether we can host it on the public demo. |
| 12 | ~~**INPI Brazil**~~ | ✅ SHIPPED 2026-05-19 via `gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf` (the EN-language PDFs are anonymously accessible while the pt-BR Plone landing is auth-gated) | n/a | n/a | n/a |
| 14 | **HKIPD** Hong Kong | ipd.gov.hk (URL pattern unknown) | 404 on `/eng/fees.htm` and `/en/patents/fees/index.html` | URL drift / unknown | 15-min dev-browser navigation from `ipd.gov.hk` homepage should find current URLs. |
| 15 | **IMPI Mexico** | gob.mx/impi | Geo-blocked subdomain per research note `mx-impi.md` | Geo-block + DOF gazette gating | Stealth HTTP service with non-US IP; or paid LATAM proxy. |
| 16 | **Iran IPI** | n/a | n/a (not probed) | Sanctions + connectivity | Defer pending compliance + sanctions review. |
| 17 | **TürkPatent** | turkpatent.gov.tr/ucret-tarifesi | 200 OK, 0 tables, 21 scripts | JS-rendered SPA | Hidden API discovery via dev-browser (EPO-style); or dev-browser render. |
| 18 | **DIP Thailand** | ipthailand.go.th | Not probed | PDF (Thai + EN) per research | Probe needed; likely DPMA/IPIN-shape PDF scraper. |
| 19 | **DGIP Indonesia** | dgip.go.id | Not probed | PP 28/2019 PDF + HTML | Probe needed. |
| 20 | **IP Viet Nam** | noip.gov.vn | Not probed | Circular 263/2016 PDF | Probe needed. |
| 21 | **EAPO** | eapo.org | Not probed | Multilateral; potential RU exposure | EAPO billing is in USD which is unusual. Compliance check first. |
| 22 | **IPOS Singapore** | sso.agc.gov.sg/SL/PA1994-R1 | First fetch 200 OK / 471 KB / 141 tables (Patents Rules); follow-ups hit CloudFront 403 (CDN rate-limit) | **Stochastic CDN rate-limit** + content not in body of /SL/PA1994-R1; First Schedule lives at separate sub-URL | Use SSO with respectful caching (TTL ≥ 7 days from one hit) + find the First Schedule's `?ProvIds=Sc1-` URL form. ipos.gov.sg sub-pages all 404 on URL guesses — the SSO statutory route is the real source. ~2-3 hr session. |
| 23 | **INPI France** | legifrance.gouv.fr/codes/article_lc/LEGIARTI000043891691/ | 403 Cloudflare challenge ("Just a moment...") | **Cloudflare JS challenge** | Three options: (a) Legifrance PISTE API (free, requires registration at `piste.gouv.fr`); (b) stealth HTTP service; (c) dev-browser with stealth profile. Sub-pages on inpi.fr are 404; the only working inpi.fr Tarifs page covers PCT/Madrid/Brevet européen + ~11 line-items, NO annuities. |
| 24 | **UIBM Italy** | uibm.mise.gov.it/index.php/it/tasse-e-tariffe | Not yet probed in this session | TBD | Probe needed. uibm.mise.gov.it has historically been straightforward HTML. |
| 25 | **OEPM Spain** | oepm.es/es/invenciones/...tasas-pagos-y-reintegros/ | HTTP 410 Gone — URL retired | URL drift | URL discovery. Backup: BOE statutory route via `boe.es/buscar/act.php?id=BOE-A-2015-8328` (Ley 24/2015 Patentes) annual update. |
| 26 | **ILPO Israel** | gov.il/en/departments/ilpo | 403 Cloudflare | Cloudflare bot-protection | Same options as France: stealth, dev-browser, or look for the WIPO Lex copy at `wipo.int/wipolex/en/legislation/details/19117`. |
| 27 | **MyIPO Malaysia** | myipo.gov.my/en/patent/ (200, 3 tables on Act page) | URL discovery needed for actual fees page | URL unknown | 15-min dev-browser navigation from myipo.gov.my homepage. Probably reachable. |
| 28 | **IPOPHL Philippines** | ipophl.gov.ph | Not probed | Memorandum Circular PDF + HTML schedule | Probe needed. |
| 29 | **SAIP Saudi Arabia** | saip.gov.sa/en/ | ConnectTimeout from US IP | Geo-block / slow CDN | Either non-US IP via stealth service, or retry from a healthier route. |
| 30 | **UPRP Poland** | uprp.gov.pl | Not probed | Regulation annex PDF | Probe needed. |

Boundary cases just outside top-30 (any could displace #28-30 in any
given year): South Africa CIPC, Argentina INPI, Egypt EAIP, Switzerland
IGE/IPI (most CH activity flows through EPO anyway), New Zealand IPONZ
(has research note + research suggests clean HTML at iponz.govt.nz/get-ip).

---

## §3 Aggregated unblock paths

Looking across the gap table, the same handful of infra needs unblock
many offices at once. Picking ONE of these gets us further than any
single-office push:

### 3.1 Stealth HTTP service (highest leverage)

A residential-IP stealth proxy (ScrapingBee, Zyte, ScraperAPI, Bright
Data — $30-300/mo) would unblock:

* INPI Brazil (Plone auth-gate may persist, but Portaria PDFs on
  `in.gov.br` would be reachable)
* Legifrance for INPI France
* Wayback Machine (currently rate-limiting us)
* Brazilian DOU search
* Cloudflare-challenged pages (Israel ILPO, possibly more)
* IMPI Mexico geo-block
* SAIP Saudi Arabia ConnectTimeout from US

**Estimated impact: +5-7 offices unblocked from infrastructure alone**,
without writing any office-specific code. Each unblocked office still
needs its 2-3 hr scraper write + verification.

**Cost:** ~$30/mo on the entry tier; one-time integration ~2-3 hr
(BYOK env-var, route critical clients through the proxy).

**Tradeoff:** Adds an external dependency and a recurring spend. Worth
it for hosted-demo coverage; not worth it if the goal is local-only.

### 3.2 Paid official APIs (free but require registration)

* **Legifrance PISTE** — `piste.gouv.fr` — French statutory database
  with structured Code de la propriété intellectuelle access. Free
  with registration. Unblocks France only.
* **Gazette PISTE** — same provider — covers DOU equivalents for
  Portugal/Spain in some cases.
* **gov.br federated auth** — Brazilian CPF or consular nat-reg
  required. Bureaucratic for foreign developers; not recommended
  unless we have a Brazilian collaborator.

### 3.3 Dev-browser stealth profile

The `dev-browser` skill at `~/.claude/skills/dev-browser/` ships a
stealth-mode chromium. In this session it was in a flaky state (CDP
WebSocket connection timing out after a restart) — about 30 min of
investment to get it healthy. Once working, unblocks:

* All Cloudflare-challenged pages (FR, IL)
* All JS-rendered SPAs (TR, BR — though BR auth-gate persists)
* Wayback Machine (browser doesn't trigger API rate limit)

**Estimated impact: similar to §3.1 but no recurring spend.** Tradeoff:
slower per-fetch (~5-10s vs <1s) and requires the dev-browser server
running.

### 3.4 Sanctions clearance for RU/IR

Russia (Rospatent) and Iran (IPI) are blocked on OFAC / EU sanctions
considerations, not technical infrastructure. The fee schedule itself
is publicly informational, but hosting it on `mcp.patentclient.com`
without compliance review is a different question. Recommended:

* Defer Rospatent + Iran until a sanctions advisor signs off.
* If the answer is "informational publication is fine," both offices
  are reachable from the US with regular `httpx`.
* If the answer is "no public hosting," we can still ship the
  scrapers locally and gate them off the hosted demo.

---

## §4 Realistic ceiling without paid infra

* **Today**: 11 of 30 = 37%.
* **With dev-browser stealth fixed + 1 week of office-specific work**:
  estimate 18-20 / 30 = 60-67% (everything except Brazil-auth-gated,
  sanctions-blocked, and offices whose fees genuinely don't exist
  online).
* **With a stealth HTTP service + ~2 weeks**: 22-25 / 30 = 73-83%.
* **30 / 30**: requires Brazilian CPF/consular registration + a
  sanctions waiver. Not feasible as a one-developer push.

The honest target is probably **22-24 of 30 ≈ 75% coverage** of
top-30 by patent filing volume. The remaining 6-8 offices are
blocked on factors outside our pure-coding control (auth, sanctions,
recurring infra spend).

---

## §5 Recommended next steps (in order of leverage)

1. **Pick the unblock path** (§3.1 stealth service, §3.3 dev-browser
   fix, or sequential office-by-office without infra). Without
   picking, every session burns 60+ min on rediscovery.
2. **Probe the unprobed offices** (IT, ID, VN, TH, PH, NZ, UPRP, HK,
   MY) in a dedicated 30-min session. Some may turn out to be clean
   HTML; we won't know until we probe with the right tooling.
3. **Ship a "low-hanging fruit" batch** of whichever offices come
   back clean from the probe sweep — Italy, Indonesia, Philippines,
   New Zealand are the likely winners.
4. **Defer the hard offices** (BR, FR, IL, ES, IT-statutory) until
   the unblock-path decision is made.

Until step 1 is decided, further office-by-office grinding is likely
to keep producing 0 commits per hour.

---

## §6 Session log

* **2026-05-19 (after the gap doc)** — User found the English-language
  INPI Brazil fee PDFs at `gov.br/inpi/en/costs-and-payment/schedule-of-fees-*.pdf`
  (anonymously accessible, no auth). Shipped `BR/INPI/Fees/Patent`
  (272 FeeItems from 60 codes × tier × year-band expansion) and
  `BR/INPI/Fees/Trademark` (34 FeeItems). Worth noting: the official
  research note had been pointing to the auth-gated pt-BR landing
  page; the EN-PDF path on `/inpi/en/costs-and-payment/` is the
  practical working route. v1 GAPS documented for the multi-tier
  per-claim surcharges (prose-formatted in the PDF) and PCT-section
  variable-amount rows.
* **2026-05-19 (post-TIPO)** — Probed 9 offices for the "easy HTML
  batch" plan (BR, SG, FR, ES, IL, MY, SA, HK, TR). Found that the
  subagent's "low complexity" estimate was wrong: only 1 returned a
  plausibly-scrapeable response on first probe (MyIPO patent ACT
  page; not actually the fees page). Spent 30 min on Brazil
  (auth-gated), 20 min on France (Cloudflare), 10 min on Singapore
  (CDN rate-limit). Wrote this doc instead of forcing another
  attempt. Doc superseded by the EN-PDF discovery for Brazil.
