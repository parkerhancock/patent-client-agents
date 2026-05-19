# Africa wave — synthesis

**Date:** 2026-05-18
**Researchers:** six general-purpose subagents (one per jurisdiction, batched 2-at-a-time to dodge parallel-agent TPM stall)
**Scope:** Determine whether four major African national IP offices (ZA / EG / NG / MA) and the two African regional IP organizations (ARIPO / OAPI) expose public REST/JSON/XML APIs we can proxy at runtime, zero infrastructure on our side.
**Constraint:** zero on-disk infrastructure beyond an HTTP client.

---

## TL;DR

**6 out of 6 are red.** The entire surveyed African IP-office surface has no proxy-suitable public API. But the **transitive layer** salvages the patent side: EPO OPS / INPADOC ingests ARIPO (`AP`) and OAPI (`OA`) regional grants, so our existing `epo_ops` connector already covers the highest-leverage patent data from ~40 African states without any Africa-native connector work.

| Jurisdiction | Verdict | Blocker | Detail |
|---|---|---|---|
| **ZA** South Africa / CIPC | 🔴 red_blocked | IPS API "Coming Soon" on APIVerse Hub; live register is ASP.NET HTML; eServices ToU prohibits derived works | [za-cipc.md](za-cipc.md) |
| **EG** Egypt / EGYPO + ITDA | 🔴 red_no_api | Patents on hosted WIPO PUBLISH (HTML only); TM gazette PDF only; **Law 163/2023 dissolves both offices into new EAIP** (transition in progress) | [eg-egypto.md](eg-egypto.md) |
| **NG** Nigeria / FMITI + NCC | 🔴 red_no_api | Login-gated SvelteKit portal + ASP.NET copyright portal; ToU forbids reproduction/redistribution; NIPCOM bill not yet enacted | [ng-fmiti.md](ng-fmiti.md) |
| **MA** Morocco / OMPIC | 🔴 red_no_api | HTML-only register portals; paid `directinfo.ma` subscription is per-document B2C/B2B, no API; despite being the **only African EPO Validation State**, no public IP API | [ma-ompic.md](ma-ompic.md) |
| **ARIPO** anglophone regional | 🔴 red_no_api | KIPO-built eService HTML redirects to WIPO Publish HTML; **ARIPO Journal PDFs only**; no developer program | [aripo.md](aripo.md) |
| **OAPI** francophone regional | 🔴 red_no_api | Register on **bare-IP HTTP-only WoPublish** (`195.24.202.12:9092`, no TLS); BOPI gazette PDF only; 2024 e-filing portal is write-only and agent-gated | [oapi.md](oapi.md) |

---

## The pattern is the finding

**Zero African IP offices appear in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)** (verified across all six probes — 0 entries across CIPC, EGYPO, ITDA, FMITI, NCC, OMPIC, ARIPO, OAPI). The catalog has 179+ entries from DPMA / EPO / EUIPO / IP Australia / JPO / KIPO / UPRP / USPTO / WIPO / Kazakhstan — and not one from Africa.

Across all six jurisdictions the public IP surface is one of:

1. **HTML-only search UI** — every office. CIPC's `iponline.cipc.co.za`, EGYPO's hosted WoPublish, OMPIC's `search.ompic.ma`, ARIPO's eService, OAPI's bare-IP WoPublish.
2. **PDF-only gazette** — EGYPO TM gazette monthly PDFs, ARIPO Journal monthly PDFs, OAPI BOPI gazette, OMPIC Bulletin.
3. **Account-gated transactional portals** — NG (login-walled SvelteKit), OAPI 2024 e-filing (agent-gated, write-only), CIPC eServices (per-client deployment terms).
4. **Paid subscription with no API affordance** — OMPIC's `directinfo.ma` (per-document fee schedule, B2C/B2B subscription, no machine credentials).
5. **Promised-but-not-shipped API surfaces** — CIPC IPS API "Coming Soon" on APIVerse Hub, NIPCOM bill not yet enacted, EAIP consolidation in progress.

The structural reasons differ by jurisdiction — capacity constraint (NG, EG), policy stance (CIPC's eServices T&Cs), ongoing reorgs (EG/EAIP, NG/NIPCOM, CIPC IPS) — but the operational result is uniform: **no zero-infra proxy path through any African office exists today.**

## What's salvageable through existing connectors

The transitive coverage findings are the wave's real value:

### ARIPO → EPO OPS via INPADOC

ARIPO grants are published under WIPO ST.3 country code **`AP`**, and **EPO OPS / INPADOC ingests them**. Our existing `epo_ops` connector therefore already provides bibliography + family + legal events for ARIPO regional grants — covering the patent layer for ~20 anglophone African states transitively. No Africa-native connector required for ARIPO patents.

### OAPI → EPO OPS via INPADOC (likely)

OAPI grants are published under country code **`OA`**. EPO OPS INPADOC routinely includes `OA`-coded records; the OAPI synopsis confirms PCT-routed OAPI patents flow through PATENTSCOPE + EPO OPS. **For the 17 OAPI member states (BJ/BF/CM/CF/TD/KM/CG/CI/GQ/GA/GN/GW/ML/MR/NE/SN/TG), this is structurally the *only* machine-readable patent surface** — OAPI is a unitary office; no national substitute exists. So while OAPI direct is red, the OAPI-via-EPO-OPS path is the canonical machine route for those 17 states.

### Madrid TMs designating African members → WIPO Madrid Monitor

Madrid Protocol African members carrying Madrid IR coverage (confirm-then-use list):
- **Members:** Algeria, Botswana, Egypt, Eswatini, Gambia, Ghana, Kenya, Lesotho, Liberia, Madagascar, Malawi, Mauritius, Morocco, Mozambique, Namibia, OAPI (since 2015-03-05), Rwanda, São Tomé and Príncipe, Sierra Leone, Sudan, Tunisia, Zambia, Zimbabwe.
- **Notable non-members (refuted from prior assumptions):** **South Africa is NOT a Madrid member** as of 2026-05-18 (the SA Madrid accession has slipped since 2003 approval; the Trade Marks Amendment Bill targeted September 2025 but has not advanced). **Nigeria is NOT a Madrid member** despite long-running rumors — confirmed via the live WIPO members list.

WIPO Madrid Monitor handles IR-level data; **national TM file histories and oppositions are not transitively recoverable** for any African jurisdiction.

### Genuine unrecoverable gaps

Even with full transitive coverage, the following remain inaccessible without per-office paid contracts or a future partner program:

- **National-only patents** without EP/PCT counterparts (ZA, EG, NG, MA national filings not routed through PCT or EPO).
- **All African designs** — Hague Agreement covers only members (MA from 2022-04-22 under the Geneva Act, NG from 2017-12-12, OAPI under separate route, EG/ZA not members).
- **All African TM file histories** — Madrid Monitor sees IR-level designation status only; national prosecution + opposition records are opaque.
- **All African copyrights** — uniformly behind login walls or PDF-only.
- **All gazette text** (ARIPO Journal, OAPI BOPI, EGYPO TM gazette, OMPIC Bulletin) — PDFs only; not parseable at machine fidelity without local OCR/extraction infrastructure (violates zero-infra).

## Context corrections discovered during the wave

Several context bullets the prompts asked agents to verify were refuted by primary sources. Logging these so they don't propagate into future work:

| Claim (as written in research prompts) | Reality (per primary source, 2026-05-18) | Source |
|---|---|---|
| **South Africa joined Madrid 2018-01-30** | SA is **still not a Madrid member**. Accession approved 2003 but has slipped repeatedly; Trade Marks Amendment Bill targeted September 2025 executive submission — not yet acceded. | [WIPO Madrid members list](https://www.wipo.int/madrid/en/members/) |
| **Nigeria joined Madrid 2023-12-02** | NG is **not** a Madrid member as of 2026-05-18. | [WIPO Madrid members list](https://www.wipo.int/madrid/en/members/) |
| **Nigeria PCT accession 2005-05-08** | Correct date is **2005-02-08** (per TREATY/PCT/169). | [WIPO PCT/169 notification](https://www.wipo.int/treaties/en/notifications/pct/treaty_pct_169.html) |
| **Morocco Hague Agreement since 1957** | MA's accession under the current **1999 Geneva Act** was deposited **2022-04-22**. The "1957" date likely confused historical 1934/1960-Act engagement with the current instrument. | [WIPO Hague member profile](https://www.wipo.int/treaties/en/registration/hague/) |
| **ARIPO has 21 member states; 4 protocols** | ARIPO has **22 member states** (Seychelles joined 2022; Mauritius acceded to Harare 2025-08-27) and **5 protocols** — the **Kampala Protocol** on voluntary copyright registration was adopted in 2024. | [ARIPO Member States page](https://www.aripo.org/member-states); [Kampala Protocol 2024 PDF](https://www.aripo.org/storage/resources-protocols/1715840913_Kampala%20Protocol%20on%20Voluntary%20Registration%20of%20Copyright%20and%20Related%20Rights%20(2024).pdf) |
| **Egypt's IP authority is split (EGYPO under ASRT + ITDA TM/Designs)** | Currently split, but **Law 163 of 2023 dissolves both into a new Egyptian Authority for Intellectual Property (EAIP)** reporting to the Prime Minister, with a 2024-08-05 transition deadline. As of 2026-05-18 the legacy sites still serve; EAIP has no discoverable canonical web property yet. | [WIPO Lex Law 163/2023](https://www.wipo.int/wipolex/en/legislation/details/22398) |

## Implications for the roadmap

1. **Do not build Africa-native register connectors.** All six surveyed jurisdictions are red. The CONNECTOR_STANDARDS.md zero-infra constraint cannot accommodate any of them today.
2. **Document the transitive layer in the atlas.** Africa is *not* an absence in the catalog — it's covered through `epo_ops` (AP + OA codes) and `WIPO Madrid Monitor` for the right subset of states. Atlas cards for the 30+ African states should point to the transitive route, not "no coverage."
3. **No new substantive-law corpora from this wave.** Unlike the 2026-05-18 secondary-nationals wave (which surfaced 7 multi-statute-corpus candidates), the African research surfaced fewer immediately corpus-shaped opportunities: WIPO Lex carries the statutory texts for all six jurisdictions already, and our existing `wipo_lex` connector is the right surface.
4. **Watch items** (recheck quarterly): SA Madrid accession progress; NG NIPCOM bill enactment; EG EAIP consolidation + new web presence; CIPC IPS API GA on APIVerse Hub; OAPI BOPI machine-readable feed (currently PDF only); ARIPO API program (none signaled).
5. **Paid-tier deferral:** None of the surveyed offices offer a paid API tier that would unlock proxy-suitable access. OMPIC's `directinfo.ma` is per-document B2C/B2B, not machine-credential. There is no DPMAconnectPlus-equivalent paid contract path for any of these jurisdictions.

## Recommendation

1. **Close the Africa proxy-connector backlog.** Add `connector_status: red_no_api` (or `red_blocked` for ZA/CIPC specifically) entries to `coverage/sources.yaml` for ZA/EG/NG/MA/ARIPO/OAPI, citing this wave.
2. **Add atlas cards** for the 4 nationals + 2 regionals pointing to: (a) `epo_ops` as the patent surface where applicable, (b) `WIPO Madrid Monitor` as the TM surface for member states, (c) the WIPO Lex statute corpus for substantive law, and (d) `red_no_api` for everything else.
3. **Update [`BACKLOG.md`](../../BACKLOG.md) reconciliation log** with the six new findings — particularly the Madrid corrections (SA, NG) and the EAIP consolidation watch item.
4. **No further African coverage waves needed before recheck quarterly.** Egypt/EAIP and SA/CIPC IPS API are the two genuine watch items; the rest of the continent's posture is structural and unlikely to shift on a months timeframe.

---

## Files in this research wave

- [`00-summary.md`](00-summary.md) — this file
- [`za-cipc.md`](za-cipc.md) — South Africa / CIPC
- [`eg-egypto.md`](eg-egypto.md) — Egypt / EGYPO + ITDA (EAIP transition flagged)
- [`ng-fmiti.md`](ng-fmiti.md) — Nigeria / FMITI Patents+Designs + Trademarks + NCC + NIPCOM
- [`ma-ompic.md`](ma-ompic.md) — Morocco / OMPIC (EPO Validation State)
- [`aripo.md`](aripo.md) — ARIPO (anglophone regional, 22 members, 5 protocols)
- [`oapi.md`](oapi.md) — OAPI (francophone regional, 17 unitary states)
