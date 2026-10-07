# Configure local source access

Local Python, plugin, and stdio deployments can use office credentials and
locally built legal corpora. Configure them once in the environment that starts
Patent Client Agents.

## Set credentials

Most connectors work without keys. Export credentials for restricted sources
in the shell that launches Python or your agent client:

```bash
export USPTO_ODP_API_KEY="…"
export USPTO_TSDR_API_KEY="…"
export EPO_OPS_API_KEY="…"
export EPO_OPS_API_SECRET="…"
```

Restart the client after changing its environment.

| Variable | Source | How to get |
|---|---|---|
| `USPTO_ODP_API_KEY` | USPTO Open Data Portal | [developer.uspto.gov](https://developer.uspto.gov/) (free) |
| `USPTO_TSDR_API_KEY` | USPTO Trademark Status & Document Retrieval | [account.uspto.gov/api-manager/](https://account.uspto.gov/api-manager/) (free MyUSPTO account; pick the TSDR API product) |
| `EPO_OPS_API_KEY`, `EPO_OPS_API_SECRET` | EPO Open Patent Services | [developers.epo.org](https://developers.epo.org/) (free, 4 GB/week) |
| `JPO_API_USERNAME`, `JPO_API_PASSWORD` | JPO J-PlatPat | Contact JPO (restricted). JPO MCP tools register in local/private servers when both variables are set; they are intentionally absent from the public hosted demo. |
| `DPMA_CONNECTPLUS_USERNAME`, `DPMA_CONNECTPLUS_PASSWORD` | DPMAconnectPlus | [Apply through DPMA](https://www.dpma.de/english/search/data_supply_services/dpmaconnect/index.html). A registered static IP is also required. The connector is mock-only tested and live compatibility is unverified. |
| `IPI_DATA_USERNAME`, `IPI_DATA_PASSWORD` | Swiss IPI datadelivery | [Apply through IPI](https://www.ige.ch/en/services/digital-resources/ip-data/data-delivery-api) by submitting signed Terms of Use. The connector is schema-tested only and live compatibility is unverified. Set optional `IPI_DATA_TOTP_TOKEN` for an MFA account. |
| `OEPM_CEO_USERNAME`, `OEPM_CEO_PASSWORD` | OEPM Spain CEO | [Apply through OEPM web services](https://www.oepm.es/es/sobre-OEPM/servicios-al-ciudadano/servicios-gratuitos/Servicios-web-de-la-OEPM/). The connector is public-WSDL tested only. |
| `IPONZ_SUBSCRIPTION_KEY` | IPONZ New Zealand | [Subscribe through the MBIE IPONZ API portal](https://portal.api.business.govt.nz/api/iponz). Set optional `IPONZ_ACCESS_TOKEN` when required. The connector is public-contract tested only. |
| `DIP_DATA_EXCHANGE_TOKEN` | Thailand DIP | [Apply through DIP Data Exchange](https://api.ipthailand.go.th/data-exchange/view/home.aspx). Paper-contract registration is required. The connector is official-catalogue tested only. |
| `CANLII_API_KEY` | CanLII | [canlii.org/en/feedback/feedback.html](https://www.canlii.org/en/feedback/feedback.html) (free, by request) |
| `EUIPO_CLIENT_ID`, `EUIPO_CLIENT_SECRET` | EUIPO Trademark + Design Search | [dev.euipo.europa.eu](https://dev.euipo.europa.eu/) (sandbox auto-approves; production requires ID-document review). Set `EUIPO_ENV=sandbox` to point at the sandbox. |
| `USITC_EDIS_TOKEN` | USITC EDIS (Section 337) | [edis.usitc.gov](https://edis.usitc.gov) > API Token Generator (free Login.gov account). JWT, ~2 wk lifetime. Required for attachment downloads even on public documents. |
| `USITC_DATAWEB_TOKEN` | USITC DataWeb (US trade statistics) | [dataweb.usitc.gov](https://dataweb.usitc.gov) account page (free). Needed only for `run_dataweb_report`. |
| `PCA_WAF_TOKEN_PATH` *or* `PCA_WAF_TOKEN_JSON` | USPTO Trademark Search (TESS) | Bring-your-own AWS WAF token (~4 day lifetime), *or* install the `[tmsearch]` extra to mint via Playwright in-process. See [Add live USPTO trademark search](#add-live-uspto-trademark-search). |

Google Patents, USPTO Publications, USPTO Assignments, USPTO Trademark
Assignments, MPEP, TMEP, WIPO Lex, Federal Circuit (CAFC), US Copyright
Office, USITC HTS, USITC IDS, and the UPC decisions feed need no
credentials.

## Add live USPTO trademark search

USPTO TESS sits behind AWS WAF. To mint the WAF token in-process,
install the optional extra and bootstrap Chromium once:

```bash
pip install 'patent-client-agents[tmsearch]'
playwright install chromium
```

On headless server deployments where Playwright isn't installed, set
`PCA_WAF_TOKEN_JSON` to a token JSON payload (Secret Manager mount) or
`PCA_WAF_TOKEN_PATH` to a path on disk: the client will reuse the
cached token until it expires (~4 days). A typical pattern is to run a
Playwright job on a workstation, write the token JSON into a secret,
and mount it into the server container at runtime.

## Build local corpora

`MpepClient`, `TmepClient`, and the UPC statutes tools read from local
SQLite/FTS5 snapshots instead of calling upstream sources. The wheel
ships the builders; build each corpus once into the default cache:

```bash
patent-client-agents-build-mpep-corpus \
    --output ~/.cache/patent_client_agents/mpep.db
patent-client-agents-build-tmep-corpus \
    --output ~/.cache/patent_client_agents/tmep.db
patent-client-agents-build-upc-statutes-corpus \
    --output ~/.cache/patent_client_agents/upc_statutes.db
```

MPEP is ~50MB and takes ~4 minutes; TMEP is ~16MB and takes ~2 minutes;
UPC statutes (UPCA + Rules of Procedure + Table of Fees, EN/FR/DE) is
~2MB and takes well under a minute. Re-run periodically to pick up
revisions.

For cloud deployments, build the corpora into the container image and
set `MPEP_CORPUS_PATH` / `TMEP_CORPUS_PATH` / `UPC_STATUTES_CORPUS_PATH`
in the runtime env to point at the output paths. The published wheel
stays small (no corpus bundled); refresh becomes "rebuild + redeploy."

If a call is made before the corpus exists, the client raises
`CorpusUnavailable` with the build command in the message: there is
no silent fallback to live HTTP.

When deployments use a corpus manifest, check local readiness without
downloading files:

```bash
patent-client-agents-bootstrap-corpora MANIFEST_URI --check
patent-client-agents-bootstrap-corpora MANIFEST_URI --check --json
```

The command exits with status 1 when a selected corpus is missing or its
SHA-256 does not match the manifest.
