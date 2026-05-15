# WIPO Multilateral IP Systems: Research & Access Models

## Overview

WIPO operates eight major international IP registers and databases aggregating data across 130+ member jurisdictions. These systems provide high-leverage data access points because each aggregates registrations from many countries through unified endpoints. Most are accessible via web search interfaces; several offer programmatic access (SOAP/REST APIs) for bulk data extraction.

---

## 1. Madrid Monitor / Madrid Express — International Trademark Register

**Canonical URL**: `https://www3.wipo.int/madrid/monitor/en/`

**Jurisdiction**: WO (Madrid Protocol members: ~130 countries)

**Access Model**: 
- Web UI search at Madrid Monitor
- Madrid Express (simplified interface): `https://madrid-express.wipo.int/`

**Data Exposed**:
- Trademark registrations and applications
- Bibliographic data (owner, agent, mark image, goods/services)
- Status and legal events

**API Available**: Partial
- WIPO publishes no official public REST/SOAP API for Madrid data
- Web scraping viable for bibliographic queries
- No documented bulk XML export for Madrid

**Rate Limiting**: Not published (web UI appears rate-limited via CAPTCHA challenges)

**License**: WIPO open data terms (generally freely accessible for non-commercial use; commercial redistribution terms vary by jurisdiction)

**Commercial Use**: Permitted with attribution; redistribution restrictions apply to some jurisdictions

**Status**: candidate

**Notes**: Madrid Monitor aggregates ~1.4 million international trademark registrations from 130+ Madrid Protocol members. Web-search only; no programmatic bulk access documented. CAPTCHA protection limits scraping. This is a high-value target because it consolidates trademark data across EUIPO, USPTO, JIPO, CNIPA, and 120+ other offices into a single searchable database.

---

## 2. Hague System — International Industrial Design Register

**Canonical URL**: `https://www.wipo.int/hague/en/` (redirects to https://designdb.wipo.int/designdb/hague/en/)

**Jurisdiction**: WO (Hague Agreement members: ~79 countries)

**Access Model**: 
- Web UI search interface only
- No documented API

**Data Exposed**:
- Design registrations and applications
- Design images and technical drawings
- Locarno classification codes
- Ownership and legal status

**API Available**: None documented

**Rate Limiting**: CAPTCHA-protected (blocks most automated access)

**License**: WIPO open data

**Commercial Use**: Permitted; terms vary by member jurisdiction

**Status**: candidate

**Notes**: The Hague System registers ~80k new designs annually across 79 member countries. Web-search interface only; significant bot protection (CAPTCHA) prevents programmatic bulk extraction. High leverage for design practitioners because this single database replaces searches across 79 separate national design registers.

---

## 3. PATENTSCOPE — PCT Patent Search & Bulk Data

**Canonical URLs**: 
- Search: `https://patentscope.wipo.int/search/en/`
- Bulk data products: `https://www.wipo.int/patentscope/en/data/products.html` (or `https://www.wipo.int/en/web/patentscope/data/products`)

**Jurisdiction**: WO (PCT: ~158 member states; covers ~60 million patent documents from WIPO and 10+ national offices)

**Access Model**: 
- Web UI search at PATENTSCOPE
- Bulk XML/PDF downloads (official data products)
- SOAP API (documented in WIPO technical specs, requires registration)

**Data Exposed**:
- PCT applications and published specifications
- Bibliographic data (title, abstract, applicants, inventors, priority dates)
- Full text (abstract + claims + drawings in PDF/XML)
- Classification (IPC, CPC, national classifications)
- Legal status (limited to PCT layer)
- Prosecution history (limited)

**Bulk Data Options**: YES (High value)
- WIPO publishes monthly XML snapshots of PCT applications and publications
- Available at `https://www.wipo.int/patentscope/en/data/products.html`
- Formats: XML, PDF
- Coverage: Full PCT backfile (40+ years)

**API Available**: Yes (SOAP)
- WIPO exposes a SOAP API for PATENTSCOPE queries
- Endpoint documented but requires authentication/registration
- Used by patent offices and large corporations for bulk extraction

**Rate Limiting**: Web UI enforces rate limits; SOAP API has documented thresholds

**License**: 
- Bulk data: WIPO public data license
- Commercial use: Permitted with attribution

**Commercial Use**: True (but check WIPO's specific terms for your use case)

**Status**: candidate (already partially in manifest as WO/PCT)

**Notes**: PATENTSCOPE is the most comprehensive multilateral patent database, aggregating PCT filings and covering 60+ million documents. The bulk XML products are the primary value — these are machine-readable, updated monthly, and directly importable to patent databases. SOAP API is secondary but valuable for incremental updates. This is a system to prioritize because PATENTSCOPE data fuels downstream databases (Google Patents, FreePatentsOnline, etc.). The bulk XML feeds directly into our ETL pipeline without web scraping.

---

## 4. UPOV PLUTO — Plant Variety Database

**Canonical URL**: `https://www3.wipo.int/pluto/user/en/` (or `https://pluto.upov.int/user/en/`)

**Jurisdiction**: WO (UPOV members: 91 countries; covers ~100k registered plant varieties)

**Access Model**: 
- Web UI search interface only
- No documented bulk API

**Data Exposed**:
- Plant variety registrations
- Breeder identity and contact
- Crop type and botanical description
- Legal status and expiration dates

**API Available**: None documented

**Rate Limiting**: None observed (lighter protection than Madrid/Hague)

**License**: WIPO/UPOV open data

**Commercial Use**: Permitted

**Status**: candidate

**Notes**: UPOV PLUTO is the international registry for plant variety protection, covering ornamental plants, crops, and food varieties across 91 member countries. Web-search only. Smaller dataset (~100k varieties) compared to patents/trademarks, but critical for agricultural and biotech IP practitioners. Less bot-protected than Madrid/Hague, making scraping more feasible.

---

## 5. WIPO Global Brand Database (GBD)

**Canonical URL**: `https://branddb.wipo.int/en/`

**Jurisdiction**: WO (Aggregates trademark data from 70+ jurisdictions including USPTO, EUIPO, JPO, CNIPA, etc.)

**Access Model**: 
- Web UI search interface only
- CAPTCHA-protected (very strict bot detection)
- No documented public API

**Data Exposed**:
- Trademark registrations and applications from multiple jurisdictions
- Bibliographic data (owner, mark image, goods/services)
- Basic legal status
- Multi-jurisdiction search (single query across 70+ national databases simultaneously)

**API Available**: None documented publicly

**Rate Limiting**: Aggressive CAPTCHA challenges; blocks most automated access

**License**: WIPO open data (with per-jurisdiction limitations)

**Commercial Use**: Varies by jurisdiction; generally permitted with attribution

**Status**: candidate (web-only, high value but requires sophisticated scraping or manual lookup)

**Notes**: The Global Brand Database is a meta-search interface aggregating trademark data from 70+ jurisdictions in real-time. This is extremely high-leverage because a single query can return results from USA, EU, Japan, China, Australia, Canada, and 60+ other territories without hitting multiple national offices separately. However, CAPTCHA protection and bot-detection are severe — this system is designed to funnel users to WIPO's Brands & Designs Offices for official filings rather than bulk data export. Web UI only; no bulk download or API documented.

---

## 6. WIPO Global Design Database (GDD)

**Canonical URL**: `https://www.wipo.int/designsearch/en/` or `https://designdb.wipo.int/`

**Jurisdiction**: WO (Aggregates design data from 60+ national design offices)

**Access Model**: 
- Web UI search interface only
- Some jurisdiction-specific APIs (e.g., EUIPO DesignView API) but WIPO GDD itself has no public API

**Data Exposed**:
- Design registrations from multiple jurisdictions
- Design images, Locarno classifications
- Legal status and ownership
- Multi-jurisdiction simultaneous search

**API Available**: None documented for GDD; individual member offices may expose APIs (outside WIPO)

**Rate Limiting**: CAPTCHA-protected

**License**: Per-jurisdiction open data terms

**Commercial Use**: Permitted with jurisdiction-specific restrictions

**Status**: candidate (similar to GBD — web UI, high leverage, bot-protected)

**Notes**: WIPO Global Design Database aggregates design registrations from 60+ design offices. Like the Global Brand Database, this is high-leverage for design professionals seeking multi-jurisdiction searches but is heavily bot-protected with no public bulk API.

---

## 7. WIPO Lex — Legislation, Treaties & Case Law

**Canonical URLs**: 
- Main: `https://www.wipo.int/wipolex/en/`
- Collections: Legislation, National Treatment, Bilateral Agreements, Case Law (Judgments database is separate)

**Jurisdiction**: WO (Covers legislation from 200+ countries; treaties and agreements)

**Access Model**: 
- Web UI search at WIPO Lex
- Treaty texts directly downloadable as PDF
- No bulk XML API documented
- Case Law (WIPO Lex Judgments) accessible separately

**Data Exposed**:
- National trademark, patent, copyright, design laws and regulations
- International treaties and agreements
- Court decisions and tribunal judgments (separate collection)
- Commentary and legislative history

**API Available**: No

**Bulk Data**: No documented bulk download

**License**: Open (WIPO)

**Commercial Use**: Permitted

**Status**: Active (already in manifest; not a new discovery)

**Notes**: WIPO Lex is the reference legislation and treaty database for all member countries. This is already part of our IP research infrastructure. The Judgments collection is a subcollection within WIPO Lex that tracks litigation decisions from national courts and WIPO dispute resolution bodies (UDRP, ADRP, etc.). Not requiring separate entry because WIPO Lex is already active.

---

## 8. Lisbon System — Geographical Indications Register

**Canonical URL**: `https://www.wipo.int/lisbon/en/` (or `https://www.wipo.int/en/web/lisbon-system/`)

**Jurisdiction**: WO (Lisbon Agreement members: ~35 countries and the EU; ~1,500 registered GIs)

**Access Model**: 
- Web UI search interface: `https://www.wipo.int/lisbon/search`
- No documented API

**Data Exposed**:
- Appellation of origin (AO) and geographical indication (GI) registrations
- Product category, origin country
- Legal status and renewal dates
- Member office contact information

**API Available**: None documented

**Rate Limiting**: Minimal (lighter protection than Madrid/Hague)

**License**: WIPO open data

**Commercial Use**: Permitted

**Status**: candidate

**Notes**: The Lisbon System registers international appellations of origin and geographical indications (GIs) such as "Champagne," "Parmesan," "Darjeeling." Smaller database (~1,500 registrations) compared to trademarks/patents but specialized and high-value for food, wine, and agricultural IP professionals. Web-search only; no API documented. Smaller member base (35 countries + EU) but growing, especially in Africa and Latin America.

---

## Summary: Leverage vs Current Manifest

**Current Manifest Coverage**:
- WO/WIPO Lex: Active (legislation, treaties, case law)
- WO/PCT: Candidate (PATENTSCOPE, patents only)

**New High-Leverage Entries** (Recommended Priority):

1. **WO/PATENTSCOPE Bulk Data** (Highest) — Upgrade from candidate to active; existing system but adds bulk XML feed and SOAP API documentation. 60+ million patent documents; monthly XML updates available.

2. **WO/Madrid System** (High) — 1.4 million trademark registrations across 130 countries. Web-search only but high-value aggregator; replaces ~130 national searches. Candidate status.

3. **WO/Hague System** (High) — 80k+ design registrations across 79 countries. Single registry replacing 79 national searches. Candidate status.

4. **WO/Global Brand Database** (Medium-High) — 70+ jurisdiction trademark meta-search. High leverage but strictly web UI + CAPTCHA. Candidate status with scraping feasibility note.

5. **WO/UPOV PLUTO** (Medium) — 100k+ plant varieties across 91 countries. Smaller dataset but specialized; minimal bot protection. Candidate status.

6. **WO/Lisbon System** (Medium) — 1,500+ geographical indications across 35+ jurisdictions. Specialized niche but valuable for food/wine/agriculture IP. Candidate status.

---

## API & Bulk Access Summary Table

| System | Bulk XML | REST API | SOAP API | Web UI | Bot-Protected |
|--------|----------|----------|----------|--------|---------------|
| Madrid Monitor | No | No | No | Yes | Yes (CAPTCHA) |
| Hague System | No | No | No | Yes | Yes (CAPTCHA) |
| PATENTSCOPE | **Yes** | No | **Yes** | Yes | Moderate |
| UPOV PLUTO | No | No | No | Yes | Light |
| Global Brand DB | No | No | No | Yes | Yes (CAPTCHA) |
| Global Design DB | No | No | No | Yes | Yes (CAPTCHA) |
| WIPO Lex | No | No | No | Yes | Light |
| Lisbon System | No | No | No | Yes | Light |

---

## Recommended Next Steps

1. **Prioritize PATENTSCOPE Bulk XML**: Implement monthly ingestion of PCT XML data products from `https://www.wipo.int/patentscope/en/data/products.html`. This is machine-readable, no scraping needed.

2. **Add Madrid + Hague as Web-Scrape Candidates**: Both have high leverage (~1.4M + 80k records). CAPTCHA is an obstacle but not insurmountable with rotating proxies or manual intervention workflows.

3. **Document WIPO Lex Case Law Separately**: The Judgments collection deserves its own entry because it tracks litigation data distinct from legislation.

4. **Evaluate Global Brand DB via Hybrid Approach**: The 70-jurisdiction search capability is valuable. Consider a hybrid: light web scraping + manual research workflow, or negotiate direct data access with WIPO.

---

## License & Commercial Use Notes

- **WIPO Open Data Policy**: Most WIPO databases are open for non-commercial use; commercial redistribution requires attribution and per-jurisdiction verification.
- **Madrid Protocol**: Administered by WIPO but trademark data ownership varies by member office (USPO, EUIPO, JPO, etc.). Bulk use should reference member ToS.
- **PATENTSCOPE**: PCT filings are WIPO-administered. Bulk XML is explicitly redistributable under WIPO open data license.
- **Verify Per Jurisdiction**: Each entry's ToS should be spot-checked for the top 5 jurisdictions (USA, EU, Japan, China, Korea) because their national data policies may supersede WIPO's general terms.

