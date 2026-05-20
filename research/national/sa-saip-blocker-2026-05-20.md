# SAIP Saudi Arabia — fee-schedule connector: research blocker

**Status:** Cannot ship `SA/SAIP/Fees` patent/trademark/design FeeSchedule
connectors today. Halting at the research-gap boundary per task
instructions ("DO NOT invent fees").

**Date:** 2026-05-20
**Worktree branch:** `worktree-agent-a24752035b2fa52a1`
**Off-ramp recommended by upstream research:** [`research/national/sa-saip.md`](research/national/sa-saip.md) §4 — Option A (service-catalog reference document) ships, not a FeeItem connector.

---

## §1 Why we're stopped

The task requires three `FeeSchedule` objects (patent / trademark /
design) each with a real `Decimal` amount on every `FeeItem`, sourced
from a live URL, with at least filing + renewal categories present.

That data is not extractable from any reachable source today.

### Live probes 2026-05-20 (US residential egress)

| Host | Result |
|---|---|
| `https://www.saip.gov.sa/en/` | ConnectTimeout (curl exit 28, 15s) — confirms 2026-05-19 finding |
| `https://eservices.saip.gov.sa/` | ConnectTimeout (curl exit 28, 15s) |
| `https://uqn.gov.sa/` | ConnectTimeout (curl exit 28, 15s) — Umm al-Qura gazette, primary statutory source |
| `https://tm.saip.gov.sa/` | (not re-tested today; same finding 2026-05-19) |

Packet-level block — no TLS handshake reached. This is **not** a
Cloudflare 403 / WAF challenge / auth gate; it is whole-CIDR or whole-AS
filtering at the SAIP edge. Mitigations require Saudi-egress or paid
stealth-proxy infrastructure (Option B in the upstream research),
neither of which is provisioned for this session.

### Reachable secondary sources — insufficient for FeeItem-grade data

* **WIPO Lex 19743** — Implementing Regulations of the Law of Patents,
  Layout-Designs, Plant Varieties, and Industrial Designs (consolidated
  to SAIP Board Decision No. 5/8/2019 of 9 May 2019). PDF reached via
  signed CloudFront URL on `wipolex-res.wipo.int` after browser-style
  request from the WIPO Lex HTML detail page (signed-URL expires
  2026-05-21 ≈; harvested 2026-05-20).

  Inspection of the 49-page consolidated text: the **only** monetary
  fee table is page 49, titled *"A table of the expenses stipulated in
  these regulations"* — three rows, **procedural fees only**:

  | # | Item | Individuals (SAR) | Institutions (SAR) |
  |---|---|---|---|
  | 1 | Seek correction or addition of precedence | 400 | 800 |
  | 2 | Petition to return the application process | 1,000 | 2,000 |
  | 3 | Seek extension of time limit | 300 | 600 |

  **There is no filing / examination / grant / annuity / renewal fee
  table in this consolidated document.** The substantive provisions
  reference "fees" but do not enumerate amounts — those are set by
  Board resolution and applied dynamically at filing time in the
  eServices portal. WIPO Lex 23123 (the principal Law M/27) is the
  primary statute and likewise does not enumerate tariff amounts.

  Three procedural fees with a single individual-vs-institution split
  do not satisfy the task's quality bar of *filing + renewal* coverage
  across three rights.

* **Wayback Machine snapshots of `saip.gov.sa`** — closest archived
  service-catalog page is `/web/20250125031914/...services/` (2025-01-25).
  Extracted text body is ~1.1 KB (SPA shell, not server-rendered fee
  data); no numeric fee amounts present. Right-specific paths
  (`/en/services/patents`, `/en/services/trademarks`,
  `/en/industrial-design`) have **no Wayback snapshots at all**.

* **Research-anchored amounts** in
  [`research/national/sa-saip.md`](research/national/sa-saip.md) §4:
  TM filing SAR 1,000/class; TM publication-for-opposition SAR 500;
  TM renewal publication ~USD 310 (post-June-2022 Board resolution).
  These are user-sourced notes, not citations to a fetchable primary
  source — and even taken at face value would cover only the
  trademark schedule, not patents or designs.

### Architectural finding (from upstream research, confirmed)

SAIP does **not publish a consolidated fee schedule analogous to**:

* OEPM Spain `TASAS_y_PRECIOS_PUBLICOS.pdf` (17 pages, every right)
* INPI France `download-document?id=20516` (every right)
* IMPI Mexico `Acuerdo.Tarifa.12.05.23.pdf` (every right)
* IPOS Singapore P/TM/D forms-and-fees HTML pages
* TÜRKPATENT Turkey gazette + 3 HTML mirrors

Instead, **fees are calculated dynamically at the point of filing in
the eServices portal**, with statutory authority fragmented across
(a) the principal Law M/27, (b) its Implementing Regulations, and
(c) periodic SAIP Board resolutions formally published in the
Umm al-Qura gazette (`uqn.gov.sa` — also blocked).

This means even with Saudi egress / a stealth proxy in place, the
deliverable shape is not "scrape a static schedule" — it would require
reverse-engineering the eServices SPA fee-calculation endpoint (similar
to the ILPO Israel ecom.gov.il work, with the additional layer of
Nafath digital-identity gating that may block foreign-developer access
entirely regardless of egress IP).

---

## §2 What's missing to unblock

In rough order of how decisively they would unblock:

1. **Direct extraction from `eservices.saip.gov.sa` fee-calculation
   endpoint** — requires either:
   * Saudi-egress (Cloud Run with SA-resident IP, or a stealth-proxy
     provider with KSA pool such as Bright Data residential / Smartproxy
     KSA, ~$30–300/mo entry tier), **and**
   * resolving whether Nafath digital-identity gating blocks access for
     non-resident developer accounts. If Nafath gates the entire portal
     (not just transactional endpoints), foreign-developer access is
     structurally infeasible regardless of egress routing.

2. **Umm al-Qura gazette (`uqn.gov.sa`) access** for the post-2019
   SAIP Board resolutions — same Saudi-egress requirement; gazette
   itself is the statutory source of record but is blocked at the same
   packet level as SAIP.

3. **Local KSA counsel** to provide the current operative tariff
   directly (the user's existing notes anchor TM filing / publication /
   renewal amounts but not patent or design line items).

4. **Open Saudi Data initiative** — SAIP has discussed publishing a
   consolidated downloadable service-catalog PDF (see
   [`research/national/sa-saip.md`](research/national/sa-saip.md) §4
   Option C). No published timeline as of 2026-05-19. Quarterly check
   of `saip.gov.sa/en/news/` (also blocked) would catch this; proxy via
   Wayback or user reports.

5. **Cloud-egress reachability probe** (Cloud Run / EU / Asia egress)
   to confirm whether the SAIP block is US-CIDR-specific or applies
   uniformly to all non-Saudi egress. Would change the proxy-
   infrastructure conversation if Asia or EU egress reaches.

---

## §3 What I did not do and why

* **Did not create `src/patent_client_agents/fees/scrapers/saip.py`** —
  every code path led to either (a) inventing fee amounts not anchored
  to a fetchable primary source, or (b) shipping a `FeeSchedule` with
  three procedural rows and calling it complete, which would silently
  misrepresent SAIP coverage in `fees/registry.py` and atlas downstream.

* **Did not register `"SAIP"` in `fees/registry.py`** — registering a
  scraper that cannot return real data would break the registry's
  invariant that every registered route resolves to a populated
  `FeeSchedule` on demand.

* **Did not write test fixtures from the 2019 Implementing
  Regulations PDF** — the three procedural rows on page 49 are real
  and verifiable, but emitting them as the entirety of `SA/SAIP/Patent`
  would imply SAIP charges nothing for filing/examination/grant/
  annuities, which is false.

* **Did not author `RESEARCH_GAPS.md` as a substitute deliverable**
  beyond this note — the upstream research already has
  [`research/national/sa-saip.md`](research/national/sa-saip.md) as
  the canonical living document and
  [`FEES_TOP30_GAP.md`](FEES_TOP30_GAP.md) tracks SAIP's gap
  prominently; duplicating that into a third doc would create drift.

---

## §4 Recommended path forward

Option A in the upstream research (service-catalog reference document)
is still the correct v1. Implementing it would require:

* A new shape in `patent_client_agents.fees` (not `FeeSchedule`) —
  closest sibling is the `StaticLawCorpus` pattern used by
  `dpma_statutes` / `legifrance_ip`, but tagged explicitly as
  reference-grade with the "fee calculated at filing time" caveat.
* A separate atlas/manifest entry that does not silently inherit the
  FeeSchedule contract.
* Coordinating with `coverage/sources.yaml` so the SAIP row exists
  with the correct yellow rating and `kind: reference` (or analogous)
  marker, not under the regular fees connector kind.

That work is **out of scope for the current task** (which is shaped
around `scrape_saip_*()` functions emitting `FeeSchedule`); reshaping
the deliverable contract should be a separate decision by the
maintainer, not a freelance pivot during a connector PR.

---

## §5 Related artifacts

* [`research/national/sa-saip.md`](research/national/sa-saip.md) —
  authoritative SAIP research synopsis (2026-05-19), Options A/B/C
  analysis, rating rationale, statutory citations
* [`FEES_TOP30_GAP.md`](FEES_TOP30_GAP.md) — top-30 coverage gap
  doc, SAIP row in §1 and §3.4
* [WIPO Lex SA legislation listing](https://www.wipo.int/wipolex/en/main/profile/SA)
* [WIPO Lex 23123 — Law on Patents, Layout-Designs, Plant Varieties, and Industrial Designs (Royal Decree M/27, 2004)](https://www.wipo.int/wipolex/en/legislation/details/23123)
* [WIPO Lex 19743 — Implementing Regulations (consolidated to 2019-05-09)](https://www.wipo.int/wipolex/en/legislation/details/19743)
