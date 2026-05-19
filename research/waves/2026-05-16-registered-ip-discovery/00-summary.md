# Registered-IP discovery — synthesis

**Date:** 2026-05-16
**Researchers:** five general-purpose subagents (one per target, WIPO trio batched as one)
**Goal:** identify free public REST/JSON/XML APIs at top-tier patent offices that we can proxy from our connector at runtime — no bulk downloads, no offline corpus, no search index on our side.
**Constraint:** zero on-disk infrastructure beyond an HTTP client.

---

## TL;DR

The premise was wrong. Out of eight surfaces researched across five jurisdictions, **none cleanly meet the zero-infra proxy bar**:

| Office | Verdict | Blocker | Detail |
|---|---|---|---|
| KIPO Korea | 🟡 Yellow | ToS forbids key sharing → BYOK-only architecture | [kipo-kipris-plus.md](kipo-kipris-plus.md) |
| WIPO PATENTSCOPE | 🔴 Red | Paid SOAP/SFTP only; ToS §2.1 forbids automated queries | [wipo-global-databases.md](wipo-global-databases.md) |
| WIPO Global Brand DB | 🔴 Red | Single API restricted to "collaborating IP Offices"; UI CAPTCHA-walled | [wipo-global-databases.md](wipo-global-databases.md) |
| WIPO Global Design DB | 🔴 Red | Only filing-side Hague Web Services; no public search; 24-hour IP block for "robot" behaviour | [wipo-global-databases.md](wipo-global-databases.md) |
| UKIPO Patents | 🔴 Red | IPSUM retired 2025-01-22; One IPO replacement HTML-only; no API timeline published | [ukipo-uk.md](ukipo-uk.md) |
| UKIPO Trade Marks | 🔴 Red | HTML-only; transformation just entering design phase | [ukipo-uk.md](ukipo-uk.md) |
| UKIPO Designs | 🔴 Red | HTML lookup only; designs phase queued behind trade marks | [ukipo-uk.md](ukipo-uk.md) |
| CIPO Canada (patents/TMs/designs) | 🔴 Red | Zero REST search APIs across all three rights; mid-modernization | [cipo-canada.md](cipo-canada.md) |
| DPMA Germany | 🔴 Red | Clean REST API exists but contract §3.2 prohibits proxy use | [dpma-germany.md](dpma-germany.md) |

---

## The pattern is the finding

The mental model "lots of free public REST APIs we can proxy" doesn't survive contact with primary sources. Across the eight surfaces checked, proxy-shaped use is being **actively closed off** through one or more of:

1. **No API at all.** UKIPO Patents (IPSUM dead since Jan 2025), UKIPO TMs/designs, CIPO patents/TMs/designs. The HTML web UI is the only public surface.
2. **ToS prohibitions on automation.** WIPO's three databases share identical language in their terms of service: "perform automated queries"; >10 actions/min from one IP "can be considered excessive." Source: [Brand DB Terms of Use](https://branddb.wipo.int/en/quicksearch/about/terms) (October 2025).
3. **Contract terms barring redistribution.** DPMA's standard DPMAconnectPlus contract §3.2 explicitly forbids passing data to third parties — the legal definition of a proxy. Source: [DPMAconnectPlus contract terms (PDF)](https://www.dpma.de/docs/recherche/dienste/dpmaconnectplusvertragsbedingungen.pdf).
4. **Restriction to "collaborating IP Offices."** WIPO's only public-facing Brand DB API (idAPI 188 in the [WIPO API Catalog for Intellectual Property](https://apicatalog.wipo.int/)) is gated to fellow IP offices, not commercial third parties.
5. **Paid-only commercial tiers.** WIPO PATENTSCOPE programmatic access is CHF 600–2,000/year for a SOAP/SFTP batch-download product — not a query API and explicitly a paid product. Source: [PCT Data Products and Services](https://www.wipo.int/en/web/patentscope/data/index).
6. **Per-key sharing prohibition.** KIPO's KIPRIS Plus ToS §11: "Members may only obtain one Authentication Key at a time. Additionally, Members shall not provide, disclose, or share Authentication Keys with others." This forbids the one-key proxy pattern.
7. **Operational hostility.** Paper contracts by postal mail (DPMA), fixed-IP requirements that fight cloud egress (DPMA §2.1), CAPTCHAs on every page load (WIPO Brand DB AltCha proof-of-work, observed 2026-05-16), undocumented IP allowlists.

The integrations we already have — USPTO ODP, USPTO PPUBS, USPTO Assignments, USPTO Office Actions, USPTO PTAB, EPO OPS, EUIPO Trade Marks, EUIPO Designs, JPO, IP Australia Patents/TMs/Designs/Bulk, Google Patents, USITC — are **the exceptions, not the rule**. USPTO is unusually permissive because of its statutory open-data mandate. Several of the others (EUIPO, JPO, IP Australia) are auth-keyed and presumably handled via per-deployment credentials.

## Implications for the roadmap

**"Just add more proxy connectors for top patent offices" is not a viable growth strategy.** The road is closed for the offices we checked, and the same patterns likely repeat at KIPO-adjacent jurisdictions (e.g., CN, JP — though JPO we've handled via credentials).

The realistic moves under the zero-infra constraint:

### 1. Bring-your-own-key (BYOK) where the API itself is clean

**KIPO is the canonical example.** The API is technically excellent — REST/XML at `kipo-api.kipi.or.kr/openapi/service/…`, structured field search, patents/UMs/designs/TMs, 1948-onward backfile, free 1,000-call/month tier. The only blocker is the ToS prohibition on sharing keys.

**Architecture:** require the end user to supply their own `KIPO_KIPRIS_API_KEY` via env var; our connector layer becomes a typed Python interface over the user's own key, identical pattern to how `jpo` requires `JPO_API_USERNAME` + `JPO_API_PASSWORD` and `ip_australia_*` requires `IPAUSTRALIA_CLIENT_ID` + `IPAUSTRALIA_CLIENT_SECRET`. Tool registration becomes env-gated (CONNECTOR_STANDARDS.md §7.x). On the hosted demo (mcp.patentclient.com) the KIPO tools simply don't register without a key — which is fine and honest.

**Secondary route:** the KIPO research file flags that [`data.go.kr`](https://www.data.go.kr/), Korea's national open-data portal, mirrors the same KIPRIS endpoints with an English UI (e.g., trademark service `15043964`, design service `15043970`). If KIPO direct signup hits Korean-identity-verification friction for non-Korean developers, `data.go.kr` is the alternate registration path — same data, different gate.

DPMA *could* be BYOK-shaped in the same way for users willing to sign their own German paper contract, but that's a high enough operational bar that "active connector" is misleading — better to wait for DPMAregister modernization or rely on EPO OPS for German patents.

### 2. Squeeze more out of aggregators we already have

**EPO OPS** already covers German national patents transitively, plus EP, plus PCT national-phase entries for many designated states. The §5.9 envelope sweep on EPO tools completed on 2026-05-18; the next layer of value is per-jurisdiction recipe helpers (CN/DE/KR via INPADOC).

**Google Patents** covers many jurisdictions transitively. ToS friction we already accept; the scraper is operational.

**USPTO ODP/PPUBS/Assignments/Office Actions/PTAB/Petitions** — all on the §5.9 envelope as of 2026-05-18.

### 3. Keep building substantive-law corpora

The May 2026 fan-out wave (IPO India, DPMA, Légifrance, Taiwan Trade Secrets — substantive law) is the kind of expansion that *actually ships* under our constraint. Statutes, manuals, guidelines, and case-law publications from official sites are public-domain text with no ToS friction. This is the lane that scales.

### 4. Monitor for partner-program openings

Two specific signals worth watching:

- **WIPO Brand DB partner API.** Undocumented endpoint observed at `public-api.branddb.wipo.int` returns "Missing Authentication Token" via AWS API Gateway — suggests WIPO is building a partner program. Recheck quarterly via [WIPO API Catalog for Intellectual Property](https://apicatalog.wipo.int/).
- **UKIPO One IPO Patents Service** launched publicly 2026-03-31 without a search API. UKIPO has stated "exact timeline for releasing APIs is still to be confirmed." Recheck quarterly via [gov.uk/government/news](https://www.gov.uk/government/organisations/intellectual-property-office).
- **CIPO Next Generation Patents (NGP)** is mid-rollout; HTML surface migrated from `ic.gc.ca` to `ised-isde.canada.ca/cipo` in 2024. Monitor [ISED API Catalogue](https://api.ised-isde.canada.ca/) for new entries.

### 5. Targeted commercial partnerships (if budget allows)

- **WIPO PATENTSCOPE** paid SOAP/SFTP product (CHF 600–2,000/yr) gets us PCT + many national collections. Volume-shaped product (batch + SFTP), not a query API — would need careful architecture to expose as live tools.
- **DPMA DPMAconnectPlus** paid contract (EUR 200 + signed paper contract) covers DE patents/TMs/designs. Same proxy-redistribution restriction in §3.2 means even paid access doesn't unlock a hosted-demo proxy.

## Recommendation

1. **Stop pursuing "free national-office REST APIs" as a growth strategy.** The pattern across 8/8 surfaces is restrictive-to-hostile; further canvassing in adjacent jurisdictions (CN, BR, IN, MX) is likely to find more of the same.
2. **Build the KIPO BYOK connector** next. One office, real coverage, ToS-clean if architected per-user. Follows the JPO/EUIPO/IPA pattern we already operate.
3. ~~Finish the MIGRATION_PLAYBOOK pending rows.~~ Done 2026-05-18 — all 21 rows of the original sweep landed; existing tools are §5.9 envelope-compliant with provenance and lean+full projections.
4. **Continue substantive-law expansion** — this is the lane that ships freely under our constraint.
5. **Monitor partner-program signals** quarterly (WIPO, UKIPO, CIPO).

---

## Files in this research wave

- [`00-summary.md`](00-summary.md) — this file
- [`kipo-kipris-plus.md`](kipo-kipris-plus.md) — KIPO Korea
- [`wipo-global-databases.md`](wipo-global-databases.md) — PATENTSCOPE + Global Brand DB + Global Design DB
- [`dpma-germany.md`](dpma-germany.md) — DPMA Germany
- [`ukipo-uk.md`](ukipo-uk.md) — UKIPO United Kingdom
- [`cipo-canada.md`](cipo-canada.md) — CIPO Canada

## Not researched in this wave (queued)

- **INPI France** — Open Data API exists for patents and TMs. Recommended for round two given EPO OPS already covers French patent filings transitively, but INPI France TMs and designs would be a gap-fill.
- **TIPO Taiwan** — gov.tw Open API portal hosts TIPO endpoints; needs confirmation of public availability and ToS.
- **CNIPA China** — limited public APIs; high operational complexity (geofencing, language); deferred.
- **Rospatent Russia** — APIs exist but politically and operationally fraught; not recommending.
