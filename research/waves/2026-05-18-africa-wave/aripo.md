# African Regional Intellectual Property Organization (ARIPO) — Patents/Designs/TMs/Plant Varieties API Discovery

- **Date:** 2026-05-18
- **Scope:** ARIPO regional rights under the **Harare** (patents, utility models, industrial designs), **Banjul** (trademarks), **Arusha** (plant varieties — in force [2024-11-24](https://www.aripo.org/news/The+Arusha+Protocol+for+the+Protection+of+New+Varieties+of+Plants+Officially+Comes+into+Force-1732618853)), **Swakopmund** (TK/folklore — in force [2015-05-11](https://www.wipo.int/wipolex/en/treaties/details/971)), and the newly-discovered **Kampala** Protocol (voluntary copyright registration, 2024).
- **TL;DR:** **🔴 red_no_api.** ARIPO publishes IP data through two HTML-only front ends — the legacy KIPO-built [eService IPDL](https://eservice.aripo.org/pdl/pqs/quickSearchScreen.do) and the WIPO-built [Regional IP Database (`regionalip.aripo.org/wopublish-search`)](https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/) — and the [ARIPO Journal as monthly PDFs](https://eservice.aripo.org/ppb/pjd/PPBJournalViewList.do). No registered REST/JSON API exists; ARIPO does **not** appear in the [WIPO IP API Catalog](https://apicatalog.wipo.int/) and is not listed as having an open API in [WIPO INSPIRE's AP jurisdiction profile](https://inspire.wipo.int/system/files/juri/ARIPO.pdf). The Regional IP Database is built on **WIPO Publish** (same platform as many national offices) — same shape, same lack of public API. Transitive coverage is partial: WIPO Publish ingested IPAS data from ~13 anglophone members but only ~5 national journals are searchable.

---

## §1 Endpoints

| Host | Right(s) | Shape | Probe result |
|---|---|---|---|
| `www.aripo.org` | Corp, protocols, member-state list, news | HTML + PDF | 200; LiteSpeed; permissive [robots.txt](https://www.aripo.org/robots.txt) (`Disallow:` empty); no machine surface |
| `eservice.aripo.org/pdl/pqs/quickSearchScreen.do` | Quick search (AP + national IPDL) | HTML form (JSP, Apache-Coyote/1.1, JSESSIONID, KIPO-built ca. 2014) | 200; on submit, JS `onSubmit()` **redirects users to `regionalip.aripo.org`** (`alert(...)`+`window.open("http://regionalip.aripo.org/wopublish-search/public/patents?&query=OFCO:AP")`); native IPDL search reportedly broken per [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/ARIPO.pdf) ("the latter is currently loading and a search gives no results") |
| `eservice.aripo.org/pdl/pah/advancedSearchScreen.do` | Advanced search | HTML form | 200; same KIPO platform; same redirect to WIPO Publish |
| `eservice.aripo.org/ppb/pjd/PPBJournalViewList.do` | **ARIPO Journal** (gazette) | HTML index → PDF downloads | 200; monthly PDFs in English, coverage **2015→present** per [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/ARIPO.pdf) |
| `eservice.aripo.org/pes/...` | Online filing, e-payment, notifications, dockets | HTML behind sign-in (transactional only) | 200; account-walled; no third-party API per [ARIPO eService demo, AfrIPI 2021](https://internationalipcooperation.eu/sites/default/files/afripi-docs/AfrIPI_28apr2021_Agenda%20Item%205%20-%20Demonstration%20of%20%20ARIPO%20eServices.pdf) |
| `regionalip.aripo.org/wopublish-search/public/patents?query=OFCO:AP` | **Regional IP Database** (WIPO Publish) — AP rights + 12 member states' IPAS exports | HTML (WIPO Publish UI) | Reachable from public Internet (HTTP 302→`/public/home`); rate-limited / blocks Cloud-Run-like egress on HTTPS; HTTP-only on port 80; no documented JSON endpoint. Coverage per [ARIPO success story](https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/): "ARIPO, Botswana, Gambia, Ghana, Kenya, Malawi, Mozambique, Namibia, Rwanda, Tanzania, Uganda, Zambia and Zimbabwe" |
| `data.aripo.org`, `api.aripo.org` | — | — | **DNS resolves to wildcard, no matching SSL cert** (TLS handshake fails). No public data/API subdomain exists. |
| `apicatalog.wipo.int` | WIPO IP API Catalog | — | **No ARIPO entries** ([catalog](https://apicatalog.wipo.int/), launched [2024](https://www.wipo.int/en/web/standards/w/news/2024/news_0001)) |

## §2 Auth

No developer program. The eService portal has [Sign in](https://www.aripo.org/login) / [Register](https://www.aripo.org/register), but those credentials gate **transactional** access (filing, e-payment, dockets) — not bulk read or a public API. Both search front ends (`eservice.aripo.org/pdl/...` and `regionalip.aripo.org/wopublish-search/public/...`) are anonymous HTML. WIPO INSPIRE's [ARIPO profile](https://inspire.wipo.int/system/files/juri/ARIPO.pdf) does not list any API capability.

## §3 ToU / contract posture

ARIPO does **not** publish a website Terms of Use page. The [General Notice](https://www.aripo.org/notice) and the eService [help page](http://eservice.aripo.org/common/html/help.jsp) contain no proxy-prohibition language. The Regional IP Database is described as **"free and easy to access"** ([ARIPO 2018 launch announcement](https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/)) but is the standard WIPO Publish read-only UI — there is no contract that admits a third party to redistribute. `robots.txt` on `www.aripo.org` is permissive (`User-agent: *` / `Disallow:` empty), but `eservice.aripo.org` returns 404 on `/robots.txt`. The absence of any ToU document is itself the load-bearing fact: there is **no published contract on which a hosted proxy could rely.**

## §4 Member states + transitive coverage matrix

**ARIPO has 22 member states** ([Member States page](https://www.aripo.org/member-states); [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/ARIPO.pdf); [Banjul Protocol 2026 ed.](https://www.aripo.org/storage/media/1765285419_Banjul%20Protocol%20on%20Marks%20(2026%20Edition).pdf)): Botswana, Cabo Verde, eSwatini, Gambia, Ghana, Kenya, Lesotho, Liberia, Malawi, Mauritius (Harare only as of 2025-08-27), Mozambique, Namibia, Rwanda, São Tomé and Príncipe, Seychelles, Sierra Leone, Somalia, Sudan, Tanzania (mainland), Uganda, Zambia, Zimbabwe.

| Protocol | Subject matter | In force | Contracting states (count) | Source |
|---|---|---|---|---|
| **Harare** | Patents, utility models, industrial designs | 1984-04-25 | 20 (all except Somalia; Mauritius effective 2025-08-27) | [WIPO INSPIRE](https://inspire.wipo.int/system/files/juri/ARIPO.pdf) |
| **Banjul** | Trademarks | 1997-03-06 | 11 (Botswana, eSwatini, Lesotho, Liberia, Malawi, Mozambique, Namibia, STP, Tanzania, Uganda, Zimbabwe) + Cabo Verde from 2025 per [news](https://www.aripo.org/news/the-harare-and-banjul-protocols-now-effective-in-cape-verde-6732) | [Banjul Protocol 2026 ed.](https://www.aripo.org/storage/media/1765285419_Banjul%20Protocol%20on%20Marks%20(2026%20Edition).pdf) |
| **Swakopmund** | Traditional knowledge, expressions of folklore | **2015-05-11** ✓ confirmed | 9 signatory states ([WIPO Lex](https://www.wipo.int/wipolex/en/treaties/members/profile/ARIPO)) | [news](https://www.aripo.org/news/the-harare-and-banjul-protocols-now-effective-in-cape-verde-6732) |
| **Arusha** | New plant varieties (UPOV-like) | **2024-11-24** ✓ confirmed | 4 (Cabo Verde, Ghana, Rwanda, STP) | [ARIPO news 2024](https://www.aripo.org/news/The+Arusha+Protocol+for+the+Protection+of+New+Varieties+of+Plants+Officially+Comes+into+Force-1732618853) |
| **Kampala** (new) | Voluntary copyright registration | 2024-adopted, not yet in force | n/a | [Kampala Protocol 2024 PDF](https://www.aripo.org/storage/resources-protocols/1715840913_Kampala%20Protocol%20on%20Voluntary%20Registration%20of%20Copyright%20and%20Related%20Rights%20(2024).pdf) |

**Transitive coverage via the Regional IP Database (WIPO Publish):** ARIPO + **12** national IPAS exports (Botswana, Gambia, Ghana, Kenya, Malawi, Mozambique, Namibia, Rwanda, Tanzania, Uganda, Zambia, Zimbabwe) per the [ARIPO success story](https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/). But WIPO INSPIRE notes the national side "currently loading and a search gives no results"; Member-State Journals available cover only **Kenya, Mozambique, Rwanda, STP, Tanzania**.

**Relationship with the national layer:** ARIPO grants take effect in **designated** states subject to a 6-month national objection window ([Harare Protocol §3(6)](https://www.aripo.org/storage/resources-protocols/1740752895_Harare%20Protocol%20on%20Patents,%20Utility%20Models%20and%20Industrial%20Designs%20(2025).pdf)). An ARIPO grant becomes enforceable as a national right but is **not** re-published in national registers as a standalone national application — it stays AP-numbered. So the ARIPO register is the canonical surface; national registers see ARIPO-derived rights only as legal-status events.

**INPADOC / EPO OPS:** EPO OPS publishes ARIPO bibliography under the `AP` country code (e.g. `AP12345`); the [Inventa survey of EU priorities](https://inventa.com/en/news/article/507/looking-at-eu-priority-in-aripo-patent-applications) and [WIPO PCT KGL 2018 briefing](https://www.wipo.int/edocs/mdocs/pct/en/wipo_pct_kgl_18/wipo_pct_kgl_18_t3.pdf) both rely on AP-coded INPADOC records. **Practical implication: EPO OPS already gives us ARIPO bibliographic + family + legal-event coverage**, which is the primary route any zero-infra proxy should use for ARIPO data today.

**Confirmation of context bullets:**
- ✓ Arusha entered into force **2024-11-24** (not stated more precisely in brief — confirmed).
- ✓ Swakopmund entered into force **2015-05-11** (confirmed via WIPO Lex).
- ✓ South Africa, Nigeria, Egypt **not** members (not in the 22-state list).
- ✓ Tanzania mainland is an ARIPO member; Zanzibar is separately addressed via the Banjul Protocol's "Tanzania (Zanzibar)" provisions ([Banjul 2026 ed.](https://www.aripo.org/storage/media/1765285419_Banjul%20Protocol%20on%20Marks%20(2026%20Edition).pdf)).
- ✓ Journal is monthly PDF (confirmed via WIPO INSPIRE: "monthly in English").
- ✓ KIPO-built eService + WIPO Publish IPAS integration (confirmed via [ARIPO 2018 launch](https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/) and the KIPO grant attribution in the [AfrIPI demo](https://internationalipcooperation.eu/sites/default/files/afripi-docs/AfrIPI_28apr2021_Agenda%20Item%205%20-%20Demonstration%20of%20%20ARIPO%20eServices.pdf)).
- ✦ Surprise: **Kampala Protocol** (voluntary copyright registration, 2024) — fifth protocol, not in brief.
- ✦ Surprise: **Mauritius** (acceded to Harare 2025-08-27 — recent) and **Seychelles** (member from 2022) — 22 members not 21.

## §5 Verdict (zero-infra proxy)

**🔴 red_no_api.** ARIPO offers two HTML-only public search front ends (KIPO-built eService that redirects to WIPO Publish, plus the WIPO Publish UI itself at `regionalip.aripo.org`) and a monthly **ARIPO Journal as PDF**. There is **no JSON/REST API**, no entry in the [WIPO IP API Catalog](https://apicatalog.wipo.int/), and no developer program. The Regional IP Database is "free" in the read sense but has no documented machine interface and would require HTML scraping with brittle session/cookie handling — and `regionalip.aripo.org` is on a Windows IIS box that blocks Cloud-Run-class egress on HTTPS. **For our purposes the load-bearing fact is that EPO OPS already publishes ARIPO bibliography + legal events under the `AP` country code via INPADOC** — meaning we already have a zero-infra path to ~all ARIPO patent data through our existing `epo_ops` connector. ARIPO-direct adds the Industrial Property Journal PDF feed (a 🟡 yellow_link-only resource — link to PDFs, never mirror) and Banjul TM data not in EPO OPS. Recommend: **link-only atlas card for ARIPO**, with the EPO OPS connector handling the patent data path transitively.

## §6 References

All last-verified **2026-05-18**.

- ARIPO eService — Quick Search → https://eservice.aripo.org/pdl/pqs/quickSearchScreen.do
- ARIPO eService — Advanced Search → https://eservice.aripo.org/pdl/pah/advancedSearchScreen.do
- ARIPO Journal (gazette) → https://eservice.aripo.org/ppb/pjd/PPBJournalViewList.do
- ARIPO eService Help → http://eservice.aripo.org/common/html/help.jsp
- ARIPO Regional IP Database (WIPO Publish, public) → http://regionalip.aripo.org/wopublish-search/public/patents?query=OFCO:AP
- ARIPO — "Free IP Database; Revolutionizing IP in Africa" (2018 launch context) → https://www.aripo.org/success-stories/aripos-free-ip-database-revolutionizing-ip-in-africa/
- ARIPO Member States → https://www.aripo.org/member-states
- ARIPO Protocols index → https://www.aripo.org/resources/protocols
- Harare Protocol (2025 ed.) → https://www.aripo.org/storage/resources-protocols/1740752895_Harare%20Protocol%20on%20Patents,%20Utility%20Models%20and%20Industrial%20Designs%20(2025).pdf
- Banjul Protocol on Marks (March 2026 ed.) → https://www.aripo.org/storage/media/1765285419_Banjul%20Protocol%20on%20Marks%20(2026%20Edition).pdf
- Kampala Protocol on Voluntary Copyright Registration (2024) → https://www.aripo.org/storage/resources-protocols/1715840913_Kampala%20Protocol%20on%20Voluntary%20Registration%20of%20Copyright%20and%20Related%20Rights%20(2024).pdf
- Arusha Protocol — entry into force 2024-11-24 → https://www.aripo.org/news/The+Arusha+Protocol+for+the+Protection+of+New+Varieties+of+Plants+Officially+Comes+into+Force-1732618853
- Harare+Banjul effective in Cabo Verde → https://www.aripo.org/news/the-harare-and-banjul-protocols-now-effective-in-cape-verde-6732
- ARIPO General Notice (no ToU on site) → https://www.aripo.org/notice
- WIPO INSPIRE — ARIPO/AP jurisdiction profile (PDF) → https://inspire.wipo.int/system/files/juri/ARIPO.pdf
- WIPO Lex — ARIPO member profile → https://www.wipo.int/wipolex/en/treaties/members/profile/ARIPO
- WIPO Lex — Arusha Protocol treaty record → https://www.wipo.int/wipolex/en/treaties/details/971
- WIPO IP API Catalog (ARIPO **not** listed) → https://apicatalog.wipo.int/
- WIPO 2024 API Catalog launch → https://www.wipo.int/en/web/standards/w/news/2024/news_0001
- ARIPO eServices demo, AfrIPI 2021 (KIPO grant attribution) → https://internationalipcooperation.eu/sites/default/files/afripi-docs/AfrIPI_28apr2021_Agenda%20Item%205%20-%20Demonstration%20of%20%20ARIPO%20eServices.pdf
- WIPO PCT KGL 2018 — ARIPO role briefing → https://www.wipo.int/edocs/mdocs/pct/en/wipo_pct_kgl_18/wipo_pct_kgl_18_t3.pdf
