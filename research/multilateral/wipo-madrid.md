# WIPO Madrid System (WO/WIPO/Madrid)

**Layer:** multilateral
**Jurisdiction:** n/a (Madrid Protocol — 116 members, 132 countries)
**Issuing body:** World Intellectual Property Organization (WIPO),
International Bureau (IB)
**Rights administered:** trademark (international registrations under
the Madrid Agreement + Madrid Protocol)
**Working languages:** English, French, Spanish (Common Regulations Rule 6)
**Connector status:** skipped (ToS-blocked; no zero-infra path)
**Last verified:** 2026-05-16
**Manifest entry:** not yet listed in [`coverage/sources.yaml`](../../coverage/sources.yaml) — skipped pending a public WIPO Madrid search API.

**Detail surveys:**
- [`connectors/wipo.md`](../connectors/wipo.md) — 2026-05 cross-asset
  WIPO survey (Madrid covered alongside PATENTSCOPE, Hague, Lisbon,
  Brand DB, etc.)
- [`waves/2026-05-16-coverage-batch-2/wipo-madrid.md`](../waves/2026-05-16-coverage-batch-2/wipo-madrid.md)
  — current API-discovery research (this synopsis distills it)

**Higher layers covering this office transitively:**
- [WIPO Global Brand Database](https://branddb.wipo.int/) — aggregates
  Madrid IRs alongside national TMs. Also red (see
  [`waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md`](../waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md)).
- National TM registers via Madrid designation chains (USPTO TSDR for
  US designations, EUIPO TMView for EU designations, IP Australia for
  AU designations, etc.). These are reachable through their own APIs.

---

## §1 Mission

The Madrid System lets a trademark holder file a **single international
application** in one language and one set of fees to seek protection in
up to 132 countries through the WIPO International Bureau. The Madrid
Agreement (1891) and Madrid Protocol (1989) define the legal
infrastructure; the IB runs the
[International Register](https://www.wipo.int/en/web/madrid-system) and
publishes registration data through Madrid Monitor and (post-2024) the
eMadrid Find-and-Monitor service. Agents care because the Madrid IR
number is the canonical identifier that links national TM records back
to a single international filing.

## §2 What's unique here

- The **IR number** — cross-jurisdiction identifier tying US, EU, JP,
  etc. designations to one filing.
- The full **designation chain** (which countries, when, under Agreement
  vs Protocol, with which Nice classes).
- **Subsequent designations** (Article 3ter additions).
- **Transformation and replacement** events (Article 4bis; five-year
  "central attack" conversion to national applications).
- **Provisional refusals, refusals, final decisions, declarations of
  grant** by designated offices on a standardized IB timeline.

## §3 Programmatic surfaces

### Madrid Monitor — public UI

| Field | Value |
|---|---|
| Endpoint | [`https://www3.wipo.int/madrid/monitor/en/`](https://www3.wipo.int/madrid/monitor/en/) |
| Auth | none |
| Format | HTML (UI) |
| Rate limit | "≤ 10 search-related actions per minute per IP" |
| ToS posture | proxy-prohibited (automated queries forbidden) |
| Verdict | 🔴 red |
| Primary source | [Madrid Monitor Terms of Use (July 2025)](https://www3.wipo.int/madrid/monitor/en/terms.jsp) |

ToS §5 prohibits bulk acquisition; §6 prohibits automated queries.
Even though the UI is free, server-side proxying for end-users is not
permitted. Slated for decommissioning once eMadrid Find-and-Monitor
reaches parity.

### Madrid Monitor — undocumented per-IR XML endpoints

| Field | Value |
|---|---|
| Endpoint | `GET /madrid/monitor/api/v1/data/{IRN}` and `/api/v1/tmxml/data/{IRN}` on `www3.wipo.int` / `www.wipo.int` |
| Auth | none |
| Format | XML (WIPO ST.66 / Romarin v1.3 on `/data/`; TM-View on `/tmxml/data/`) |
| Rate limit | inherits Madrid Monitor fair-use cap |
| ToS posture | proxy-prohibited (same Madrid Monitor ToS applies) |
| Verdict | 🔴 red |
| Primary source | confirmed by probe 2026-05-16; example record [`/api/v1/data/WO500000000789955`](https://www3.wipo.int/madrid/monitor/api/v1/data/WO500000000789955) |

Lookup-by-IRN only — no documented search params. Not advertised on the
[WIPO API Catalog](https://apicatalog.wipo.int/) and could disappear in
the Find-and-Monitor migration without notice.

### eMadrid "Find and Monitor"

UI-only successor to Madrid Monitor at
[`madrid.wipo.int/findmonit/quick-search`](https://madrid.wipo.int/findmonit/quick-search).
Auth: none for search, WIPO User Account for watchlists/alerts. Format:
HTML; export PDF/CSV/XML. ToS inherits the Madrid System family —
**🔴 red, proxy-prohibited.** No public REST/JSON API behind it as of
2026-05-16; primary source
[Finding and Monitoring International Trademark Registrations](https://www.wipo.int/en/web/madrid-system/find-and-monitor-international-trademark-registrations).

### Madrid Monitor bulk XML (UN ICC FTP)

CHF 30,000/yr paid contract; daily `yyyymmdd.zip` deltas + images via UN
International Computing Centre anonymous FTP; format ST.66 XML + TIFF.
**🔴 red** — violates zero-infra constraint by definition (we'd host an
index, not proxy). Primary source
[Download Madrid Monitor update files](https://www.wipo.int/madrid/en/monitor/download.html).

### WIPO API Catalog — no Madrid entries

[`apicatalog.wipo.int/api/apis/all`](https://apicatalog.wipo.int/api/apis/all)
probe 2026-05-16: 181 APIs total, 4 WIPO-org (Pearl, Hague HWS, GBD
image, IPCPUB). No Madrid search API listed — primary-source
confirmation that WIPO does not publish one.

### Madrid Office Portal (MOP) / Madrid e-Filing (MeF)

Partner-IP-office-only filing and document-exchange surfaces, not search
APIs — irrelevant to a third-party proxy. See
[`mm_ld_wg_23_roundtable_1_ib.pdf`](https://www.wipo.int/edocs/mdocs/madrid/en/mm_ld_wg_23/mm_ld_wg_23_roundtable_1_ib.pdf).

## §4 Fees

Madrid fees are charged in CHF and combine a basic fee + complementary
or individual fee per designated office + supplementary fee per class
beyond three. Renewal cycle is 10 years. Individual fees move per WIPO
Information Notices, so the fee calculator is the only authoritative
source at any given time.

- **Official schedule:** [Madrid System Schedule of Fees](https://www.wipo.int/en/web/madrid-system/fees/sched)
- **Fee calculator:** [Madrid fee calculator](https://madrid.wipo.int/feecalcapp/)
- **Fees & payments hub:** [Madrid System — fees](https://www.wipo.int/en/web/madrid-system/fees)
- **Individual fees (per Contracting Party):** [Madrid — individual fees](https://www.wipo.int/madrid/en/fees/ind_taxes.html)

## §5 Connector strategy

### What we cover today

Nothing direct for Madrid. We cover Madrid designations transitively
through national TM connectors:

- `patent_client_agents.uspto_odp` — US designations of Madrid IRs land
  in TSDR as US TM applications/registrations.
- `ip_australia_trademarks` — AU designations via the IP Australia
  Trade Marks OAuth API.
- (Planned — see [`coverage/atlas.json`](../../coverage/atlas.json)) —
  EUIPO TMView for EU designations.

### What we should add (if anything)

Nothing for now. Any Madrid connector would require one of:
(1) the paid bulk **ICC FTP** mirror — violates zero-infra;
(2) proxying Madrid Monitor — violates [ToS §5/§6](https://www3.wipo.int/madrid/monitor/en/terms.jsp);
or (3) reselling a commercial Madrid aggregator — out of scope.
A BYOK config path for clients with their own bulk subscription is
possible but not on the roadmap.

### What we should NOT add

- **Madrid Monitor scraping or per-IR XML proxying.** ToS explicitly
  forbids automated queries and re-publication to "another service
  provider host or publisher" per
  [Madrid Monitor Terms of Use (July 2025)](https://www3.wipo.int/madrid/monitor/en/terms.jsp).
  The undocumented `/api/v1/data/{IRN}` and `/api/v1/tmxml/data/{IRN}`
  endpoints look tempting (no auth, ST.66 XML out) but using them
  programmatically is the exact thing §6 prohibits.
- **A Madrid bulk-XML mirror.** CHF 30,000/yr plus we'd be hosting a
  search index — explicitly forbidden by our connector standards
  (zero-infra rule).
- **The Global Brand Database** as a Madrid back-door. Also red — see
  [`waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md`](../waves/2026-05-16-registered-ip-discovery/wipo-global-databases.md).

### Next steps

- Monitor for a public WIPO Madrid REST/JSON API in the eMadrid
  Find-and-Monitor decommissioning timeline. WIPO has published its own
  [WIPO Standard on Web API](https://www.wipo.int/meetings/en/doc_details.jsp?doc_id=415578)
  pushing REST/JSON — Madrid is a candidate but not announced.
- Watch the
  [WIPO API Catalog](https://apicatalog.wipo.int/api/apis/all)
  for a new Madrid entry under `organization == "WIPO"`. We probe this
  monthly as a side-effect of our broader sweep.

## §6 Open questions

- **Will eMadrid Find-and-Monitor ship a public API?** WIPO's webapi
  standard suggests it should, but no announcement as of 2026-05-16.
  Worth a direct email to `madrid.assistance@wipo.int`.
- **Are the undocumented per-IR XML endpoints stable under the
  Find-and-Monitor migration?** No commitment is published; they could
  break with the Madrid Monitor decommissioning.
- **Does Madrid Monitor expose a search endpoint behind the JSF UI we
  haven't found?** A 2026-05-16 probe of `/api/v1/search?q=test` was
  404; a deeper look at the UI's actual XHR traffic may reveal more.
- **What is the smallest paid Madrid product?** The
  [Download page](https://www.wipo.int/madrid/en/monitor/download.html)
  lists only the CHF 30,000 full feed; is there a per-jurisdiction or
  per-day pricing tier WIPO offers on request?

## §7 References

- [WIPO Madrid System homepage](https://www.wipo.int/en/web/madrid-system)
- [Madrid Monitor (UI)](https://www3.wipo.int/madrid/monitor/en/)
- [Madrid Monitor Terms of Use (July 2025)](https://www3.wipo.int/madrid/monitor/en/terms.jsp)
- [Madrid Monitor download page (bulk XML / ICC FTP)](https://www.wipo.int/madrid/en/monitor/download.html)
- [eMadrid portal](https://madrid.wipo.int/) and
  [Find and Monitor](https://madrid.wipo.int/findmonit/quick-search)
- [Finding and Monitoring International Trademark Registrations](https://www.wipo.int/en/web/madrid-system/find-and-monitor-international-trademark-registrations)
- [Madrid System Schedule of Fees](https://www.wipo.int/en/web/madrid-system/fees/sched) and [Fee Calculator](https://madrid.wipo.int/feecalcapp/)
- [Individual fees per Contracting Party](https://www.wipo.int/madrid/en/fees/ind_taxes.html)
- [WIPO API Catalog](https://apicatalog.wipo.int/) and [JSON index](https://apicatalog.wipo.int/api/apis/all)
- [WIPO B2B Developer Portal](https://b2b.wipo.int/catalog/all)
- [WIPO Standard on Web API](https://www.wipo.int/meetings/en/doc_details.jsp?doc_id=415578)
- [Madrid e-Filing and Madrid Office API — IB roundtable Sep 2025](https://www.wipo.int/edocs/mdocs/madrid/en/mm_ld_wg_23/mm_ld_wg_23_roundtable_1_ib.pdf)
- [Resources for IP Offices of Madrid System Members](https://www.wipo.int/en/web/madrid-system/contracting_parties/resources-for-intellectual-property-offices-of-madrid-system-members)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-16 | Initial synopsis. Verdict: red, skipped. | Distilled from [`connectors/wipo.md`](../connectors/wipo.md) §2 and [`waves/2026-05-16-coverage-batch-2/wipo-madrid.md`](../waves/2026-05-16-coverage-batch-2/wipo-madrid.md) |
