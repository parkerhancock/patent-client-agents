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

## §1 Coverage today: 13 of 30 offices

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
| 23   | INPI France        | P / TM / D     | PDF (curated catalog + annuity walker); large/small tiers via "TARIFS RÉDUITS" column; SPC at y=21 |
| 13   | TIPO Taiwan        | P / TM         | HTML table + bilingual PDF curated catalog |

Plus 3 non-national routes:
* **EUIPO** (regional TM/D — Next.js SSR stream decoding for TM, HTML for D)
* **WIPO** PCT / Madrid / Hague (international systems)

**Total** = 17 offices on 25 routes; 13/30 of the WIPO national ranking,
or 13/27 if we exclude the offices below that are blocked on factors
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
| 23 | ~~**INPI France**~~ | ✅ SHIPPED 2026-05-19 via inpi.fr/inpi-block/download-document?id=20516 (the procedures PDF, anonymously accessible — discovered as an anchor on the INPI Tarifs landing page). The Cloudflare-blocked legifrance route turned out to be unnecessary. | n/a | n/a | n/a |
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

* **Today**: 13 of 30 = 43%.
* **With the EN-PDF-anchor pattern applied to the unprobed offices**:
  estimate 18-22 / 30 = 60-73%. The Brazil + France wins this session
  came from finding a parallel public PDF anchor that bypassed the
  obvious Cloudflare/auth wall on the canonical URL. The same pattern
  likely works for IL, ES, IT, SG, MY, HK, TR, ID, VN, TH, PH.
* **With a stealth HTTP service + ~2 weeks**: 22-25 / 30 = 73-83%.
* **30 / 30**: requires sanctions waivers for RU/IR. The other
  remaining offices should all be reachable via the EN-PDF pattern
  or a paid official API; pure 30/30 is feasible without exotic infra
  if we can get a clean probe sweep first.

The honest target is **22-25 of 30 ≈ 80% coverage** of top-30 by
patent filing volume on a one-developer push. Beyond that, RU and
Iran need sanctions clearance; the rest is "keep probing until we
find the anonymous EN-PDF route."

---

## §5 Recommended next steps (in order of leverage)

**Discovery first, ship second.** The session re-anchored this
priority after Brazil and France both turned out to be unblockable
once we found the right URL. The next session should:

1. **Do a 30-min "EN-PDF anchor sweep"** across the remaining
   unprobed offices: IT, ID, VN, TH, PH, NZ, UPRP, HK, MY, IL, ES,
   SG, TR. For each: fetch the main fees URL → look for `<a href>`
   to a downloadable PDF (`.pdf`, `/download-document`, `/block/`,
   `/wSite/public/Attachment/`, etc.) AND try the `/en/`-prefix
   equivalent. Even if the canonical URL 403s, a parallel anonymous
   PDF route is the more-common-than-not outcome.
2. **Order ship work by ranking × accessibility**:
   - Singapore (#22) — landing hub works; SSO has the statutory
     route under stochastic rate-limit. Try the EN-PDF pattern
     on ipos.gov.sg first.
   - Italy (#24) — uibm.mise.gov.it not yet probed; statutory
     ministerial decree route via Normattiva is documented.
   - Spain (#25) — research note has BOE links; both the
     procedural fees pages 410'd but BOE is anonymously fetchable.
   - Israel (#26) — Cloudflare on gov.il; check WIPO Lex copy at
     `wipo.int/wipolex/en/legislation/details/19117` first.
   - Mexico (#15) — geo-blocked subdomain; needs non-US IP. Lower
     priority without stealth service.
3. **Defer until policy review**: Rospatent + Iran IPI (sanctions);
   Brazil 2025 Portaria 10 update (waiting on INPI to republish the
   EN PDF — the scraper currently reflects the 2019 schedule).

Until step 1 is decided, further office-by-office grinding is likely
to keep producing 0 commits per hour.

### §5.1 Next-session pickup: EN-PDF-anchor probe script

Drop this into the next session as a starting point. It hits the
landing pages for the 13 unshipped non-sanctioned offices in
parallel, reports HTTP status + PDF-link count + currency hints,
and flags any office whose page has a fetchable PDF anchor.

```python
import asyncio, httpx, re
from lxml import html as L

OFFICES = {
    "SG/IPOS-patent":   "https://www.ipos.gov.sg/manage-ip/",
    "IT/UIBM":          "https://uibm.mise.gov.it/index.php/it/tasse-e-tariffe",
    "ES/OEPM-patent":   "https://www.oepm.es/es/invenciones/Presentar-una-solicitud/tasas-pagos-y-reintegros/",
    "IL/ILPO":          "https://www.gov.il/en/departments/ilpo",
    "MY/MyIPO":         "https://www.myipo.gov.my/en/patent/",
    "SA/SAIP":          "https://saip.gov.sa/en/",
    "HK/HKIPD":         "https://www.ipd.gov.hk/en/",
    "TR/TurkPatent":    "https://www.turkpatent.gov.tr/en/",
    "ID/DGIP":          "https://www.dgip.go.id/",
    "VN/IPVN":          "https://ipvietnam.gov.vn/",
    "TH/DIP":           "https://www.ipthailand.go.th/",
    "PH/IPOPHL":        "https://www.ipophl.gov.ph/",
    "NZ/IPONZ":         "https://www.iponz.govt.nz/get-ip/patents/fees/",
    "PL/UPRP":          "https://uprp.gov.pl/en",
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept-Language": "en;q=0.9",
}

async def probe(client, name, url):
    try:
        r = await client.get(url, follow_redirects=True)
        d = L.fromstring(r.text) if r.text else None
        pdfs = []
        if d is not None:
            for a in d.cssselect("a[href]"):
                href = (a.get("href") or "").lower()
                text = (a.text_content() or "").strip().lower()
                if ".pdf" in href or "download-document" in href or "/block/" in href:
                    if any(t in text for t in ["fee", "tarif", "redevance", "tasa", "ücret", "費", "fees"]) or ".pdf" in href:
                        pdfs.append((a.text_content().strip()[:50], a.get("href")))
        # Currency hints
        currencies = sum(c in r.text for c in ["€", "£", "$", "¥", "₺", "₹", "₪", "₱", "₫", "฿", "₩", "Rp", "RM"])
        return f"{name:18s} {r.status_code} bytes={len(r.text):>7} pdf-anchors={len(pdfs):>2} curr-hints={currencies:>3}  →  first PDF: {pdfs[0] if pdfs else '-'}"
    except Exception as e:
        return f"{name:18s} ERROR {type(e).__name__}: {str(e)[:50]}"

async def main():
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS, http2=True) as c:
        results = await asyncio.gather(*[probe(c, n, u) for n, u in OFFICES.items()])
        for r in results:
            print(r)

asyncio.run(main())
```

Then, for offices with PDF anchors: download, run `pypdf` for a
sample page, and decide between the IPIN/DPMA/INPI-BR PDF pattern
(numeric codes + columns) vs the INPI-FR curated-catalog pattern
(prose with embedded amounts). Most office PDFs are clean column
tables — favour the IPIN pattern when possible.

---

## §6 Session log

* **2026-05-19 (after Brazil ship)** — User pointed at the INPI France
  Tarifs landing page. A deeper inspection (looking past the 11 inline
  ``<li>`` €-items I'd captured earlier) revealed three downloadable
  PDF anchors on the page, one of which — "Tarifs des procédures
  applicables au 27 avril 2026.pdf" at
  `inpi.fr/inpi-block/download-document?id=20516` — is the full
  cross-right schedule. Anonymously accessible, no Cloudflare on the
  download endpoint. Shipped `FR/INPI/Fees/{Patent,Trademark,Design}`
  via a curated-catalog + annuity-walker. Patent annuities years 2-20
  extracted (reduced rates reliably for 2-7 only — pypdf drops second
  column for years 8-20).
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
