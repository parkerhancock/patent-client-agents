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

A subsequent bounded native Bun Trademark Search probe used the existing WAF
secret only in subprocess memory and the exact User-Agent from the deployed
refresh source. One public query returned HTTP200 and one normalized result.
Its scrubbed response replays offline. This verifies that session from this
host for one query, not automatic refresh or hosted Cloud Run reliability.

The TypeScript port now has a separate Bun/Playwright acquisition worker and
browser-free file or Secret Manager session delivery. The default MCP client
polls the configured source and reloads after WAF rejection. Fresh browser
acquisition through protected-file delivery to an actual MCP search was
verified locally. See [WAF worker](waf-worker.md) for setup and validation.
Production cutover has not occurred. Environment-mounted secret values remain
fixed for an instance lifetime, so that legacy configuration alone does not
deliver periodic secret updates to a running process.

Evidence: deployed service and job metadata; tracked
`src/patent_mcp_deploy/waf_refresh.py`, `src/patent_mcp_deploy/main.py`,
`deploy/terraform/main.tf`, `deploy/terraform/variables.tf`, `cloudbuild.yaml`
and `uv.lock` at the commit above. These credential types are also distinct in
the Python `uspto_tmsearch/token_manager.py` and `uspto_tsdr/client.py` clients.
