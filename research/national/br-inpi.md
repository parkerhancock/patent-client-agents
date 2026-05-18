# INPI Brazil (BR) — national

**Layer:** national
**Jurisdiction:** BR (WIPO ST.3: BR)
**Issuing body:** Instituto Nacional da Propriedade Industrial (INPI)
**Rights administered:** patent, utility model (modelo de utilidade —
inside LPI patent regime), trademark, design, geographical indication
(industrial GIs), integrated-circuit topography, computer-program
registration
**Working languages:** Portuguese (primary, near-exclusive). EN portal
is thin marketing only.
**Connector status:** **none** — closed out; no live register API meets
our zero-infra-proxy constraint. Static-law module (`BR/LPI/Statute`)
queued separately.
**Last verified:** 2026-05-18
**Manifest entry:** *not yet listed* — older 2026-05 worktree drafted
`BR/INPI/RPI` and `BR/LPI/Statute` but did not integrate to main; see §5.

**Detail surveys:**
- [`connectors/inpi_brazil.md`](../connectors/inpi_brazil.md) — 2026-05 detail survey (cross-asset inventory: pePI, dados.gov.br, RPI, statutes, courts).
- [`waves/2026-05-18-priority-2-synopses/br-inpi.md`](../waves/2026-05-18-priority-2-synopses/br-inpi.md) — 2026-05-18 grounded API discovery; locks in the red rating.

**Higher layers covering this office transitively:**
- **EPO INPADOC** (via [`regional/epo.md`](../regional/epo.md)) — BR patent biblio + family + legal events when there is a corresponding EP publication or PCT national-phase entry; BR-national-only filings partial.
- **WIPO PATENTSCOPE** — PCT applications + national-phase data with BR as receiving/designated office.
- **WIPO Madrid** — Madrid IRs designating Brazil (BR acceded effective 2019-10-02; see [WIPO Madrid contracting parties](https://www.wipo.int/treaties/en/ShowResults.jsp?treaty_id=8)).
- **WIPO Hague** — Brazil is not party; BR national designs are INPI-exclusive.

---

## §1 Mission

INPI is Brazil's national IP office under MDIC and the only
authoritative registrar for BR-national patents, utility models,
trademarks, industrial designs, geographical indications,
integrated-circuit topographies, and computer-program registrations
([gov.br/inpi/pt-br](https://www.gov.br/inpi/pt-br/)). It is the largest
IP office in Latin America (~30k patent filings/year, ~300k trademark
filings/year per the older detail survey). Brazil joined the Madrid
Protocol in 2019, so post-2019 "Brazilian trademarks" are
non-trivially WIPO Madrid IR designations; pre-2019 backfile and
BR-national-only filings remain INPI-exclusive.

## §2 What's unique here

- **BR-national patents (incl. utility models)** — non-EP/PCT national
  filings; some mirrored in EPO INPADOC at biblio fidelity; full
  prosecution detail is INPI-only.
- **BR-national trademarks** — large absolute volume even after Madrid;
  pre-Madrid backfile is BR-only on the register side.
  ([Marcas service page](https://www.gov.br/inpi/pt-br/servicos/marcas))
- **BR national designs** — Brazil is not a Hague contracting party; no
  parallel coverage in WIPO Hague.
- **Computer-program registrations under
  [Lei 9.609/1998](https://www.planalto.gov.br/ccivil_03/leis/l9609.htm)** —
  copyright-equivalent right administered by INPI on a register
  distinct from patents.
- **Integrated-circuit topographies under
  [Lei 11.484/2007](https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/lei/l11484.htm)** —
  sui generis, low volume; INPI-exclusive.
- **Industrial / artisanal GIs** under LPI Title IV (Arts. 176–182)
  ([guia básico](https://www.gov.br/inpi/pt-br/servicos/indicacoes-geograficas/guia-basico));
  distinct from agricultural GIs (MAPA).
- **INPI administrative decisions** — patent / TM oppositions and
  nullity actions resolve administratively at INPI with decisions
  published in the RPI. No PTAB-style portal.

## §3 Programmatic surfaces

### pePI — live register UI

| Field | Value |
|---|---|
| Endpoint | [`busca.inpi.gov.br/pePI/`](https://busca.inpi.gov.br/pePI/) |
| Auth | Free e-INPI account (partial anonymous browse) + CAPTCHA |
| Format | Server-rendered HTML, JSP/servlet, JSESSIONID cookies |
| Rate limit | Undocumented; session-reset + IP-throttle observed; no primary source publishes thresholds |
| ToS posture | CAPTCHA-enforced anti-automation; no standalone "Termos de Uso" page found beyond the [login screen](https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login) |
| Rating | 🔴 Red — HTML + CAPTCHA; no API beneath |
| Primary source | [pePI login](https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login) |

Live register is HTML-only and CAPTCHA-gated. The newer
[`servicos.busca.inpi.gov.br`](https://servicos.busca.inpi.gov.br/) is
the same data with a friendlier shell, still HTML.

### Revista da Propriedade Industrial (RPI) weekly XML

| Field | Value |
|---|---|
| Endpoint | [`revistas.inpi.gov.br/rpi/`](https://revistas.inpi.gov.br/rpi/); per-section PDF + ZIP+TXT + ZIP+XML |
| Auth | None |
| Format | PDF / ZIP+TXT / ZIP+XML; INID + dispatch-coded |
| Rate limit | None published; static ZIPs |
| ToS posture | [Decreto 8.777/2016](https://www.planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8777.htm) open licence; free reuse with attribution |
| Rating | 🔴 Red — bulk feed, not query API; hosting an index off-spec |
| Primary source | [RPI dataset on dados.gov.br](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi) |

Cleanly licensed, well-structured bulk XML since 2017-01-31 (RPI
2404). Weekly Tuesdays; RPI 2888 was 2026-05-12. Schema docs at
[`rpi_xml_marcas_versao_103.pdf`](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf)
(marcas; analogous PDFs for patents / designs). Fidelity is good — it
just isn't a query API.

### dados.gov.br — annual biblio dumps

| Field | Value |
|---|---|
| Endpoint | [INPI org page](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi) |
| Auth | None |
| Format | CSV + XML inside ZIPs; CKAN metadata over the top |
| Rate limit | None published |
| ToS posture | Decreto 8.777/2016 open licence |
| Rating | 🔴 Red — bulk; same disposition as RPI |
| Primary source | [INPI open-data release note](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-disponibiliza-dados-abertos-sobre-cinco-servicos) |

Annual biblio cuts for five tracks (patents, marks, designs, software,
technology-transfer contracts); recapitulates RPI at year granularity.

### meu.inpi.gov.br Swagger (filing portal — NOT register)

| Field | Value |
|---|---|
| Endpoint | [`meu.inpi.gov.br/pag/swagger/index.html`](https://meu.inpi.gov.br/pag/swagger/index.html) |
| Auth | gov.br federated SSO (CPF-anchored) |
| Scope | e-INPI user portal — account, GRU bank slip, petitioning |
| Rating | 🔴 Red — not a register read API; SSO is not delegable |
| Primary source | [Swagger UI](https://meu.inpi.gov.br/pag/swagger/index.html) |

Noted here so future-us doesn't re-discover it and mistake it for the
missing register API.

## §4 Fees

**Policy: link only.** INPI publishes a consolidated Brazilian Real
(BRL) tariff under Portaria MDIC 110/2025 + Portaria INPI/PR 10/2025
(effective in phases through late 2025), covering **patents** (filing,
search/examination, annuities), **utility models**, **trademarks**
(filing/renewal per class), **industrial designs**, **GIs**, **computer
programs**, **IC topographies**, and **technology-transfer contracts**.

- **Official schedule:** [Tabelas de Retribuição — INPI](https://www.gov.br/inpi/pt-br/servicos/tabelas-de-retribuicao)
- **Rate adjustment notice:** [INPI fixa descontos para a nova Tabela de Retribuições](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-fixa-descontos-para-a-nova-tabela-de-retribuicoes-pelos-seus-servicos)
- **Statutory basis:** [Lei 9.279/1996 (LPI)](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm)

Discount programs *(name + one-line eligibility — no amounts, no dates)*:

- **50% reduction** — natural persons, microenterprises (ME), individual
  microentrepreneurs (MEI), small businesses (EPP), simple-innovation
  enterprises, scientific & technological institutions (ICTs),
  non-profit entities, public bodies.
- **Full exemption** — persons in financial hardship and persons with
  disabilities registered in CadÚnico or the National PcD Register.

## §5 Connector strategy

### What we cover today

- Nothing on-main for BR. The 2026-05-16 worktree (commit `8c0c2614`)
  drafted `inpi_br_bulk` (RPI Shape E download catalog) and
  `inpi_br_statutes` (LPI 9.279/1996 SQLite/FTS5 corpus) but did **not**
  integrate to main and pre-dates the connector-standards sweep.
- BR patent biblio / family transitively via
  [`patent_client_agents.epo_ops`](../regional/epo.md) (INPADOC).
- BR Madrid TM designations transitively via WIPO Madrid (no shipped
  connector yet).

### What we should NOT add

**Recommendation: close out the stale 2026-05 RPI-bulk worktree.** The
wave file re-verified primary sources and confirms there is no public
REST register API at INPI Brazil. The bulk feeds (RPI weekly XML,
dados.gov.br annual) are openly licensed and high-fidelity but require
us to host an index to expose query semantics — violating the repo's
hard constraint (proxy live APIs at runtime; do NOT host bulk dumps or
build search indexes). Bulk-richness is not load-bearing.

- **pePI scraping** — HTML + CAPTCHA + ToS-hostile + brittle. No.
- **`inpi_br_bulk` (RPI Shape E)** — defensible only if reframed as a
  pure pass-through catalog returning `pca://` ResourceLinks to static
  ZIPs (no on-our-side parsing). Even then: low caller value (end user
  gets a ZIP), and we'd own the
  [schema-version chase](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf).
- **`inpi_br_opendata` (annual biblio)** — recapitulates RPI; same call.
- **meu.inpi.gov.br Swagger** — filer-portal scope only. Not a register
  API.

### What we *could* still add (separate decision)

- **`BR/LPI/Statute` — static-law module.** LPI 9.279/1996 is unusually
  consolidated: one master law covers patents (Title I), designs (II),
  marks (III), GIs (IV), and trade-secret / unfair-competition (V). PT
  corpus from
  [Planalto Lei 9.279/1996](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm)
  + optional EN from
  [WIPO Lex Brazil](https://www.wipo.int/wipolex/en/legislation/profile/BR)
  replaces 4–5 separate statute mirrors. Same pattern as IN, DE, FR, TW.
  The stale worktree already drafted this half; **salvageable** — queue
  separately from the bulk decision.
- **`BR/Lei9609/Software` + `BR/Lei11484/IC`** — adjacent statutes,
  cheap to fold into the same static corpus once LPI ships.

### Next steps

1. **Close the bulk worktree.** Delete the
   `feature/...-rpi-bulk` branch or archive as reference-only under
   `connectors/`. Do not revive `inpi_br_bulk` for live-register coverage.
2. **File a separate BACKLOG entry for `BR/LPI/Statute`**; reuse the
   worktree's Planalto + WIPO Lex ingestion.
3. **STATE.yaml** updates: `rating: red_no_api`, `connector_status: none`,
   `next_action: monitor`.
4. **Monitor** the [INPI news feed](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias)
   and the [Plano de Dados Abertos vigente](https://www.gov.br/inpi/pt-br/acesso-a-informacao/dados-abertos/plano-de-dados-abertos-vigente)
   for any future "API pública de consulta" announcement.

## §6 Open questions

- **Does `meu.inpi.gov.br/pag/swagger/index.html` ever extend to public
  register reads?** No primary source confirms or denies. It is the
  only signal that INPI runs a modern API stack internally; whether
  any of it gets externalized is the live unblock question.
- **RPI XML schema-version drift.** INPI bumps
  [`rpi_xml_marcas_versao_NNN.pdf`](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf)
  periodically; no primary-source changelog page found.
- **Foreign-developer registration on pePI / e-INPI.** Empirically
  unclear how much CPF/CNPJ-anchored friction non-BR registrants face.
  No primary source found beyond the implicit PT-only flow.
- **WIPO Madrid coverage of BR designations vs. INPI national.** Once
  Madrid Monitor matures in our coverage, does BR uniqueness shrink
  further on the TM side? Likely yes for post-2019 IRs; pre-2019
  backfile unaffected.

## §7 References

Primary sources only — `gov.br/inpi`, `busca.inpi.gov.br`,
`revistas.inpi.gov.br`, `dados.gov.br`, `planalto.gov.br`, WIPO.

**INPI service entry points:**
- [INPI portal (PT)](https://www.gov.br/inpi/pt-br/) · [INPI portal (EN)](https://www.gov.br/inpi/en)
- [pePI](https://busca.inpi.gov.br/pePI/) · [pePI login](https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login) · [Plataforma de Serviços](https://servicos.busca.inpi.gov.br/)
- [Search by Patents (EN)](https://www.gov.br/inpi/en/services/patents/basic-guide/patent-search) · [Marcas](https://www.gov.br/inpi/pt-br/servicos/marcas) · [GIs guia básico](https://www.gov.br/inpi/pt-br/servicos/indicacoes-geograficas/guia-basico) · [Manual de Marcas](https://manualdemarcas.inpi.gov.br/)

**Open data + RPI:**
- [Revista RPI](https://revistas.inpi.gov.br/rpi/) · [RPI dataset on dados.gov.br](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi) · [INPI org on dados.gov.br](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi)
- [INPI open-data release note (5 services)](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-disponibiliza-dados-abertos-sobre-cinco-servicos) · [Plano de Dados Abertos vigente](https://www.gov.br/inpi/pt-br/acesso-a-informacao/dados-abertos/plano-de-dados-abertos-vigente)
- [RPI Marcas XML schema v1.03](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf) · [Códigos e Abreviações](https://www.gov.br/inpi/pt-br/servicos/patentes/codigos-e-abreviacoes)

**Statutes & licensing basis:**
- [LPI — Lei 9.279/1996](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm) · [Lei 9.609/1998 (software)](https://www.planalto.gov.br/ccivil_03/leis/l9609.htm) · [Lei 11.484/2007 (IC topographies)](https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/lei/l11484.htm)
- [Decreto 8.777/2016 (open-data policy)](https://www.planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8777.htm) · [WIPO Lex Brazil profile](https://www.wipo.int/wipolex/en/legislation/profile/BR)

**Fees:**
- [Tabelas de Retribuição](https://www.gov.br/inpi/pt-br/servicos/tabelas-de-retribuicao) · [2025 tariff release note](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-fixa-descontos-para-a-nova-tabela-de-retribuicoes-pelos-seus-servicos)

**Filing portal (not a register API):**
- [meu.inpi.gov.br Swagger UI](https://meu.inpi.gov.br/pag/swagger/index.html)

**Detail survey + wave:**
- [`connectors/inpi_brazil.md`](../connectors/inpi_brazil.md) · [`waves/2026-05-18-priority-2-synopses/br-inpi.md`](../waves/2026-05-18-priority-2-synopses/br-inpi.md)

---

## §8 Change log

| Date | Change | Source |
|---|---|---|
| 2026-05-18 | Initial synopsis. Rated 🔴 red_no_api against the zero-infra-proxy constraint — no public register REST API; pePI is HTML+CAPTCHA; RPI ZIP+XML and dados.gov.br annual dumps are bulk-only and would require hosted indexing. Recommends closing the stale 2026-05-16 RPI-bulk worktree for live-register coverage and queuing `BR/LPI/Statute` separately as a static-law module candidate. Drift vs. older detail survey: the survey recommended shipping `inpi_rpi` + `inpi_opendata` as v1 scope, which presupposed an indexing posture we've since ruled off-spec. | [waves/2026-05-18-priority-2-synopses/br-inpi.md](../waves/2026-05-18-priority-2-synopses/br-inpi.md) |
