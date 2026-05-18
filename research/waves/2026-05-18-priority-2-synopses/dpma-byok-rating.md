# DPMA Germany — BYOK contract rating (2026-05-18)

**Scope:** Re-examine the existing 🔴 `red_contract` rating on `DE/DPMA`
(STATE.yaml + national/de-dpma.md) against the BYOK pattern used for
JPO/KIPO/TIPO/INPI France. The previous rating was based on a paraphrase of
"§3.2 prohibits proxy use." This memo pulls the **actual** standard-contract
text and re-rates per programmatic surface.

**Primary sources read (all dpma.de / register.dpma.de):**
- [DPMAconnectPlus overview (DE)](https://www.dpma.de/recherche/datenabgabe/dpmaconnect/index.html)
- [**Standardvertrag DPMAconnectPlus**, Stand 01.04.2020, 10 pages (DE PDF)](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf) — the actual contract; the URL `dpmaconnectplusvertragsbedingungen.pdf` cited in the existing synopsis is a **dead link → DPMA 404 page**.
- [Anlage 1 — Datenpaket-Bestellblatt (DE PDF)](https://www.dpma.de/docs/recherche/dienste/anlage_2_standardvertragdpmaconnectplus.pdf)
- [Anlage 2 — EU-Standardvertragsklauseln (DE PDF)](https://www.dpma.de/docs/recherche/dienste/anlage_3_standardvertragdpmaconnectplus.pdf)
- [Schnittstellenbeschreibung DPMAconnectPlus (DE PDF, 12pp)](https://www.dpma.de/docs/recherche/dienste/schnittstellenbeschreibungdpmaconnectplus.pdf)
- [DPMAregister Nutzungsbedingungen](https://register.dpma.de/DPMAregister/service/nutzungsbedingungen)
- [DEPATISnet Nutzungsbedingungen](https://depatisnet.dpma.de/DepatisNet/depatisnet?window=1&space=menu&content=index&action=nutzung)

---

## §1 Per-surface contract findings

### 1.1 DPMAconnectPlus (REST API) — the only first-class programmatic surface

**Contract:** [Standardvertrag DPMAconnectPlus, Stand 01.04.2020](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf).
Counterparty: BRD vertreten durch BMJV → Präsidentin des DPMA, 80297 München.
Term: indefinite; either side may terminate with 1 month's notice (§7.2).
Law: German (§10.4); venue Munich (§10.3). No German-residency requirement —
"Land" is a free-text field on Anlage 1 and §8 explicitly contemplates
Datenempfänger established outside the EU (then EU-SCC Anlage 2 attaches).
One-time connection fee **EUR 200** (§4.2); per-record retrieval free;
optional Frontfile/backfile packages per Anlage 1 (EUR 8 / weekly delivery
for biblio + legal-status; EUR 260 / Jahrgang for backfile full-text).

**§2.1 — registered, non-dynamic IP, no third-party use of the *access channel*:**
> "Die Anbindung an die Schnittstelle erfolgt gemäß der technischen Spezifikation und unter der Voraussetzung, dass der Datenempfänger über ein System mit registrierter und nicht dynamischer IP-Adresse herunterlädt. Der Datenempfänger ist verpflichtet, die unberechtigte Nutzung des Datenzugangs durch Dritte zu verhindern."
>
> "Connection to the interface follows the technical specification and on the condition that the data recipient downloads via a system with a registered, non-dynamic IP address. The data recipient is required to prevent unauthorized use of the data access by third parties."

This is a **fixed-IP requirement** for the contracting party's own client.
It does not forbid self-hosting; it *requires* it (no shared cloud egress
IP unless the user pre-registers it). It bars the user from letting an
unauthorized third party reuse their access channel.

**§3.1 — purposes of use (the Datenempfänger ticks one):**
- (a) build internal database for own protective-rights research,
- (b) **build a database that the Datenempfänger makes available to authorized third parties** (with or without fee) so that *those third parties* can ascertain/manage protective rights,
- (c) develop/sell information products and services on protective rights,
- (d) scientific work.

**§3.2 — non-transferable use right + the data-redistribution prohibition:**
> "Der Datenempfänger erwirbt mit Abschluss dieses Vertrags das einfache, nicht ausschließliche, **auf Dritte nicht übertragbare** Recht zur Nutzung der Daten zu dem in Ziffer 1 genannten Zweck. Jede Verarbeitung oder Nutzung der Daten zu einem anderen Zweck ist unzulässig. Insbesondere ist es nicht zulässig, die vom DPMA bezogenen Daten beziehungsweise Datensätze ganz oder teilweise an Dritte weiterzugeben; **eine Weitergabe im Rahmen einer Nutzung gemäß dem Zweck nach Ziffer 1 b) ist von diesem Verbot ausgenommen** […]"
>
> "By concluding this contract, the Datenempfänger acquires the simple, non-exclusive, **non-transferable to third parties** right to use the data for the purpose stated in [§3.1]. Any other processing or use is impermissible. In particular, it is impermissible to pass the data or records obtained from DPMA, in whole or in part, to third parties; **passing-on within a use under purpose 1(b) is exempted from this prohibition** […]"

This is the central clause. It restricts **redistribution of the data records**
to third parties (with an explicit carve-out for purpose 1(b)). It does **not**
restrict where the contracting party runs their own client, nor forbid the
contracting party from automating the calls, nor name "proxy" anywhere. The
prior synopsis's framing "§3.2 prohibits proxy use" is a misread — what §3.2
prohibits is **rebroadcasting the data** in non-1(b) configurations.

**Rate-limit posture:** Schnittstellenbeschreibung — registered users get
**max 1000 hits per search query** (test accounts: 100). No published per-second
or per-day throttle; §2.2 lets DPMA cap volume if a user impairs interface
availability for others.

**Foreign signup:** Anlage 1 collects Anrede / Name / Firma / Straße / PLZ /
**Ort / Land** — explicitly accepts a non-German address. EU-SCC bolt-on
(§8 + Anlage 2) attaches automatically for non-EU/EEA Niederlassung.

### 1.2 DPMAregister web UI

[Nutzungsbedingungen](https://register.dpma.de/DPMAregister/service/nutzungsbedingungen):
> "Personen, die die allgemeine Nutzung dieses Dienstes durch eine ungewöhnliche hohe Anzahl manueller oder softwareunterstützter Zugriffe zu behindern drohen (**mehr als 5000 Datenbankzugriffe täglich** durch dieselbe Person oder unter derselben IP-Adresse beziehungsweise unter einem zusammengehörigen Adressbereich), können ohne weitere Vorwarnung von der Nutzung ausgeschlossen werden."
>
> ">5000 database hits/day from same person/IP/IP-range may be excluded without warning."

No contract, no signup. Free, but explicitly UI-shaped, hard 5,000-hit/day
ceiling, and for "larger volumes" the page redirects users to DPMAconnectPlus.
Scraping at scale is structurally foreclosed; light per-record lookups (≤5,000/day
across the global IP pool) are tolerated.

### 1.3 DEPATISnet patent-search UI

[Nutzungsbedingungen](https://depatisnet.dpma.de/DepatisNet/depatisnet?window=1&space=menu&content=index&action=nutzung):
identical language to DPMAregister — same 5,000/day ceiling, same "for more,
use DPMAconnectPlus" pointer. Same posture.

### 1.4 DPMA Datenabgabe / Backfile

Same contract as DPMAconnectPlus (Anlage 1 of `standardvertrag_dpmaconnectplus.pdf`
sells the backfile as line items). No separate ToS surface.

---

## §2 Verdict matrix

| Surface | BYOK verdict | Basis |
|---|---|---|
| **DPMAconnectPlus (REST)** | 🟢 **Permits BYOK** | §3.2 restricts *redistributing the data*, not self-hosting. §2.1 requires user's own registered fixed IP — exactly the self-host shape. No German-residency requirement (Anlage 1 accepts any Land; §8 ships EU-SCC for non-EU recipients). User signs their own contract, gets their own credentials, never shares them with us. |
| **DPMAregister UI** | 🔴 Forbids automation at scale | 5,000 hits/day ceiling on IP-range basis; UI structure; explicit "use DPMAconnectPlus for volume." Not BYOK-shaped (no per-user creds to gate on). |
| **DEPATISnet UI** | 🔴 Forbids automation at scale | Identical 5,000/day ceiling; same UI shape. |
| **DPMA Datenabgabe (backfile)** | 🟢 **Permits BYOK** | Same contract as DPMAconnectPlus; same analysis. Per-package fees apply (EUR 30 – EUR 750 per dataset). |

**Headline correction:** the previous `red_contract` rating on `DE/DPMA` was
based on a misread of §3.2. The actual blocker to a *DPMA-as-zero-infra-proxy*
deployment is real (§3.2 forbids us from rebroadcasting), but the **BYOK
shape**, where each user is themselves the Datenempfänger, is unambiguously
permitted by the contract text.

---

## §3 Recommendation

**Proposed BACKLOG.md entry (DPMA row, Tier 2 — replaces the current red-skip line):**

> | **DPMA** | "Tier 2; skipped — contract forbids proxy" | **Reconciled.** §3.2 of the [DPMAconnectPlus standard contract](https://www.dpma.de/docs/recherche/dienste/standardvertrag_dpmaconnectplus.pdf) forbids us from running it as a zero-infra proxy, but **does not forbid self-hosted BYOK**: each user signs their own Datenempfänger contract (EUR 200 one-time), registers their own fixed IP, gets their own Basic-auth credentials, and runs `patent-client-agents-mcp` locally. Same shape as JPO/KIPO/TIPO/INPI France. Estimated effort **~3-5 days** for the REST surface (3 services × ~10 functions, single Basic-auth header, 1000-hit cap per search, weekly Frontfile ZIPs). Adds the only authoritative path to **DE Gebrauchsmuster, national-only DE trademarks, and national-only DE designs** — none of which are in EPO OPS. | [waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md](waves/2026-05-18-priority-2-synopses/dpma-byok-rating.md) |

**Suggested next action:** flip `DE/DPMA` in STATE.yaml from `red_contract`
to `yellow_byok` (or equivalent), update `national/de-dpma.md` §3 verdict
rows + §5 "What we should NOT add" → "What we CAN add as BYOK", and queue a
`dpma_register` connector card mirroring `jpo/` for next sprint. Hold the
broken dead link fix (`dpmaconnectplusvertragsbedingungen.pdf` → 404; use
`standardvertrag_dpmaconnectplus.pdf` instead) into the same PR.
