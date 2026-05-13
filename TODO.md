# patent-client-agents TODO

Things flagged but not yet done. Sorted by how much they'd hurt if we
left them unchecked. Add items as you find them; check them off in PRs
that fix them.

## User-decision / enablement

- [ ] **Publish `patent-client-agents` to PyPI.** Install-from-GitHub works fine and
      the plugin's `uvx --from ${CLAUDE_PLUGIN_ROOT}[mcp]` already "just
      works" without PyPI. PyPI would unlock the shorter `pip install patent-client-agents`
      / `uvx --from patent-client-agents[mcp]` forms used throughout the docs, and
      enable install-without-git-clone for non-plugin users. Register the
      project name, set up trusted publishing from GitHub Actions, cut a
      0.2.0 release.

- [ ] **Stand up the public remote MCP demo.** Deploy artifacts moved
      to [`parkerhancock/patent-client-agents-deploy`](https://github.com/parkerhancock/patent-client-agents-deploy)
      (Cloud Run + Google OAuth + Firestore rate limits). Still need: GCP
      project, OAuth client, custom domain, first `terraform apply`. Once
      live, swap the `patent-mcp-demo.example.com` placeholder in
      `docs/installation.md` §6 for the real hostname.

- [ ] **CI auto-deploy on merge to `main`.** Cloud Build trigger on the
      deploy repo pointing at `cloudbuild.yaml`. Needs the GCP project to
      exist and `roles/run.admin` + `roles/artifactregistry.writer` granted
      to the Cloud Build SA.

## Known issues (deferred)

- [ ] **MPEP and TMEP live calls fail against USPTO; replace with a local
      scrape-and-serve corpus.** Discovered while smoke-testing the v0.8.2
      promote (2026-05-13). Both subdomains misbehave when the library
      proxies live requests:

      - `mpep.uspto.gov/RDMS/MPEP/search` returns Apache `502 Proxy
        Error` for the library's `User-Agent: patent-client-agents-mpep/0.2`
        (set in `src/patent_client_agents/mpep/client.py:37`). The same
        URL with `User-Agent: Mozilla/5.0` returns 200. USPTO's WAF is
        bot-flagging the custom UA. Affects every endpoint in `client.py`
        (`/RDMS/MPEP/search`, `/result`, `/content`, `/current`) and so
        all of `search_mpep` and `get_mpep_section`.
      - `tmep.uspto.gov` returns 200 to direct curls with either the
        library UA or a Mozilla UA, but `search_tmep` and
        `get_tmep_section` consistently time out from prod. Different
        root cause from MPEP — likely a slow path or a different
        sub-endpoint the library polls. Needs reproduction with logging
        on to nail down.

      Short-term workaround would be to ship a Mozilla-like UA in both
      clients, but that's a fragile arms race with USPTO's WAF and
      doesn't help with the TMEP timeout. The right solution is to scrape
      both corpora once and serve from a static index bundled with the
      wheel (similar to how `cpc/` ships a snapshot, or the way the
      `skills/ip_research/` knowledge corpus is packaged via
      `importlib.resources`). Section text and search are both
      deterministic functions of the published MPEP/TMEP — there's no
      reason to round-trip to USPTO at runtime. A scheduled scrape job
      (monthly?) can republish a fresh wheel when the corpora update.

      Files most relevant:
      - `src/patent_client_agents/mpep/client.py` — URL paths + UA
      - `src/patent_client_agents/mpep/transformers.py` — HTML→model parser
      - `src/patent_client_agents/uspto_tmep/` — equivalent module for TMEP
      - Empirical proof from the v0.8.2 smoke test is in this session's
        Cloud Logging timestamp 2026-05-13T14:50:59Z (search
        `mpep.uspto.gov.*502` against `patent-mcp-demo` service logs).

- [ ] **`get_trademark_status` silently returns all-null fields — TSDR
      switched to JSON, parser still expects ST96 XML.** Discovered
      during the v0.8.2 prod smoke test (2026-05-13). The fix is small
      but the bug is total: every TSDR status call against live USPTO
      has been returning empty since whenever USPTO swapped the
      response format.

      The smoking gun is `src/patent_client_agents/uspto_tsdr/client.py`
      lines 494–495:

      ```python
      except ET.ParseError:
          return TrademarkStatus(serialNumber=serial_number)
      ```

      `_parse_status_xml` calls `ET.fromstring(response.text)`, but the
      live endpoint `https://tsdrapi.uspto.gov/ts/cd/casestatus/sn{serial}/info`
      now returns JSON (`{"trademarks": [{"status": {...}}]}`) when
      no `Accept: application/xml` is sent. The XML parser throws
      `ParseError`, the bare except swallows it, and the caller gets a
      `TrademarkStatus` with only `serialNumber` set and every other
      field at its model default (None / empty list).

      The test cassette
      `tests/cassettes/tests_uspto_tsdr_test_client_py_TestTsdrClientLive_test_get_status.yaml`
      already records a JSON body (`"trademarks": [...]`), so the test
      suite parse-fails identically to live — but the live tests are
      skipped by default (no `USPTO_TSDR_API_KEY` in CI), and the
      offline test (`test_models.py`) only exercises the Pydantic
      model, never the parser. The bug has zero test coverage and so
      slipped past the v0.8.0 trademark release.

      Two viable fixes, listed by effort:

      1. **Send `Accept: application/xml`** in the TSDR client headers
         and keep `_parse_status_xml`. Smallest possible diff. Risk:
         USPTO is clearly steering toward JSON-default; XML may be
         deprecated quietly at some point. Validate by recording a
         fresh cassette against live (header-set), confirming the body
         comes back as ST96 XML, and re-running.
      2. **Switch the parser to consume JSON**, matching the documented
         shape in the cassette. More work but follows USPTO's apparent
         direction. The JSON has a flatter structure — `trademarks[0]
         .status.mark` for `markText`, `trademarks[0].status.serialNumber`,
         etc. — and avoids the ST96 namespace dance. Drop
         `_parse_status_xml` entirely.

      Also, while in there: tighten the bare `except ET.ParseError` to
      log + reraise (or at minimum emit a `logger.warning`). A silent
      catch that ships an empty model is a footgun — exactly how this
      bug went undetected.

      Smoke evidence from the v0.8.2 cycle: serials `78787878`
      (cassette-known-good), `85088070`, and `88876181` all returned
      the all-null shape on prod. Re-run after fixing to confirm
      populated fields.

- [ ] **Re-record stale law-tools VCR cassettes** (TSDR + FedReserve).
      The TSDR test also needs a code update — the cassette recorded
      `/last-update/info.json?sn=...` but current client requests
      `/ts/cd/casestatus/sn.../info`. Needs live `USPTO_TSDR_API_KEY` to
      re-record.

- [ ] **Cold-start latency on first plugin use.** First `uvx` invocation
      after `/plugin install patent-client-agents@patent-client-agents` downloads ~100 packages and takes ~30
      seconds. Subsequent invocations hit uv's cache and are ~1s. Consider
      pre-warming the cache at plugin-add time (via a Claude Code install
      hook, if one ever gets blessed) or leaning on the skill-first UX
      where the agent can answer before the MCP is cold-started.

## Nice to have

- [ ] **Migrate JPO off its bespoke retry loop.** The JPO client inherits
      from `BaseAsyncClient` but overrides `_request` with its own
      AsyncRetrying loop to handle rate-limiting + token refresh on
      401/403. Consolidation would require moving rate-limit + auth-refresh
      hooks into `BaseAsyncClient`. Not done — the bespoke logic is
      justified and a refactor risk.

- [ ] **JPO module test coverage.** Credentials are restricted, so the
      pragmatic approach is recording VCR cassettes once against a known
      good fixture set and replaying thereafter.

## Done this session (2026-04-23)

- ✓ Skill references/*.md refreshed — EP Register section stripped from
  epo_ops.md (5 nonexistent methods); `resolve_document_by_publication_number`
  renamed to `resolve_publication` in uspto_publications.md; JPO method
  names corrected.
- ✓ `docs/api/` backfilled — added uspto-odp.md, uspto-assignments.md,
  uspto-office-actions.md.
- ✓ Monorepo CLAUDE.md lists patent-client-agents as a library-backed skill.
- ✓ `patent-client-agents-mcp --help` / `--version` works (was a bare `mcp.run()`).
- ✓ `USPTO Publications _poll_print_job()` has a 5-minute bounded timeout.
- ✓ `Google Patents` retry loop uses `law_tools_core.resilience.default_retryer`
  (consolidated from a bespoke `AsyncRetrying` instance).
- ✓ Module-level loggers + one meaningful `logger.warning()` at the XML-fallback
  path in USPTO applications / assignments / publications.
- ✓ Fixed latent bug: `from ...core.exceptions import NotFoundError` in
  `uspto_odp/clients/applications.py` (stale pre-extraction import that
  would have ImportError'd on first call).
- ✓ Skill `install.sh` prefers `uv` over `pip install --user`.
- ✓ Law-tools colline tests skip collection cleanly when `pdfplumber` is
  absent (pytest `collect_ignore_glob` gate, not a dep bump).
- ✓ Law-tools leaks scrubbed: LegiScan API key + 9 access_keys sanitized
  in the VCR cassette, VCR `filter_query_parameters` patched to catch
  `key=...` going forward, `.gitleaks.toml` allowlist for 3 known-safe
  findings (EDIS JWT example, Google Patents browser-inlined GCP key,
  placeholder `YOUR_*` strings). `gitleaks detect` → 0 leaks.
