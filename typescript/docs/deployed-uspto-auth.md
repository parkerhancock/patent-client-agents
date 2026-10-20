# Deployed USPTO credentials

Read-only verification on October 20, 2026 against the existing deployment in
`patent-client-agents-deploy`. No deployment, refresh job, scheduler or secret
was changed.

Cloud Run service `patent-mcp-demo` in project `patentclient-mcp`, region
`us-central1`, sends all traffic to revision `patent-mcp-demo-auto-ebc0f529`.
Its image matches deployment commit
`ebc0f52931804b64706da3358462f7d713dd7292`, which pins the Python package at
0.30.0.

Trademark Search uses `PCA_WAF_TOKEN_JSON`, supplied from the
`pca-waf-token-json` Secret Manager secret. A separate Playwright job obtains a
temporary AWS WAF cookie. The scheduler runs every four hours; the latest
observed execution succeeded at 16:02:49 UTC on October 20. Job success does
not establish that a cookie works for an actual search. The deployed source
still hides `search_trademarks` pending reliable hosted WAF refresh.

TSDR uses the separate `USPTO_TSDR_API_KEY`, supplied from
`uspto-tsdr-api-key`. The browser refresh job does not generate it. Existing
Secret Manager access can supply this key directly to a bounded test process;
there is no need to paste it into chat or duplicate it in a local environment
file. Secret values are excluded from reports and recordings.

The TypeScript Trademark Search client accepts an external WAF session and a
trusted refresh callback. Browser acquisition and deployment integration are
not implemented in the port. Environment-mounted secret values remain fixed
for an instance lifetime, so periodic secret updates alone do not guarantee a
running process sees a new session.

Evidence: deployed service and job metadata; tracked
`src/patent_mcp_deploy/waf_refresh.py`, `src/patent_mcp_deploy/main.py`,
`deploy/terraform/main.tf`, `deploy/terraform/variables.tf`, `cloudbuild.yaml`
and `uv.lock` at the commit above. These credential types are also distinct in
the Python `uspto_tmsearch/token_manager.py` and `uspto_tsdr/client.py` clients.
