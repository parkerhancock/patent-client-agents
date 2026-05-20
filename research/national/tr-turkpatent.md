# TÜRKPATENT (TR) — national

**Layer:** national
**Jurisdiction:** TR (WIPO ST.3: TR)
**Issuing body:** Türk Patent ve Marka Kurumu (Turkish Patent and Trademark Office, "TÜRKPATENT")
**Rights administered:** patent, utility model (*faydalı model*), industrial design (*tasarım*), trademark (*marka*), integrated-circuit topography (*entegre devre topoğrafyası*), geographical indication (*coğrafi işaret*), traditional product name (*geleneksel ürün adı*)
**Working languages:** Turkish (primary); English mirrors exist for navigation, but the Turkish-language texts are the gazette-authoritative versions
**Connector status:** **fees: ready to build (green — schedule reachable on TÜRKPATENT site + Resmî Gazete primary source); register: not yet surveyed**
**Last verified:** 2026-05-19
**Manifest entry:** not yet listed (fees scheduled for next build wave)

**Higher layers covering this office transitively:**
- **EPO INPADOC / OPS** — Turkey is a [contracting state of the European Patent Convention since 2000-11-01](https://www.epo.org/en/about-us/foundation/member-states); TR-designated European Patents and validated EP patents in Turkey flow through OPS biblio + family + legal events.
- **WIPO Madrid Monitor** — Turkey is a [Madrid Protocol contracting party since 1999-01-01](https://www.wipo.int/treaties/en/ShowResults.jsp?treaty_id=8); Madrid IRs designating TR flow through Madrid Monitor.
- **WIPO Hague Express** — Turkey is a [Hague Agreement contracting party since 2005-01-01](https://www.wipo.int/hague/en/members/); Hague IRs designating TR flow through Hague Express.
- **WIPO Patentscope** — Turkey is a [PCT contracting state since 1996-01-01](https://www.wipo.int/pct/en/pct_contracting_states.html); PCT national-phase entries into TR flow through Patentscope and INPADOC.

---

## §1 Mission

TÜRKPATENT is Turkey's sole national IP office and the
administrative authority for all national industrial property
rights under the **Industrial Property Code (Sınai Mülkiyet
Kanunu, Law No. 6769)**, in force since 10 January 2017. The
office is a successor to the Türk Patent Enstitüsü (TPE),
renamed in 2017 to reflect its expanded mandate over trademarks
and designs. Headquartered in Ankara, with an institutional
landing at [turkpatent.gov.tr](https://www.turkpatent.gov.tr/).

Turkey is a substantial filer regionally — within the top-30
WIPO ranking by patent volume — and is a contracting state to
the EPC (since 2000), PCT (since 1996), Madrid Protocol (since
1999), and Hague Agreement (since 2005). EP validations in TR
and Madrid IRs designating TR are common practice for foreign
filers.

## §2 What's unique here

Data types that live ONLY at TÜRKPATENT and are not covered by
any higher layer at full fidelity:

- **TR national-only patents and utility models** — direct
  national filings (not via EP validation or PCT national
  phase).
- **TR industrial designs** — Locarno-classed national designs
  under SMK Book IV.
- **TR national trademarks** — direct filings (not via Madrid).
- **TR geographical indications and traditional product names**
  — sui generis rights under SMK Book III.
- **TR integrated-circuit topographies** — sui generis right
  under Law No. 5147.

## §3 Programmatic surfaces — to be surveyed

Status: deferred. Register-level connector surveying not yet
done; fees connector takes priority because the surface is
fully open. A follow-up sweep should cover:

- TÜRKPATENT online search portals (EPATS, marka araştırma,
  tasarım araştırma)
- Bulk data feeds (if any) for the official gazette (*Resmi
  Patent Bülteni*, *Resmi Marka Bülteni*, *Resmi Tasarım
  Bülteni*)
- EPO Federated Register Service participation status

## §4 Fees

**Status (2026-05-19):** Ready to build. The fee schedule
publication chain is fully open and gives us **two
authoritative routes** to the same numbers — TÜRKPATENT's site
for the practical extraction target, and Resmî Gazete for
formal citation.

**Publication chain:**

1. **Primary statutory source — Resmî Gazete (Official Gazette).**
   The 2026 schedule was published in the **5th mükerrer
   (supplementary) issue of 31 December 2025** as
   **"Türk Patent ve Marka Kurumunca 2026 Yılında Uygulanacak
   Ücret Tarifesine İlişkin Tebliğ (BİK/TÜRKPATENT: 2026/1)"**:
   [resmigazete.gov.tr/eskiler/2025/12/20251231M5.htm](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5.htm) → PDF at [`20251231M5-37.pdf`](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf). Anonymously fetchable. This is the document with binding legal effect.
2. **TÜRKPATENT site pages (practical extraction target).**
   TÜRKPATENT re-hosts the gazetted schedule as native HTML
   tables, one per right type. All return clean `<table>`
   markup (6 columns: KOD | AÇIKLAMA | ÜCRET | KDV | HARÇ |
   TOPLAM TUTAR) and are anonymously fetchable from US egress:
   - [Patents and utility models — patent-islem-ucretleri](https://www.turkpatent.gov.tr/patent-islem-ucretleri) (57 rows on the patent table observed 2026-05-19)
   - [Trademarks — marka-islem-ucretleri](https://www.turkpatent.gov.tr/marka-islem-ucretleri)
   - [Industrial designs — tasarim-islem-ucretleri](https://www.turkpatent.gov.tr/tasarim-islem-ucretleri)
   - Appeal-procedure fees are published as a separate schedule on the same site.
3. **English mirrors** (for navigation only, not gazette-authoritative): e.g. [trademark-fees (EN)](https://www.turkpatent.gov.tr/en/trademark-fees).

**Earlier "21 scripts, 0 tables" finding superseded.** The
2026-05-19 probe found 1 real `<table>` per page with the
fee schedule rendered server-side. The earlier "JS-rendered
SPA" assessment in [`FEES_TOP30_GAP.md`](../../FEES_TOP30_GAP.md)
was wrong.

**Scope of the schedule (TRY-denominated, hierarchical code-tagged):**

- **Patents & utility models (`01.x.x` code prefix)** — filing fee, priority claim, EP validation/translation publication, page surcharge, renewal certificate issuance, transfer, license, structural changes, inheritance, security/lien, recordation, force-majeure surcharge, late-annuity penalty (with formula-defined amounts), per-year annuities (3rd through 20th year sicil kayıt ücreti). 57 rows observed on the patent table 2026-05-19.
- **Trademarks (`02.x.x` code prefix)** — per-class filing, opposition, renewal, recordation, late surcharges.
- **Industrial designs (`03.x.x` code prefix)** — filing, renewal, recordation.
- **Appeals** — separate schedule covering YİDD (Yeniden İnceleme ve Değerlendirme Dairesi Başkanlığı) appeal procedures for all three right types.

**Column model:** `ÜCRET` (TÜRKPATENT base fee) + `KDV` (18%
VAT, where applicable) + `HARÇ` (Stamp duty / treasury fee
where applicable) = `TOPLAM TUTAR` (total). The HARÇ column
encodes some rows as formulas (e.g., late-annuity penalty =
"Ödenmesi gereken yıllık ücret + (Ödenmesi gereken yıllık
ücret - harç)ın %50'si") — connector should preserve the
formula text verbatim where present.

**Annual revision cadence.** TÜRKPATENT republishes the
schedule annually in the Resmî Gazete on or about 31
December, taking effect 1 January of the following year.
Year-over-year jumps have been large because of TRY
inflation: 2024 → 2025 was approximately +44%, 2025 → 2026
approximately +20–25%. **Do not rely on a quoted figure more
than a few months old without re-pulling.**

**TRY volatility caveat.** Because fees are TRY-denominated
and the lira has been volatile, the effective USD/EUR cost
to a foreign filer can shift materially mid-year even when
the official fee hasn't changed. Cost estimates sent to a US
client should include the TRY→USD spot rate on the date of
quotation, with a forward-volatility note.

**Discount tiers (mapped to `EntityTier`):**

- The Turkish schedule does not encode a US-style "small
  entity" rate; TÜRKPATENT applies the same base fee to all
  filers regardless of size. No row-level tier expansion is
  required.
- Reduced fees do apply in specific circumstances (e.g.,
  certain student / academic exam fees, individual
  inventors via TÜBİTAK-supported tracks), but these are
  programme-level subsidies administered outside the gazetted
  tariff, not tariff-line discounts. Out of scope for v1.

**Statutory basis:**

- [Sınai Mülkiyet Kanunu (Law No. 6769) — Resmî Gazete publication, 10-01-2017 (Issue No. 29944)](https://www.resmigazete.gov.tr/eskiler/2017/01/20170110.htm) — the consolidated Industrial Property Code, replacing the prior Decree-Laws KHK/551 (patents), KHK/554 (designs), KHK/555 (GIs), and KHK/556 (trademarks). Annual fee schedules are issued under Article 188 of Law 6769 by Cabinet/Office decision and published in the Resmî Gazete.

**v1 connector plan — `TR/TURKPATENT/Fees/{Patent, UtilityModel, Design, Trademark, Appeal}`:**

- **Source:** the three TÜRKPATENT HTML pages (patent / marka / tasarim) as the extraction target; the Resmî Gazete PDF (`20251231M5-37.pdf`) as the cited authority and version pin.
- **Parser pattern:** `lxml` table extraction — 6-column shape per page, hierarchical KOD prefix splits row population across right types. Annuity rows expand into per-year FeeItems via the "N.Yıl Sicil Kayıt Ücreti" pattern.
- **Currency:** TRY.
- **Provenance metadata:** `version_as_of = "2026-01-01"`, `gazette_citation = "Resmî Gazete 31-12-2025 5. mükerrer, BİK/TÜRKPATENT: 2026/1"`, `freshness_max_age = 90d`.
- **Freshness probe:** quarterly check of (a) the three TÜRKPATENT HTML page hashes, (b) the Resmî Gazete on or about 31 December for the next year's tebliğ.
- **Charset note:** the TÜRKPATENT pages declare `charset=utf-8` in the HTTP header, but observed bytes are decoded cleanly only with `httpx`'s response handling using `response.text` (Turkish characters preserved). Resmî Gazete legacy pages (`/eskiler/...`) use Windows-1254; URLs and PDF anchors are ASCII-safe and the PDF itself is UTF-8.
- **SSL note:** Both `turkpatent.gov.tr` and `resmigazete.gov.tr` present valid certs (unlike `dof.gob.mx`); no `verify=False` required.

## §5 Connector strategy

### Fees connector (this wave)

Ship `TR/TURKPATENT/Fees/{Patent, UtilityModel, Design,
Trademark, Appeal}` per §4 — five routes from three HTML
pages plus the appeal schedule. The TÜRKPATENT HTML route is
the practical scraping target; the Resmî Gazete PDF is the
authoritative version pin and citation source.

### Register connector (deferred)

Surface survey pending. Open questions for the survey:

- Does TÜRKPATENT publish a documented REST/JSON API for
  patent / TM / design search?
- Are the EPATS portals (e.g., `epats.turkpatent.gov.tr`)
  account-gated or guest-accessible for read-only search?
- Is TÜRKPATENT listed in the [WIPO IP API Catalog](https://apicatalog.wipo.int/)? (Quick probe TBD.)
- Does TÜRKPATENT participate in EPO Federated Register
  Service?
- Is the Resmi Patent / Marka / Tasarım Bülteni available as
  structured data feeds (XML/JSON) or PDF only?

Until surveyed, MX register coverage flows transitively
through EPO OPS / INPADOC (granted TR national + TR-validated
EP patents), WIPO Madrid Monitor (Madrid IRs designating
TR), WIPO Hague Express (Hague IRs designating TR), and
Patentscope (PCT national-phase entries).

## §6 Open questions

- **Register-side connector feasibility.** Surface survey
  deferred to a later wave; the §3 placeholder enumerates
  the questions.
- **English-language fee-schedule fidelity.** TÜRKPATENT
  hosts English mirrors of the fee pages; do they get
  updated synchronously with the Turkish gazetted schedule,
  or do they lag? Empirical diff check TBD.
- **HARÇ formula rows.** A small number of patent rows
  encode amounts as prose formulas referencing other rows
  (force-majeure surcharge, late-annuity penalty). v1
  preserves the formula text verbatim; later versions may
  resolve them into per-year computed amounts.
- **Appeal schedule structure.** Verified as a separate
  page but the exact URL and column shape need a 5-min
  probe before ship.

## §7 References

**TÜRKPATENT institutional + fee pages (reachable):**
- [TÜRKPATENT landing](https://www.turkpatent.gov.tr/)
- [Patent fee schedule — patent-islem-ucretleri (TR)](https://www.turkpatent.gov.tr/patent-islem-ucretleri)
- [Trademark fee schedule — marka-islem-ucretleri (TR)](https://www.turkpatent.gov.tr/marka-islem-ucretleri)
- [Design fee schedule — tasarim-islem-ucretleri (TR)](https://www.turkpatent.gov.tr/tasarim-islem-ucretleri)
- [Trademark fees — English mirror](https://www.turkpatent.gov.tr/en/trademark-fees)

**Resmî Gazete (primary statutory source):**
- [Resmî Gazete landing](https://www.resmigazete.gov.tr/)
- [31 December 2025, 5. mükerrer issue — fihrist](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5.htm)
- [BİK/TÜRKPATENT: 2026/1 — Ücret Tarifesine İlişkin Tebliğ PDF](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf)

**Substantive law:**
- [Sınai Mülkiyet Kanunu (Law No. 6769) — Resmî Gazete 10-01-2017 (Issue 29944)](https://www.resmigazete.gov.tr/eskiler/2017/01/20170110.htm)

**International framework:**
- [EPC contracting states (Turkey since 2000-11-01)](https://www.epo.org/en/about-us/foundation/member-states)
- [WIPO Madrid contracting parties (Turkey since 1999-01-01)](https://www.wipo.int/treaties/en/ShowResults.jsp?treaty_id=8)
- [WIPO Hague members (Turkey since 2005-01-01)](https://www.wipo.int/hague/en/members/)
- [WIPO PCT contracting states (Turkey since 1996-01-01)](https://www.wipo.int/pct/en/pct_contracting_states.html)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-19 | Initial synopsis, **fee-focused**. Fees rated **green (ready to build)**: TÜRKPATENT publishes annual fee schedules in the Resmî Gazete (current: 5th mükerrer of 31-12-2025, BİK/TÜRKPATENT 2026/1, [`20251231M5-37.pdf`](https://www.resmigazete.gov.tr/eskiler/2025/12/20251231M5-37.pdf)) and re-hosts them as native HTML tables on three site pages (patent / marka / tasarım), all anonymously fetchable from US egress with valid SSL. Six-column shape: KOD / AÇIKLAMA / ÜCRET / KDV / HARÇ / TOPLAM TUTAR; 57 patent rows observed. Earlier "21 scripts, 0 tables, JS-SPA" finding in `FEES_TOP30_GAP.md` superseded — the pages have real server-rendered tables. Annual republication cadence (2024→2025 +44%, 2025→2026 +20–25% per TRY inflation); freshness window ~90d. Statutory basis: Law 6769 Sınai Mülkiyet Kanunu, in force since 10-01-2017. Register-side connector survey deferred. Coverage of TR-national patents/TMs/designs at biblio fidelity flows transitively through EPO INPADOC (granted patents + EP validations), Madrid Monitor (Madrid IRs designating TR), Hague Express (Hague IRs designating TR), and Patentscope (PCT national-phase entries). | This session; live probes 2026-05-19 |
