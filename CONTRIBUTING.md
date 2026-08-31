# Contributing

Contributions should preserve the library's offline test behavior, typed public
interfaces, provenance metadata, and credential-scrubbing guarantees.

## Set up the repository

Use Python 3.11, 3.12, or 3.13 and the locked dependency set:

```bash
uv sync --frozen --all-extras --group dev --group docs
uv run pre-commit install
```

Read `CONNECTOR_STANDARDS.md` before adding or changing a connector. Reuse the
existing client and response-envelope patterns. Add or change source metadata
in the canonical Markdown records under `catalog/sources/`; do not edit the
generated `coverage/sources.yaml` manifest directly.

## Validate a change

Run focused tests while developing. Before opening a pull request, run the same
gates used by CI:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check src/
uv run pytest --cov=patent_client_agents --cov-report=term --cov-fail-under=60
uv run python scripts/build_source_catalog.py --check
uv run python scripts/build_coverage.py --check
uv run python scripts/mcp_tool_counts.py --check-docs
uv run mkdocs build --strict
uv build
```

## Record HTTP cassettes safely

Tests replay VCR cassettes without network access by default. Use a connector's
explicit live flag only when a cassette is missing or intentionally being
refreshed. For example:

```bash
uv run pytest --run-live-uspto --vcr-record=once
uv run pytest --run-live-jpo --vcr-record=once
```

The shared VCR configuration redacts authorization headers, API-key query
parameters, cookies, and known OAuth request and response bodies. A new
credential flow needs a matching scrubber before any cassette is recorded.
Review every cassette diff, then scan tracked content:

```bash
gitleaks dir --config .gitleaks.toml --no-banner --redact .
```

Never commit live credentials, tokens, cookies, or unsanitized responses.

## Release

Releases publish through GitHub Actions and PyPI trusted publishing; they do not
use a stored PyPI API token.

1. Update `CHANGELOG.md`, `pyproject.toml`, plugin metadata, installation pins,
   and `uv.lock` together.
2. Run the complete validation suite and merge the release commit to `main`.
3. Tag the commit as `vX.Y.Z`, matching the version in `pyproject.toml`, and
   push the tag.
4. Confirm that the tag verification, three-version test matrix, package build,
   and OIDC publish jobs complete successfully.
