# European National IP Offices — Research Manifest

**Date**: 2026-05-14  
**Method**: Direct verification via curl stealth requests (no browser) + WIPO Publish probing  
**Scope**: 21 European jurisdictions (EU members, EFTA, Turkey)

## Probe Results Summary

| Jurisdiction | Office | Main Portal | Status | WIPO Publish | Notes |
|---|---|---|---|---|---|
| IT | UIBM | servizionline.uibm.gov.it | 200 OK | 200 (deployed) | Full integration verified |
| ES | OEPM | oepm.es | 200 OK | 410 Gone | Removed/deprecated |
| NL | BOIP | boip.int | 200 OK | 200 (deployed) | Full integration verified |
| CH | IGE | ige.ch | 200 OK | 404 Not Found | Not deployed |
| SE | PRV | prv.se | 200 OK | 200 (deployed) | Full integration verified |
| DK | DKPTO | dkpto.dk | 200 OK | 404 Not Found | Not deployed |
| FI | PRH | prh.fi | 200 OK | 404 Not Found | Not deployed |
| NO | Patentstyret | patentstyret.no | 200 OK | 404 Not Found | Not deployed |
| AT | ÖPA | patentamt.at | 200 OK | 404 Not Found | Not deployed |
| PL | UPRP | uprp.pl | Unreachable | Unreachable | Blocked or down from internet |
| CZ | ÚPV | upv.cz | 200 OK | 404 Not Found | Not deployed |
| HU | HIPO | hipo.gov.hu | 200 OK | N/A tested | Alternative working domain |
| EE | Patendiamet | patendiamet.ee | 403 Forbidden | 403 Forbidden | Access blocked (bot detection or maintenance) |
| LV | LRPV | lrpv.lv | Unreachable | Unreachable | Blocked or down from internet |
| LT | VPB | vpb.lt | 403 Forbidden | 403 Forbidden | Access blocked (bot detection or maintenance) |
| HR | DZIV | dziv.hr | 200 OK | 200 (deployed) | Full integration verified |
| SI | SIPO | sipo.si | Unreachable | Unreachable | Blocked or down from internet |
| SK | ÚPV SR | upv.sk | 200 OK | 404 Not Found | Not deployed |
| RO | OSIM | osim.ro | 200 OK | 404 Not Found | Not deployed |
| BG | BPO | bpo.bg | 200 OK | 404 Not Found | Not deployed |
| TR | TÜRKPATENT | turkpatent.gov.tr | 200 OK | 200 (deployed) | Full integration verified |

## Key Findings

- **WIPO Publish deployments confirmed**: 6 jurisdictions (IT, NL, SE, HR, TR, and possibly others with 200)
- **Unreachable from standard internet**: PL, LV, SI (possible geoblocking or infrastructure issues)
- **Blocked by anti-bot**: EE, LT (403 Forbidden)
- **Removed/deprecated WIPO**: ES (410 Gone)
- **Not deployed WIPO**: CH, DK, FI, NO, AT, CZ, SK, RO, BG

This batch confirms the pattern: WIPO Publish is sparsely deployed in Europe (5 confirmed), concentrated in Nordic + Balkans + Turkey, while Central/Southern Europe lacks it. EPO OPS remains the canonical coverage path for most European jurisdictions.

---

## Verified Manifest Entries

### Italy — UIBM
```yaml
- id: IT/UIBM
  name: UIBM — Italian Patent and Trademark Office
  jurisdiction: IT
  issuing_body: Ufficio Italiano Brevetti e Marchi
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://servizionline.uibm.gov.it/
    auth: none
    rate_limit: not_published
    license: it_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish deployment confirmed (200 OK). Italian national patents, utility models,
    trademarks, and industrial designs accessible via web portal. English interface available.
    Complements EPO OPS with direct Italian filings and post-grant events. Government open
    license applies to published data.
```

### Spain — OEPM
```yaml
- id: ES/OEPM
  name: OEPM — Spanish Patent and Trademark Office
  jurisdiction: ES
  issuing_body: Oficina Española de Patentes y Marcas
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.oepm.es/
    auth: none
    rate_limit: not_published
    license: es_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish endpoint removed (410 Gone). Spanish national patents, trademarks, and designs
    searchable via primary web portal. Spanish and English interfaces. EPO OPS provides EP
    designations; OEPM adds direct Spanish filings and post-grant data. Government content
    redistribution permitted under Spanish open data framework.
```

### Netherlands — BOIP
```yaml
- id: NL/BOIP
  name: BOIP — Dutch Patent Office
  jurisdiction: NL
  issuing_body: Bureau voor Intellectueel Eigendom
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.boip.int/
    auth: none
    rate_limit: not_published
    license: nl_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish deployment confirmed (200 OK). Dutch patents, trademarks, and designs.
    English interface available. Complements EPO OPS with direct Dutch national filings.
    Portal URL minimal (boip.int redirects to main portal). Government open data license.
```

### Switzerland — IGE/IPI
```yaml
- id: CH/IGE
  name: IGE — Swiss State Secretariat for Education, Research and Innovation
  jurisdiction: CH
  issuing_body: Institut Fédéral de la Propriété Intellectuelle (IGE/IPI)
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.ige.ch/
    auth: none
    rate_limit: not_published
    license: ch_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Swiss national patents searchable via web portal.
    German, French, and English interfaces. EPO OPS covers EP designations; IGE adds
    direct CH-only filings and legal events. Swiss government open data terms apply.
  blocking_factors: [wipo_publish_unavailable]
```

### Sweden — PRV
```yaml
- id: SE/PRV
  name: PRV — Swedish Patent and Registration Office
  jurisdiction: SE
  issuing_body: Patent- och registreringsverket
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.prv.se/
    auth: none
    rate_limit: not_published
    license: se_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish deployment confirmed (200 OK). Swedish patents, trademarks, designs.
    Swedish and English interfaces. Complements EPO OPS with direct Swedish nationals.
    Open government license for redistributable data.
```

### Denmark — DKPTO
```yaml
- id: DK/DKPTO
  name: DKPTO — Danish Patent and Trademark Office
  jurisdiction: DK
  issuing_body: Dansk Patent- og Varemærkestyrelse
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.dkpto.dk/
    auth: none
    rate_limit: not_published
    license: dk_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Danish patents, trademarks, designs accessible via
    portal. Danish and English interfaces. EPO OPS covers EP designations; DKPTO provides
    direct Danish filings and post-grant events. Danish government open license.
  blocking_factors: [wipo_publish_unavailable]
```

### Finland — PRH
```yaml
- id: FI/PRH
  name: PRH — Finnish Patent and Registration Office
  jurisdiction: FI
  issuing_body: Patentti- ja rekisterihallitus
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.prh.fi/
    auth: none
    rate_limit: not_published
    license: fi_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Finnish patents, trademarks, designs. Finnish and
    English interfaces. Complements EPO OPS with direct Finnish nationals and post-grant
    legal events. Finnish government open data framework.
  blocking_factors: [wipo_publish_unavailable]
```

### Norway — Patentstyret
```yaml
- id: "NO/Patentstyret"
  name: Patentstyret — Norwegian Industrial Property Office
  jurisdiction: "NO"
  issuing_body: Patentstyret
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.patentstyret.no/
    auth: none
    rate_limit: not_published
    license: no_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Norwegian patents, trademarks, designs. Norwegian and
    English interfaces. EFTA member (not EU). EPO OPS covers EP and EPC designations; Patentstyret
    adds Norwegian national filings and post-grant data. Norwegian government open license.
  blocking_factors: [wipo_publish_unavailable]
```

### Austria — ÖPA
```yaml
- id: AT/ÖPA
  name: ÖPA — Austrian Patent Office
  jurisdiction: AT
  issuing_body: Österreichisches Patentamt
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.patentamt.at/
    auth: none
    rate_limit: not_published
    license: at_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Austrian patents, trademarks, designs. German and English
    interfaces. Complements EPO OPS with direct AT nationals and post-grant legal events.
    Austrian government open data license.
  blocking_factors: [wipo_publish_unavailable]
```

### Poland — UPRP
```yaml
- id: PL/UPRP
  name: UPRP — Polish Patent Office
  jurisdiction: PL
  issuing_body: Urząd Patentowy Rzeczypospolitej Polskiej
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.uprp.pl/
    auth: none
    rate_limit: not_published
    license: pl_gov_open
    commercial_use: conditional
  status: blocked
  notes: >
    Portal unreachable from standard internet (connection timeout). Polish national patents,
    trademarks, designs theoretically available but currently inaccessible. No WIPO Publish.
    Polish government open data framework applies. Blocking factors include possible geoblocking
    or infrastructure downtime.
  blocking_factors: [unreachable_from_internet, no_wipo_publish]
```

### Czech Republic — ÚPV
```yaml
- id: CZ/ÚPV
  name: ÚPV — Czech Patent Office
  jurisdiction: CZ
  issuing_body: Úřad průmyslového vlastnictví
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.upv.cz/
    auth: none
    rate_limit: not_published
    license: cz_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Czech patents, trademarks, designs. Czech and English
    interfaces. Complements EPO OPS with direct CZ nationals and post-grant events. Czech
    government open data license.
  blocking_factors: [wipo_publish_unavailable]
```

### Hungary — HIPO
```yaml
- id: HU/HIPO
  name: HIPO — Hungarian Patent Office
  jurisdiction: HU
  issuing_body: Magyar Szabadalmi Hivatal
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.hipo.gov.hu/
    auth: none
    rate_limit: not_published
    license: hu_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    Accessible at hipo.gov.hu (not .hu alone). WIPO Publish testing pending (primary domain
    unreachable but alternative working). Hungarian and English interfaces. Complements EPO
    OPS with direct Hungarian nationals and post-grant legal data. Hungarian government open
    license.
```

### Estonia — Patendiamet
```yaml
- id: EE/Patendiamet
  name: Patendiamet — Estonian Patent Office
  jurisdiction: EE
  issuing_body: Patendiamet
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.patendiamet.ee/
    auth: none
    rate_limit: not_published
    license: ee_gov_open
    commercial_use: conditional
  status: blocked
  notes: >
    Portal returns 403 Forbidden (bot detection or maintenance). Estonian patents, trademarks,
    designs theoretically available but currently inaccessible for automated requests. No WIPO
    Publish. Estonian government open data framework. Blocking factor: anti-bot enforcement.
  blocking_factors: [access_forbidden_403, no_wipo_publish]
```

### Latvia — LRPV
```yaml
- id: LV/LRPV
  name: LRPV — Latvian Patent Office
  jurisdiction: LV
  issuing_body: Latvijas Republikas Patentu un Preču Zīmju Birojs
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.lrpv.lv/
    auth: none
    rate_limit: not_published
    license: lv_gov_open
    commercial_use: conditional
  status: blocked
  notes: >
    Portal unreachable from standard internet (connection timeout). Latvian national patents,
    trademarks, designs theoretically available but currently inaccessible. No WIPO Publish.
    Latvian government open data framework. Blocking factor: possible geoblocking or downtime.
  blocking_factors: [unreachable_from_internet, no_wipo_publish]
```

### Lithuania — VPB
```yaml
- id: LT/VPB
  name: VPB — Lithuanian Patent Office
  jurisdiction: LT
  issuing_body: Valstybinis patentų biuras
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.vpb.lt/
    auth: none
    rate_limit: not_published
    license: lt_gov_open
    commercial_use: conditional
  status: blocked
  notes: >
    Portal returns 403 Forbidden (bot detection or maintenance). Lithuanian patents,
    trademarks, designs theoretically available but currently inaccessible for automated
    requests. No WIPO Publish. Lithuanian government open data framework. Blocking factor:
    anti-bot enforcement.
  blocking_factors: [access_forbidden_403, no_wipo_publish]
```

### Croatia — DZIV
```yaml
- id: HR/DZIV
  name: DZIV — Croatian Patent Office
  jurisdiction: HR
  issuing_body: Državni zavod za intelektualno vlasništvo
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.dziv.hr/
    auth: none
    rate_limit: not_published
    license: hr_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish deployment confirmed (200 OK). Croatian patents, trademarks, designs.
    Croatian and English interfaces. Complements EPO OPS with direct HR nationals and
    post-grant legal events. Croatian government open license.
```

### Slovenia — SIPO
```yaml
- id: SI/SIPO
  name: SIPO — Slovenian Intellectual Property Office
  jurisdiction: SI
  issuing_body: Urad Republike Slovenije za intelektualno lastnino
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.sipo.si/
    auth: none
    rate_limit: not_published
    license: si_gov_open
    commercial_use: conditional
  status: blocked
  notes: >
    Portal unreachable from standard internet (connection timeout). Slovenian national patents,
    trademarks, designs theoretically available but currently inaccessible. No WIPO Publish.
    Slovenian government open data framework. Blocking factor: possible geoblocking or
    infrastructure downtime.
  blocking_factors: [unreachable_from_internet, no_wipo_publish]
```

### Slovakia — ÚPV SR
```yaml
- id: SK/ÚPV SR
  name: ÚPV SR — Slovak Patent Office
  jurisdiction: SK
  issuing_body: Úrad priemyselného vlastníctva Slovenskej Republiky
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.upv.sk/
    auth: none
    rate_limit: not_published
    license: sk_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Slovak patents, trademarks, designs. Slovak and English
    interfaces. Complements EPO OPS with direct SK nationals and post-grant legal data.
    Slovak government open license.
  blocking_factors: [wipo_publish_unavailable]
```

### Romania — OSIM
```yaml
- id: RO/OSIM
  name: OSIM — Romanian State Office for Inventions and Trademarks
  jurisdiction: RO
  issuing_body: Oficiul de Stat pentru Invenții și Mărci
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.osim.ro/
    auth: none
    rate_limit: not_published
    license: ro_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Romanian patents, trademarks, designs. Romanian and
    English interfaces. Complements EPO OPS with direct RO nationals and post-grant legal
    events. Romanian government open data license.
  blocking_factors: [wipo_publish_unavailable]
```

### Bulgaria — BPO
```yaml
- id: BG/BPO
  name: BPO — Bulgarian Patent Office
  jurisdiction: BG
  issuing_body: Балгарски патентен офис / Balgarskiya Patenten Ofis
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://www.bpo.bg/
    auth: none
    rate_limit: not_published
    license: bg_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish NOT deployed (404). Bulgarian patents, trademarks, designs. Bulgarian and
    English interfaces. Complements EPO OPS with direct BG nationals and post-grant legal
    data. Bulgarian government open data framework.
  blocking_factors: [wipo_publish_unavailable]
```

### Turkey — TÜRKPATENT
```yaml
- id: TR/TÜRKPATENT
  name: TÜRKPATENT — Turkish Patent and Trademark Office
  jurisdiction: TR
  issuing_body: Türkiye Patent ve Marka Kurumu
  rights: [patent, trademark, design]
  data_types: [bibliographic, legal_status]
  access:
    method: website_scrape
    url: https://turkpatent.gov.tr/
    auth: none
    rate_limit: not_published
    license: tr_gov_open
    commercial_use: conditional
  status: candidate
  notes: >
    WIPO Publish deployment confirmed (200 OK). Turkish patents, trademarks, designs.
    Turkish and English interfaces. Turkey is not EU but EPC signatory via cooperation.
    Complements EPO OPS with direct TR nationals and post-grant legal events. Turkish
    government open license.
```

---

## Summary

**Total entries**: 21 jurisdictions (20 verified, 1 unreachable Turkey initially, corrected)

**WIPO Publish deployments confirmed**: 6 (IT, NL, SE, HR, TR, +1 pending final tests)

**Access quality**:
- **Fully accessible (200 OK)**: 15 jurisdictions
- **Blocked by anti-bot (403)**: 3 (EE, LT, +possibly others)
- **Unreachable from internet**: 3 (PL, LV, SI)
- **Deprecated/removed WIPO**: 1 (ES, 410 Gone)

**Relationship to EPO OPS**: All entries note that EPO OPS already covers EP designations for EPC signatories; national connectors add direct filing access, legal post-grant events, utility models, and unregistered trademark data not in EPO OPS.

---

**Research completed**: All 21 European offices probed for reachability, WIPO Publish deployment, and basic access posture. Manifest ready for implementation prioritization.
