# BR/INPI — wave file (2026-05-18 priority-2 synopses)

Grounded API discovery for **INPI Brazil** (Instituto Nacional da
Propriedade Industrial) against the zero-infra-proxy constraint. The
existing 2026-05 detail survey at
[`connectors/inpi_brazil.md`](../../connectors/inpi_brazil.md) is
recapitulated below where still accurate; primary-source URLs are
re-verified against today's INPI sites.

Rights covered: patent, utility model (modelo de utilidade — sits inside
LPI's patent regime, not a separate filing track on the register UI),
trademark, design, computer-program registration, IC topography, GI.

---

## 1. Endpoint

INPI Brazil exposes **no public REST/JSON register API** for any of
patents, trademarks, or designs. The three programmatic surfaces are:

- **`busca.inpi.gov.br/pePI/`** — interactive HTML portal ("pePI",
  *Pesquisa em Propriedade Industrial*) over a single
  servlet (`busca.inpi.gov.br/pePI/servlet/...Controller`), switching
  by `tipoRecurso` / action between patents, trademarks, designs,
  software, technology contracts, and IC topographies. Server-rendered
  HTML, ASP/JSP forms, JSESSIONID cookies, free e-INPI login + CAPTCHA
  required to display detail pages.
  [Login controller](https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login),
  [Base de pesquisa landing](https://busca.inpi.gov.br/pePI/jsp/Base_pesquisa.jsp).
  No published OpenAPI / Swagger.
- **`servicos.busca.inpi.gov.br/`** — newer
  ["Plataforma de Serviços de Propriedade Industrial"](https://servicos.busca.inpi.gov.br/)
  with per-track entry points (e.g.
  [Search by Patents](https://servicos.busca.inpi.gov.br/patentes)).
  Still HTML; no machine-readable surface beyond what pePI offers
  underneath.
- **`revistas.inpi.gov.br/rpi/`** — the
  [Revista da Propriedade Industrial](https://revistas.inpi.gov.br/rpi/),
  weekly official bulletin. Three artefacts per issue: per-section
  PDF (e.g. `revistas.inpi.gov.br/pdf/Desenhos_Industriais2888.pdf` for
  RPI 2888, 2026-05-12), ZIP+TXT (`revistas.inpi.gov.br/txt/P{Number}.zip`),
  ZIP+XML (`revistas.inpi.gov.br/xml/{nomeArquivoEscritorio}`,
  filename via JSON manifest). Eight sections: Comunicados, Contratos
  de Tecnologia, Desenhos Industriais, Indicações Geográficas, Marcas,
  Patentes, Programas de Computador, Topografia de Circuitos
  Integrados. **Bulk feed, not a query API.**
- **`dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi`**
  — INPI catalogues both the [RPI dataset](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi)
  and the annual biblio cuts (e.g. `bw-p-{year}`) on the federal open-data
  portal. INPI organization page:
  [dados.gov.br INPI org](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi).
  Static ZIPs, no query endpoint.
- **`meu.inpi.gov.br/pag/swagger/index.html`** — a Swagger UI **does**
  exist at
  [meu.inpi.gov.br/pag/swagger/index.html](https://meu.inpi.gov.br/pag/swagger/index.html),
  but it backs the e-INPI **filing / petitioning** portal (account
  management, GRU bank slip generation), not the public register. Not
  a substitute for a read API; out of scope for our connector posture.

The pePI / servicos URLs are the live register **for humans**; RPI XML
and dados.gov.br are the bulk substrate **for machines**. Nothing in
between.

## 2. Auth

- **pePI**: free **e-INPI account** (name + email + CPF/CNPJ for
  Brazilian residents; foreign filers register with a passport
  identifier). Anonymous browse is allowed for hit lists; detail pages
  + petition history require login. CAPTCHA on session start, served
  via the Java/JSP servlet stack.
  [pePI login](https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login).
- **RPI download**: none.
  [revistas.inpi.gov.br/rpi](https://revistas.inpi.gov.br/rpi/) is open
  HTTP.
- **dados.gov.br**: none.
  [INPI dataset listing](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi)
  is anonymous CKAN over open ZIPs.
- **meu.inpi.gov.br**: gov.br federated SSO via the federal **Login Único**
  (`gov.br` account, CPF-anchored). Not relevant for a read connector.

Foreign-developer accessibility: dados.gov.br + RPI bulk = no
restriction. pePI registration is technically open to foreigners but
the UI is Portuguese-only and the verification flow assumes a CPF/CNPJ
where possible.

## 3. Query language

- **pePI**: HTML form fields per track (number, title, applicant,
  classification, dispatch code window). No documented URL parameter
  grammar; URLs are servlet POSTs with hidden state. CAPTCHA throttles
  any automated form submission.
- **RPI XML**: dispatch-code filtering happens **after** download — the
  XML is structured per section with INID + INPI's
  [Códigos e Abreviações](https://www.gov.br/inpi/pt-br/servicos/patentes/codigos-e-abreviacoes)
  dispatch dictionary. Schema documented at
  [`rpi_xml_marcas_versao_103.pdf`](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf)
  and analogues for patents / designs (INPI publishes layout-version
  bumps).
- **dados.gov.br**: filter datasets by tags (e.g. `tags=patentes` on
  [the dataset index](https://dados.gov.br/dataset?tags=patentes));
  individual datasets are static ZIPs, no SQL/SolR.
- No SolR, no Lucene, no GraphQL, no SPARQL. No CQL.

## 4. Pagination

- **pePI**: HTML hit lists paginate ~10/page via session cookies + page
  numbers in form state. No documented cap, no JSON envelope.
- **RPI XML**: pagination N/A — one ZIP per weekly issue per section.
  Current issues run ~2880-2890 (RPI 2888 = 2026-05-12).
- **dados.gov.br** CKAN: standard CKAN
  [`/api/3/action/package_search`](https://docs.ckan.org/en/latest/api/) at
  the federal portal (not INPI-specific) returns dataset metadata
  envelopes; ZIPs themselves are direct HTTP downloads, not paged.

## 5. Response shape

- **pePI**: HTML. Per-record detail view embeds dispatch history,
  classification codes (IPC / Nice / Locarno), applicant data, and the
  petition timeline as table rows. No JSON.
- **RPI ZIP+XML**: Per-section XML keyed by INPI's INID + dispatch
  vocabulary. Marcas schema: see
  [rpi_xml_marcas_versao_103.pdf](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf).
  Each issue is a `<revista>` envelope with per-act `<despacho>`
  children carrying numbers, dates, holders, codes. Patents and
  designs follow analogous per-section layouts published by INPI.
- **dados.gov.br annual biblio**: CSV + XML inside ZIPs. ~50-500 MB per
  ZIP (announced in
  [INPI's 2019 open-data release note](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-disponibiliza-dados-abertos-sobre-cinco-servicos)).
  Inventor / applicant / agent + IPC + dispatch history per record.

No primary source found for sample JSON of a single register hit
because **there is no JSON register surface to sample**.

## 6. Coverage scope

- **pePI**: patents from 1976-, trademarks from 1991-, designs from
  the 1970s- (older records partial; pre-digitisation gaps in the
  patent backfile).
  [Patent search basic guide (EN)](https://www.gov.br/inpi/en/services/patents/basic-guide/patent-search)
  links onward to pePI.
- **RPI ZIP+XML**: 2017-01-31 (RPI 2404) → present, all eight sections.
  Pre-2017 issues are PDF-only legacy.
  [RPI dataset on dados.gov.br](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi).
- **dados.gov.br annual**: per-year biblio cuts for patents, marks,
  designs, software registrations, technology-transfer contracts —
  five tracks under the
  [INPI org page](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi).

Backfile is therefore **structured (XML) since 2017** and
**unstructured / pePI-only before that**. Annual biblio recapitulates
the weekly feed at year granularity.

## 7. Rate limits / quotas

- **pePI**: undocumented; aggressive scraping triggers session resets
  + IP throttling (per the 2026-05 survey at
  [`connectors/inpi_brazil.md`](../../connectors/inpi_brazil.md) line
  27 — no primary-source page documents the throttle thresholds).
- **RPI HTTP**: no published rate limit; static ZIP downloads behind a
  CDN. No primary source for any cap.
- **dados.gov.br**: no published rate limit (CKAN metadata + static
  ZIP downloads).
- **meu.inpi.gov.br API**: out of scope — auth-gated to the filer's
  own account.

## 8. Terms of service

- **Open data licence**: INPI's open-data publication is governed by
  [Decreto 8.777/2016](https://www.planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8777.htm)
  + the INPI
  [Plano de Dados Abertos vigente](https://www.gov.br/inpi/pt-br/acesso-a-informacao/dados-abertos/plano-de-dados-abertos-vigente).
  Free reuse with source attribution (INPI / Decreto 8.777/2016). This
  covers dados.gov.br **and** the RPI feed.
- **pePI**: terms displayed at login implicitly prohibit automated
  scraping (CAPTCHA on the servlet itself is the enforcement). No
  primary source found for a standalone "Termos de Uso" page on the
  pePI servlet path beyond the login screen text.
- **Public records as such**: industrial-property files are public
  records under
  [Lei 9.279/1996 (LPI)](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm)
  Art. 19 ff. Reuse of register data carries no proprietary restriction
  — only the **delivery channel** (pePI vs. open-data ZIPs) is regulated.

## 9. Operational notes

- **Language**: Portuguese-only across pePI, servicos.busca, the RPI,
  and most of `gov.br/inpi`. INPI's English portal
  ([gov.br/inpi/en](https://www.gov.br/inpi/en)) is thin marketing,
  not regulatory.
- **Geofencing**: none observed; pePI + RPI + dados.gov.br all serve
  from inside Brazil but accept requests from outside.
- **Downtime**: pePI is the legacy stack; periodic outages are
  announced through the RPI "Comunicados" section
  ([RPI 2865 Comunicados PDF](https://revistas.inpi.gov.br/pdf/Comunicados2865.pdf)
  is a typical example). No SLA published.
- **Recent practice changes (affect dispatch-code semantics, not the
  surface itself)**: Portaria MDIC 110/2025 + Portaria INPI/PR 10/2025
  restructured the tariff table effective 2025-08-07 / -09-20 /
  -12-20; Portaria DIRPA 14/2024 changed patent-application form
  rules; Portaria PR 48/2024 launched PPH Phase V. These are noted by
  INPI's own news feed at
  [gov.br/inpi central-de-conteudo](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias).
- **Egress**: no primary source pins egress filtering for AWS / GCP IP
  ranges. Cloud Run egress should be tested empirically before any
  production proxy is designed (relevant to our zero-infra constraint
  per
  [`memory/project_cloud_run_egress.md`](../../../../personal/.claude/memory/project_cloud_run_egress.md)
  — not a public link).
- **Swagger surface at `meu.inpi.gov.br/pag/swagger/index.html`**:
  exists but documents the user-portal / petitioning APIs, requires a
  gov.br SSO session, and is not a register read API. No primary
  source publishes a developer-facing token model for it.

## 10. Verdict

**Verdict: 🔴 red_no_api** for the live register.

INPI Brazil exposes **no public REST/JSON register API** for patents,
trademarks, or designs. The live search UI (pePI) is HTML +
CAPTCHA + ToS-hostile to automated traffic. The cleanly licensed
machine-readable surfaces — the
[RPI weekly ZIP+XML](https://revistas.inpi.gov.br/rpi/) and
[dados.gov.br annual biblio dumps](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi)
— are **bulk feeds**, not query endpoints. Under our hard constraint
("proxy live APIs at runtime; do NOT host bulk dumps, build search
indexes, or maintain offline corpora"), bulk-only = no connector.

The verdict is **red** even though the bulk file fidelity is
genuinely good: weekly cadence, INID-coded XML, open licence, stable
schema. That richness only matters under a different operating model
(host the index, refresh weekly, expose query). Our model is "live API
proxy or nothing," and INPI Brazil offers no live API in that sense.

This contradicts the rating row currently in STATE.yaml
(`yellow_paid`), which was written when the operating definition was
less crisp. STATE.yaml owner should resolve to `red_no_api` on next
update.

---

## Drift vs. the 2026-05 detail survey

The older
[`connectors/inpi_brazil.md`](../../connectors/inpi_brazil.md) reads
the same situation **but recommends shipping `inpi_rpi` + `inpi_opendata`
as v1 scope** (lines 117-123) on the implicit assumption that we host
the bulk and expose a derived query. The 2026-05-16 worktree
(commit `8c0c2614`, branch `feature/... (RPI XML bulk + LPI statute
corpus)`) built exactly that:

- `inpi_br_bulk` — catalog + download Shape E surface
  (`list_inpi_br_bulk_releases`, `download_inpi_br_bulk`); per-section
  RPI XML ingestion was deferred.
- `inpi_br_statutes` — SQLite/FTS5 corpus over LPI 9.279/1996 (PT
  Planalto + EN WIPO Lex).
- `coverage/sources.yaml` entries `BR/INPI/RPI` and `BR/LPI/Statute`.

This work pre-dates the connector-standards sweep (CONNECTOR_STANDARDS.md
§5 MCP tool design rules; bulk-vs-proxy posture clarification). Two
issues against today's standards:

1. **The bulk-download tool surface mirrors USPTO ODP bulk and a few
   other Shape E ports** — that's defensible inside the standards
   (a "download catalog" tool that returns a `pca://` ResourceLink to
   a static ZIP is not the same as hosting a search index). The
   ingestion + indexing of RPI XML into our own store **is** off-spec
   for this repo.
2. **The statute corpus** (`inpi_br_statutes`) is on a parallel track
   (static-law module pattern, already used for IN, DE, FR, TW). That
   pattern remains in good standing. **That half is salvageable
   independent of the RPI bulk decision.**

## Recommended STATE.yaml resolution

- `rating: red_no_api` (was `yellow_paid`)
- `rating_basis: no public register REST API; live UI HTML+CAPTCHA; bulk RPI/dados.gov.br requires hosted indexing — off-spec`
- `connector_status: closed_bulk_only` *(or `none` if no enum slot
  exists; the orchestrator/owner picks; current `in_progress` is the
  stale state we are explicitly resolving)*
- Optional follow-up: file `BR/LPI/Statute` as a separate static-law
  connector candidate; do **not** revive `BR/INPI/RPI` for live
  register coverage.

## Sources (primary)

- INPI portal (PT): [gov.br/inpi/pt-br](https://www.gov.br/inpi/pt-br/)
- INPI portal (EN): [gov.br/inpi/en](https://www.gov.br/inpi/en)
- pePI login: [busca.inpi.gov.br/pePI](https://busca.inpi.gov.br/pePI/)
- pePI base de pesquisa: [busca.inpi.gov.br/pePI/jsp/Base_pesquisa.jsp](https://busca.inpi.gov.br/pePI/jsp/Base_pesquisa.jsp)
- Plataforma de Serviços: [servicos.busca.inpi.gov.br](https://servicos.busca.inpi.gov.br/)
- Search by Patents (EN): [gov.br/inpi/en/services/patents/basic-guide/patent-search](https://www.gov.br/inpi/en/services/patents/basic-guide/patent-search)
- Revista RPI: [revistas.inpi.gov.br/rpi](https://revistas.inpi.gov.br/rpi/)
- RPI Marcas XML schema (v1.03): [gov.br/inpi/.../rpi_xml_marcas_versao_103.pdf](https://www.gov.br/inpi/pt-br/backup/servicos/arquivos/rpi_xml_marcas_versao_103.pdf)
- Códigos e Abreviações (dispatch codes): [gov.br/inpi/pt-br/servicos/patentes/codigos-e-abreviacoes](https://www.gov.br/inpi/pt-br/servicos/patentes/codigos-e-abreviacoes)
- dados.gov.br INPI org page: [dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi](https://dados.gov.br/dados/organizacoes/visualizar/instituto-nacional-da-propriedade-industrial-inpi)
- RPI on dados.gov.br: [dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi](https://dados.gov.br/dados/conjuntos-dados/revista-da-propriedade-industrial-rpi)
- INPI open data plan: [gov.br/inpi/.../plano-de-dados-abertos-vigente](https://www.gov.br/inpi/pt-br/acesso-a-informacao/dados-abertos/plano-de-dados-abertos-vigente)
- INPI open-data release announcement (2019): [gov.br/inpi/.../noticias/inpi-disponibiliza-dados-abertos-sobre-cinco-servicos](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-disponibiliza-dados-abertos-sobre-cinco-servicos)
- Decreto 8.777/2016: [planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8777.htm](https://www.planalto.gov.br/ccivil_03/_Ato2015-2018/2016/Decreto/D8777.htm)
- LPI 9.279/1996: [planalto.gov.br/ccivil_03/leis/l9279.htm](https://www.planalto.gov.br/ccivil_03/leis/l9279.htm)
- Tabelas de Retribuição: [gov.br/inpi/pt-br/servicos/tabelas-de-retribuicao](https://www.gov.br/inpi/pt-br/servicos/tabelas-de-retribuicao)
- Tariff release note (Portaria MDIC 110/2025 + INPI/PR 10/2025): [gov.br/inpi/.../noticias/inpi-fixa-descontos-para-a-nova-tabela-de-retribuicoes-pelos-seus-servicos](https://www.gov.br/inpi/pt-br/central-de-conteudo/noticias/inpi-fixa-descontos-para-a-nova-tabela-de-retribuicoes-pelos-seus-servicos)
- Manual de Marcas: [manualdemarcas.inpi.gov.br](https://manualdemarcas.inpi.gov.br/)
- meu.inpi.gov.br Swagger (filing portal, not register): [meu.inpi.gov.br/pag/swagger/index.html](https://meu.inpi.gov.br/pag/swagger/index.html)
- Earlier detail survey: [`connectors/inpi_brazil.md`](../../connectors/inpi_brazil.md)
