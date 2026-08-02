# EAPO discovery note

**Entity:** `RU/EAPO`  
**Verified:** 2026-08-02  
**Verdict:** `red_no_api`

EAPO operates public invention and industrial-design registers, gazettes, and
a publication server. It moved these services to a new JavaScript platform in
August 2025 and preserved all retrospective data.

The browser loads data through `/pubservices/prod/`. EAPO publishes no API
contract for that backend, and its `robots.txt` disallows the path. EAPATIS
offers richer searching, but its free-access program uses institutional
agreements in member states. Neither route supports a shared library connector.

The official register remains useful for manual verification. Existing EPO OPS
and Google Patents tools provide broad publication discovery. A future EAPO API
would add authoritative status and regional-design data.

Primary evidence:

- [Platform announcement](https://www.eapo.org/en/eapv-news-en/eapo-official-publication-services-launched-ona-new-platform/)
- [Register](https://www.eapo.org/pubservices/info/registry/inventions)
- [Publication server](https://www.eapo.org/pubservices/info/publications)
- [Robots policy](https://www.eapo.org/robots.txt)
- [EAPATIS access initiative](https://www.eapo.org/en/eapv-news-en/press-release-eapo-s-new-initiative-363/)
