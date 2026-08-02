# Eurasian Patent Office (EAPO)

**Layer:** regional  
**Jurisdiction:** EA  
**Issuing body:** Eurasian Patent Organization  
**Rights administered:** patent, industrial design  
**Working language:** Russian; selected English information services  
**Connector status:** skipped  
**Last verified:** 2026-08-02  
**Manifest entry:** not listed

**Detail survey:**
[`waves/2026-08-02-roadmap-batch/eapo.md`](../waves/2026-08-02-roadmap-batch/eapo.md)

## §1 Mission

The Eurasian Patent Office grants regional invention and industrial-design
rights. Its eight invention-system states are Armenia, Azerbaijan, Belarus,
Kazakhstan, Kyrgyzstan, Russia, Tajikistan, and Turkmenistan. The office also
maintains the official registers and publication services for those rights.

Primary source: [EAPO member states](https://www.eapo.org/en/about-eapo/states-party-to-the-convention/).

## §2 What's unique here

- The authoritative Eurasian patent register and legal-status history.
- Official application, grant, opposition, and status-change publications.
- Regional industrial-design applications and patents.
- EAPO procedural records not reproduced in bibliographic aggregators.

## §3 Programmatic surfaces

### Official publication services

| Field | Value |
|---|---|
| Endpoint | `https://www.eapo.org/pubservices/info/` |
| Auth | none for the browser interface |
| Format | JavaScript application with JSON backend calls |
| API status | undocumented |
| Robots posture | production backend paths are disallowed |
| Verdict | red for an automated connector |

EAPO moved its registers, gazettes, and publication server to a new platform
in August 2025. It preserved the retrospective data and public browser
functions. EAPO does not publish a supported API contract for this platform.
Its `robots.txt` disallows `/pubservices/prod/`, which is the backend path used
by the browser application. We should not build against that hidden endpoint.

Primary sources:

- [EAPO platform announcement](https://www.eapo.org/en/eapv-news-en/eapo-official-publication-services-launched-ona-new-platform/)
- [Eurasian patent register](https://www.eapo.org/pubservices/info/registry/inventions)
- [Eurasian publication server](https://www.eapo.org/pubservices/info/publications)
- [EAPO robots policy](https://www.eapo.org/robots.txt)

### EAPATIS

EAPATIS is EAPO's broader patent-information search system. EAPO describes
free institutional access through agreements with member-state libraries,
universities, and research centers. That access model is not a public API or
a suitable shared credential for this library.

Primary source: [EAPATIS access initiative](https://www.eapo.org/en/eapv-news-en/press-release-eapo-s-new-initiative-363/).

## §4 Fees

EAPO publishes separate fee statutes for inventions and industrial designs.
The office indexed several amounts effective February 1, 2026. This synopsis
links the schedules but does not reproduce fee amounts.

- [Invention fee statute](https://www.eapo.org/en/documents-2/basic-normative-legal-acts/statute-on-fees-of-the-eurasian-patent-organization-2/statute-on-fees-of-the-eurasian-patent-organization-2/)
- [Industrial-design fee statute](https://www.eapo.org/en/document/statute-on-fees-of-the-eurasian-patent-organization-for-legally-significant-and-other-actions-performed-in-relation-to-eurasian-design-applications-and-eurasian-design-patents/)

## §5 Connector strategy

### What we cover today

The existing EPO OPS and Google Patents connectors supply broad bibliographic
and publication coverage for Eurasian patent documents. They do not replace
the official EAPO register for authoritative current status.

### What we should add

Nothing now. A supported EAPO API would justify a dedicated register
connector because the official legal-status record is unique.

### What we should not add

Do not call the browser application's hidden `/pubservices/prod/` endpoints.
The office disallows that path and publishes no stability or reuse contract.

### Next steps

Check EAPO announcements each quarter for a documented public API or a
machine-readable bulk license. Keep the current higher-layer routes.

## §6 Open questions

- Will EAPO publish an API for the platform launched in 2025?
- Will EAPATIS offer individual or commercial machine access?
- Will the office publish industrial-design bulk data after its 2026 Hague accession?

## §7 References

- [Eurasian Patent Convention](https://www.eapo.org/en/documents-2/basic-normative-legal-acts/eurasian-patent-convention-v-2/)
- [EAPO member states](https://www.eapo.org/en/about-eapo/states-party-to-the-convention/)
- [Official publication platform announcement](https://www.eapo.org/en/eapv-news-en/eapo-official-publication-services-launched-ona-new-platform/)
- [2025 Administrative Council outcomes](https://www.eapo.org/en/eapv-news-en/outcomes-of-the-eapo-administrative-council-meeting/)

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-08-02 | Initial synopsis; rated red because the supported surface is browser-only and its backend path is disallowed. | [Detail survey](../waves/2026-08-02-roadmap-batch/eapo.md) |
