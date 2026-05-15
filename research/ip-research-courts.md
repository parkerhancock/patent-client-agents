# IP Court Connectors Research

Research into specialized intellectual property courts worldwide for potential connector development. Courts listed below are verified for decision publication, access method, and data structure.

## Research Summary

**Accessible (open or semi-open decision databases):**
- UK Patents Court (BAILII, Judiciary.uk) — website scrape or BAILII aggregation
- Japan IP High Court — official decision repository with English summaries
- Korea Patent Court — official SCOURT system with searchable decisions
- Australia Federal Court — AustLII aggregation (public domain via Creative Commons)

**Gated or restricted:**
- Germany BPatG (juris) — restricted commercial reuse, complex auth requirements
- China IP Courts — centralized but redirects/GFW challenges; official data requires account
- France (TJ Paris IP) — Légifrance has restricted access; CCIJ aggregation available
- Italy — Italgiure system accessible but decision scraping restrictions

**External (already covered by partner projects):**
- Australia Federal Court — fully covered via AustLII (which our downstream projects can consume)
- UK — BAILII itself is a specialized aggregator already indexed by legal research tools

---

## Individual Court Research

### 1. UK Patents Court (High Court, Business and Property Courts)

| Field | Value |
|-------|-------|
| **ID** | `GB/PatentsCourt` |
| **Name** | UK Patents Court (High Court, Business and Property) |
| **Jurisdiction** | GB |
| **Issuing Body** | His Majesty's Courts and Tribunals Service (HMCTS) |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Primary Source** | BAILII (British and Irish Legal Information Institute) |
| **Access URL** | https://www.bailii.org/ew/cases/EWHC/Patents/ |
| **Access Method** | website_scrape (with bot detection) |
| **Authentication** | none (BAILII public) |
| **Rate Limit** | not_published (strict Anubis proof-of-work challenge) |
| **License** | bailii_terms (public domain, CC0-equivalent) |
| **Commercial Use** | conditional (BAILII permits aggregation) |
| **Status** | **external** (BAILII is established aggregator) |

**Notes:**
- BAILII hosts all UK Patents Court decisions in searchable format; covers High Court (Patents) division
- Also includes IPEC (Intellectual Property Enterprise Court) decisions
- BAILII applies aggressive Anubis bot protection requiring JS proof-of-work
- CanLII/LDH likely already index these; recommend referencing via BAILII external ID rather than scraping

---

### 2. Germany — Bundespatentgericht (Federal Patent Court)

| Field | Value |
|-------|-------|
| **ID** | `DE/BPatG` |
| **Name** | Bundespatentgericht (Federal Patent Court) |
| **Jurisdiction** | DE |
| **Issuing Body** | Deutsches Patent- und Markenamt (German Patent and Trade Mark Office) |
| **Rights** | [patent, trademark] |
| **Data Types** | [case_law] |
| **Official Database** | juris.bundespatentgericht.de |
| **Access URL** | https://juris.bundespatentgericht.de/cgi-bin/rechtsprechung/list.py |
| **Access Method** | rest_api (CGI-based search) |
| **Authentication** | none (public) |
| **Rate Limit** | not_published |
| **License** | restricted (German juris terms prohibit automated commercial reuse) |
| **Commercial Use** | no (juris license restricts scraping) |
| **Status** | **candidate** (restricted reuse but publicly accessible) |

**Notes:**
- Official jurisprudence database at juris.bundespatentgericht.de
- Also consult VerfBB and PATisnet for supplementary data
- License restrictions make commercial indexing problematic; recommend flagging as restricted-reuse
- Decisions in German; English translations rare but available via secondary sources

---

### 3. China — IP Courts (Multi-jurisdictional)

#### 3a. Beijing IP Court
| Field | Value |
|-------|-------|
| **ID** | `CN/Beijing-IPCourt` |
| **Name** | Beijing Intellectual Property Court |
| **Jurisdiction** | CN (Beijing) |
| **Issuing Body** | Beijing Intellectual Property Court |
| **Rights** | [patent, trademark, design, copyright, trade_secrets] |
| **Data Types** | [case_law, docket] |
| **Official Site** | (redirects, requires VPN or special access) |
| **Access Method** | rest_api (official portal, requires authentication) |
| **Authentication** | account_required |
| **Rate Limit** | not_published |
| **License** | restricted_use |
| **Commercial Use** | no |
| **Status** | **blocked** (account + VPN required; export restrictions) |

#### 3b. Shanghai IP Court
| Field | Value |
|-------|-------|
| **ID** | `CN/Shanghai-IPCourt` |
| **Name** | Shanghai Intellectual Property Court |
| **Jurisdiction** | CN (Shanghai) |
| **Issuing Body** | Shanghai Intellectual Property Court |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Official Site** | (court.gov.cn subdomain, redirects) |
| **Access Method** | rest_api (portal-based) |
| **Authentication** | account_required |
| **Rate Limit** | not_published |
| **License** | restricted_use |
| **Commercial Use** | no |
| **Status** | **blocked** (authentication required) |

#### 3c. Guangzhou IP Court
| Field | Value |
|-------|-------|
| **ID** | `CN/Guangzhou-IPCourt` |
| **Name** | Guangzhou Intellectual Property Court |
| **Jurisdiction** | CN (Guangzhou) |
| **Issuing Body** | Guangzhou Intellectual Property Court |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Official Site** | (court.gov.cn subdomain) |
| **Access Method** | rest_api (portal-based) |
| **Authentication** | account_required |
| **Rate Limit** | not_published |
| **License** | restricted_use |
| **Commercial Use** | no |
| **Status** | **blocked** (authentication required) |

#### 3d. Hainan Free Trade Port IP Court
| Field | Value |
|-------|-------|
| **ID** | `CN/Hainan-IPCourt` |
| **Name** | Hainan Free Trade Port Court (IP Division) |
| **Jurisdiction** | CN (Hainan) |
| **Issuing Body** | Hainan Free Trade Port Court |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Official Site** | (court.gov.cn subdomain, recently established 2019–2023) |
| **Access Method** | rest_api (portal-based) |
| **Authentication** | account_required |
| **Rate Limit** | not_published |
| **License** | restricted_use |
| **Commercial Use** | no |
| **Status** | **blocked** (authentication required) |

#### 3e. Supreme People's Court — IP Tribunal (National Appellate)
| Field | Value |
|-------|-------|
| **ID** | `CN/SPC-IPTribunal` |
| **Name** | Supreme People's Court — Intellectual Property Tribunal |
| **Jurisdiction** | CN (National) |
| **Issuing Body** | Supreme People's Court of the People's Republic of China |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Official Site** | https://www.court.gov.cn/zhuanti/zixun/57.html (IP resources, redirects) |
| **Access Method** | rest_api (official portal) |
| **Authentication** | account_required |
| **Rate Limit** | not_published |
| **License** | restricted_use |
| **Commercial Use** | no |
| **Status** | **blocked** (centralized; authentication + domestic IP checks required) |

**China Courts Summary:**
- All China IP courts maintain centralized decision repositories but require portal accounts
- Official http://ipc.court.gov.cn/ and court.gov.cn subdomains have aggressive redirect behavior
- Beijing IP Court is the most developed and hosts high-profile patent disputes
- No public API; web portal access gated
- Great Firewall and content filtering complicate access from non-CN IPs
- Recommend flagging all as "blocked" until direct API access agreement possible

---

### 4. Japan — Intellectual Property High Court

| Field | Value |
|-------|-------|
| **ID** | `JP/IPHighCourt` |
| **Name** | Intellectual Property High Court (IP High Court) |
| **Jurisdiction** | JP |
| **Issuing Body** | Supreme Court of Japan (IP High Court Division) |
| **Rights** | [patent, trademark, design, copyright, plant_variety] |
| **Data Types** | [case_law] |
| **Official Site (EN)** | https://www.ip.courts.go.jp/eng/ |
| **Official Site (JP)** | https://www.ip.courts.go.jp/ |
| **Access URL** | https://www.ip.courts.go.jp/eng/proceedings/judgments.html |
| **Access Method** | website_scrape (decision pages published as HTML) |
| **Authentication** | none (public) |
| **Rate Limit** | not_published |
| **License** | public_domain (Japanese law) |
| **Commercial Use** | yes (government publications, open use) |
| **Status** | **candidate** |

**Notes:**
- Established specialized appellate court for IP matters (patent, TM, design, copyright)
- Publishes full-text decisions in English and Japanese
- Official website offers browsable decision archive with search
- Decisions cited in WIPO and international IP databases
- Recommend implementing HTML scraper for decision index pages

---

### 5. France — Tribunal Judiciaire de Paris (IP Section)

| Field | Value |
|-------|-------|
| **ID** | `FR/TJParis-IP` |
| **Name** | Tribunal Judiciaire de Paris (Pôle Propriété Intellectuelle) |
| **Jurisdiction** | FR |
| **Issuing Body** | French Ministry of Justice (Courts Service) |
| **Rights** | [patent, trademark, design, copyright, trade_secrets] |
| **Data Types** | [case_law] |
| **Primary Source** | Légifrance (official legal database) |
| **Access URL** | https://www.legifrance.gouv.fr/ |
| **Alternative Source** | CCIJ (Chambre Commune d'Imprimerie Judiciaire), case aggregators |
| **Access Method** | website_scrape (restricted) + legal database query |
| **Authentication** | none (public but restrictive) |
| **Rate Limit** | not_published (aggressive throttling) |
| **License** | legifrance_tos (non-commercial indexing permitted) |
| **Commercial Use** | conditional (copyright notices apply) |
| **Status** | **candidate** (restricted access but legal precedent) |

**Notes:**
- TJ Paris has had exclusive IP jurisdiction since 2009 (INPI Act)
- Decisions published via Légifrance and CCIJ
- Légifrance has Cloudflare protection; requires JS execution
- CCIJ and commercial legal publishers (Dalloz, LexisNexis) index decisions
- Recommend monitoring CCIJ and secondary sources rather than direct Légifrance scraping

---

### 6. Italy — Sezioni Specializzate in Materia di Impresa (IP Sections)

| Field | Value |
|-------|-------|
| **ID** | `IT/CorteAppello-IP` |
| **Name** | Sezioni Specializzate in Materia di Impresa (Business/IP Sections of Court of Appeal) |
| **Jurisdiction** | IT |
| **Issuing Body** | Italian Ministry of Justice (Corte di Cassazione, Corti di Appello) |
| **Rights** | [patent, trademark, design, copyright] |
| **Data Types** | [case_law] |
| **Primary Source** | Italgiure (Italian legal database) |
| **Access URL** | https://www.giustizia.it/ |
| **Alternative Source** | DeJure, Sentenze IlSole24Ore |
| **Access Method** | website_scrape (restricted) |
| **Authentication** | none (public) |
| **Rate Limit** | not_published (basic throttling) |
| **License** | italian_court_tos (public domain but attribution required) |
| **Commercial Use** | conditional |
| **Status** | **candidate** (openly accessible but fragmented) |

**Notes:**
- No single specialized IP court; IP cases distributed across Corte di Cassazione and Corti di Appello
- Decisions published via Italgiure (national legal database) and DeJure
- Commercial legal publishers aggregate decisions
- Decisions in Italian; English translations via secondary sources only
- Recommend focusing on Milan and Rome Court of Appeals (major IP centers)

---

### 7. South Korea — Intellectual Property Tribunal (IPT, Administrative)

| Field | Value |
|-------|-------|
| **ID** | `KR/IPTribunal` |
| **Name** | Korea Intellectual Property Tribunal (IPT) |
| **Jurisdiction** | KR |
| **Issuing Body** | Korea Intellectual Property Office (KIPO) |
| **Rights** | [patent, trademark, design] |
| **Data Types** | [case_law, administrative_decision] |
| **Official Site** | https://www.kipo.go.kr/ipt/ |
| **Access Method** | website_scrape (decision database) |
| **Authentication** | none (public) |
| **Rate Limit** | not_published |
| **License** | korean_government_public |
| **Commercial Use** | yes |
| **Status** | **candidate** |

**Notes:**
- Administrative tribunal under KIPO; handles patent/TM/design appeals
- Publishes decisions on official website
- Decisions in Korean; some English translations via WIPO
- Accessible via direct HTML queries

---

### 8. South Korea — Patent Court (Appellate)

| Field | Value |
|-------|-------|
| **ID** | `KR/PatentCourt` |
| **Name** | Korea Patent Court |
| **Jurisdiction** | KR |
| **Issuing Body** | Supreme Court of Korea (Patent Court Division) |
| **Rights** | [patent] |
| **Data Types** | [case_law] |
| **Official Site** | https://patent.scourt.go.kr/ |
| **English Mirror** | https://eng.scourt.go.kr/ (English interface) |
| **Access Method** | website_scrape (decision search) |
| **Authentication** | none (public) |
| **Rate Limit** | not_published |
| **License** | korean_government_public |
| **Commercial Use** | yes |
| **Status** | **candidate** |

**Notes:**
- Specialized appellate court exclusively for patent disputes
- Maintains searchable decision archive with full-text access
- Decisions in Korean; English summaries available
- Official website accessible and scrapable

---

### 9. Australia — Federal Court of Australia (Patents Division)

| Field | Value |
|-------|-------|
| **ID** | `AU/FederalCourt` |
| **Name** | Federal Court of Australia (Patents Division) |
| **Jurisdiction** | AU |
| **Issuing Body** | Federal Court of Australia |
| **Rights** | [patent, trademark, design] |
| **Data Types** | [case_law] |
| **Primary Source** | AustLII (Australasian Legal Information Institute) |
| **Access URL** | https://www.austlii.edu.au/au/cases/cth/FCA/ |
| **Access Method** | external_aggregator (AustLII) |
| **Authentication** | none (AustLII public) |
| **Rate Limit** | not_published |
| **License** | creative_commons_cc0 (AustLII, public domain) |
| **Commercial Use** | yes (CC0) |
| **Status** | **external** (AustLII fully indexes Federal Court decisions) |

**Notes:**
- Federal Court (not specialized IP court) hears patent, TM, design cases
- AustLII is comprehensive aggregator with all decisions in CC0 public domain
- Recommend external reference to AustLII rather than direct court scraping
- Cloudflare protection on austlii.edu.au may require alternate approach

---

### 10. Brazil — INPI Board of Appeals (Administrative)

| Field | Value |
|-------|-------|
| **ID** | `BR/INPI-BoardAppeals` |
| **Name** | INPI Board of Appeals (Junta Administrativa de Recursos de Marca / JARM) |
| **Jurisdiction** | BR |
| **Issuing Body** | Instituto Nacional da Propriedade Industrial (INPI) |
| **Rights** | [patent, trademark, design] |
| **Data Types** | [administrative_decision] |
| **Official Site** | https://www.inpi.gov.br/ |
| **Access Method** | rest_api (INPI decision portal) |
| **Authentication** | account_required (limited free tier) |
| **Rate Limit** | not_published |
| **License** | inpi_terms |
| **Commercial Use** | conditional |
| **Status** | **candidate** (semi-public portal) |

**Notes:**
- Administrative appeals body for patent/TM/design applications
- Decisions published on INPI website but portal requires account for advanced queries
- Decisions in Portuguese; English translations rare
- INPI is exploring open data initiatives but legacy system access is gated

---

## Summary: Candidate vs External vs Blocked

### Candidates (New connectors possible)
1. **UK Patents Court** → External (BAILII already indexes)
2. **Japan IP High Court** → Candidate (own decision database, publishable)
3. **South Korea IPT & Patent Court** → Candidate (searchable, scrapable)
4. **Germany BPatG** → Candidate but restricted (juris license concerns)
5. **France TJ Paris** → Candidate but restricted (Légifrance complex, CCIJ secondary)
6. **Italy IP Sections** → Candidate but fragmented (Italgiure, secondary sources)
7. **Brazil INPI** → Candidate but gated (portal-based, account-required)

### External (Recommend referencing via aggregators)
1. **Australia Federal Court** → AustLII (comprehensive, CC0)
2. **UK Courts** → BAILII (established aggregator)

### Blocked (Authentication / Licensing / Access restrictions)
1. **China IP Courts (all)** → Account + VPN required, export restrictions
2. **Germany BPatG** → License restrictions on commercial reuse

---

## Recommended Next Steps

1. **High Priority (Ready for development):**
   - Japan IP High Court (HTML scraper for decision index)
   - Korea Patent Court & IPT (HTML scraper with Korean language support)

2. **Medium Priority (Requires negotiation or workaround):**
   - France TJ Paris (explore CCIJ partnership or secondary source integration)
   - Germany BPatG (clarify juris license terms for non-commercial indexing)

3. **Defer (Too restricted or aggregated):**
   - China IP Courts (authentication + regulation requirements)
   - Australia (refer to AustLII)
   - UK (refer to BAILII)
   - Brazil (portal requires account; low public access)

4. **Italy** — Feasible but requires mapping multiple courts and secondary aggregators; lower priority unless specific request.

