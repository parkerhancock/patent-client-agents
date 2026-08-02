# UAE Ministry of Economy and Tourism (AE)

**Layer:** national  
**Jurisdiction:** AE  
**Issuing body:** UAE Ministry of Economy and Tourism  
**Rights administered:** patent, utility model, industrial design, trademark  
**Working languages:** Arabic and English  
**Connector status:** skipped  
**Last verified:** 2026-08-02  
**Manifest entry:** not listed

**Detail survey:**
[`waves/2026-08-02-roadmap-batch/ae-moe.md`](../waves/2026-08-02-roadmap-batch/ae-moe.md)

## §1 Mission

The Ministry administers federal industrial-property and trademark services
for the United Arab Emirates. The industrial-property system covers patents,
utility models, designs, and integrated-circuit layouts. Separate Ministry
services cover trademarks and geographical indications.

Primary source: [Ministry eServices](https://www.moet.gov.ae/en/services).

## §2 What's unique here

- UAE national patent and utility-model application records.
- National industrial-design records and images.
- UAE national trademark prosecution and status data.
- Licensing, pledge, assignment, and post-grant records.

## §3 Programmatic surfaces

### Industrial Property Digital Library

| Field | Value |
|---|---|
| Endpoint | `https://eservices.moec.gov.ae/patent/IPDL` |
| Auth | Ministry login is part of the published procedure |
| Format | OutSystems JavaScript application |
| API status | no documented public API |
| Verdict | red for a connector |

The Ministry describes IPDL as a search service for published patent,
utility-model, and design records. Its service instructions start with a
Ministry login. The public application uses OutSystems and exposes no
supported machine interface.

Primary sources:

- [IPDL service page](https://www.moet.gov.ae/en/w/industrial-property-digital-library-1?assetEntryId=1303858)
- [IPDL application](https://eservices.moec.gov.ae/patent/IPDL)
- [Ministry eServices manual](https://www.moet.gov.ae/documents/20121/178047/Ministry%2Bof%2BEconomy%27s%2BeServices%2BManual%2B.pdf/b9c2c1fc-1099-d562-be19-ebe1b016bb33)

### Ministry open data

| Field | Value |
|---|---|
| Endpoint | `https://www.moet.gov.ae/en/web/guest/moec-opendata?q=patent` |
| Auth | none |
| Format | XLSX |
| Coverage | aggregate application, examination, publication, acceptance, and registration counts |
| Verdict | red for record retrieval; useful for statistics |

The July 2026 files contain aggregate measures by year, route, country, and
technical field. They do not contain application-level bibliographic records.
They therefore cannot back search or fetch tools.

Primary source: [Ministry patent open data](https://www.moet.gov.ae/en/web/guest/moec-opendata?q=patent).

### Trademark services

The old eServices portal exposes trademark filing and inquiry workflows, but
the inquiry pages require a user session. The Ministry publishes no public
trademark search API or bulk register.

Primary source: [Trademark eServices](https://services.economy.ae/m/Pages/CategoryServices.aspx?CategoryID=4&lang=en-US).

## §4 Fees

The Ministry publishes service-specific fees in AED on each filing service
page. Use the live service pages for current filing, examination, publication,
appeal, annuity, and recordation fees.

- [Patent registration service](https://www.moet.gov.ae/en/w/register-patents-%C2%A0)
- [Cabinet service-fee materials](https://www.moet.gov.ae/en/services)

## §5 Connector strategy

### What we cover today

The existing EPO OPS and Google Patents connectors provide broad patent
bibliography. WIPO services cover PCT and international-design records where
the UAE participates. They do not replace the national prosecution file.

### What we should add

Nothing now. Patent Hive is a filing and examination initiative, not a data
API. The aggregate open-data files are useful research inputs but cannot back
a record connector.

### What we should not add

Do not reverse-engineer the OutSystems session endpoints. They lack a public
contract and would create a fragile credentialed scraper.

### Next steps

Recheck the open-data catalog quarterly. Reopen connector planning if the
Ministry publishes application-level data or a documented IPDL API.

## §6 Open questions

- Will IPDL gain an anonymous documented search API?
- Will the open-data catalog publish row-level application indexes?
- Will the trademark inquiry service add a public search channel?

## §7 References

- [Industrial Property Services](https://www.moet.gov.ae/en/web/guest/w/patents-and-industrial-design-services-duplicate-0)
- [Patent Hive announcement](https://www.moet.gov.ae/en/-/ministry-of-economy-launches-%E2%80%98patent-hive%E2%80%99-initiative-to-support-inventors-in-patent-registration-and-strengthen-uae-s-global-competitiveness-in-innovation-and-creativity)
- [Patent open data](https://www.moet.gov.ae/en/web/guest/moec-opendata?q=patent)
- [Industrial-property implementing regulation](https://www.moet.gov.ae/documents/20121/0/CabinetDecision_6_2022_pdf.pdf/0986747f-bff8-5d43-7eff-323d811b0546?t=1715053035179)

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-08-02 | Initial synopsis; rated red because IPDL is session-based and current open data is aggregate only. | [Detail survey](../waves/2026-08-02-roadmap-batch/ae-moe.md) |
