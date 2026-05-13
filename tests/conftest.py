"""Pytest configuration for patent_client_agents tests.

Supports VCR recording for HTTP interactions:
    pytest tests/                           # replay from cassettes
    pytest tests/ --vcr-record=once         # record missing cassettes
    pytest tests/ --vcr-record=all          # re-record all cassettes

Cassettes are stored in ``tests/cassettes/`` with filenames derived from the
test nodeid.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import vcr

# JPO MCP tools are env-gated (see law_tools_core.mcp.conditional_tool).
# We need them registered during the test process so the JPO unit and
# dispatcher tests can call into them. Setting placeholder credentials
# at top-level conftest — before pytest collects test modules and before
# patent_client_agents.mcp.tools.international gets imported — flips
# registration on. Cassettes scrub real auth, so placeholders are fine.
# Tests that need to verify the *unset* path use monkeypatch.delenv +
# importlib.reload (see tests/jpo/test_env_gating.py).
os.environ.setdefault("JPO_API_USERNAME", "test_jpo_user")
os.environ.setdefault("JPO_API_PASSWORD", "test_jpo_pass")

# TSDR client (uspto_tsdr) requires USPTO_TSDR_API_KEY at construction
# time. Cassettes scrub the real key on record (the conftest filter
# rewrites uspto-api-key to REDACTED on both record and replay), so the
# placeholder here serves replay-only — it never reaches the network.
os.environ.setdefault("USPTO_TSDR_API_KEY", "test_tsdr_key")

# EUIPO Trademark/Design Search clients need OAuth2 client_credentials at
# construction time. Placeholders let unit tests build clients without
# touching the network; cassettes scrub the real access_token + body of
# the cas-server-webapp / auth-sandbox token endpoints on record (see
# _scrub_euipo_* below).
os.environ.setdefault("EUIPO_CLIENT_ID", "test_euipo_client")
os.environ.setdefault("EUIPO_CLIENT_SECRET", "test_euipo_secret")

USPTO_LIVE_ENV_VAR = "USPTO_LIVE_TESTS"
JPO_LIVE_ENV_VAR = "JPO_LIVE_TESTS"
EUIPO_LIVE_ENV_VAR = "EUIPO_LIVE_TESTS"

CASSETTES_DIR = Path(__file__).parent / "cassettes"
CASSETTES_DIR.mkdir(exist_ok=True)

_record_mode = "none"


def _sanitize_cassette_name(name: str) -> str:
    """Convert test nodeid to a cassette filename."""
    sanitized = re.sub(r"[^\w\-]", "_", name)
    sanitized = re.sub(r"_+", "_", sanitized)
    return sanitized.strip("_") + ".yaml"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live-uspto",
        action="store_true",
        default=False,
        help="Run tests that hit live USPTO endpoints",
    )
    parser.addoption(
        "--run-live-jpo",
        action="store_true",
        default=False,
        help="Run tests that hit live JPO endpoints",
    )
    parser.addoption(
        "--run-live-euipo",
        action="store_true",
        default=False,
        help="Run tests that hit live EUIPO endpoints (sandbox or production)",
    )
    try:
        parser.addoption(
            "--vcr-record",
            action="store",
            default="none",
            choices=["none", "once", "new_episodes", "all"],
            help="VCR record mode: none (replay), once (record if missing), new_episodes, all",
        )
    except ValueError:
        pass


def pytest_configure(config: pytest.Config) -> None:
    global _record_mode  # noqa: PLW0603
    _record_mode = config.getoption("--vcr-record", default="none")

    for marker in (
        "live_uspto: marks tests that require access to live USPTO services",
        "live_jpo: marks tests that require access to live JPO services",
        "live_euipo: marks tests that require access to live EUIPO services",
        "vcr_cassette: marks tests that use VCR cassette recording",
    ):
        config.addinivalue_line("markers", marker)


@pytest.fixture
def require_live_uspto(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live-uspto"))
    has_env = bool(os.getenv(USPTO_LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip(
            "Live USPTO test skipped. Set USPTO_LIVE_TESTS=1 or pass --run-live-uspto to enable."
        )


@pytest.fixture
def require_live_jpo(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live-jpo"))
    has_env = bool(os.getenv(JPO_LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip("Live JPO test skipped. Set JPO_LIVE_TESTS=1 or pass --run-live-jpo to enable.")


@pytest.fixture
def require_live_euipo(request: pytest.FixtureRequest) -> None:
    has_flag = bool(request.config.getoption("--run-live-euipo"))
    has_env = bool(os.getenv(EUIPO_LIVE_ENV_VAR))
    if not (has_flag or has_env):
        pytest.skip(
            "Live EUIPO test skipped. "
            "Set EUIPO_LIVE_TESTS=1 or pass --run-live-euipo to enable. "
            "Requires real EUIPO_CLIENT_ID/EUIPO_CLIENT_SECRET in env."
        )


def _scrub_euipo_token_request(request):
    """EUIPO OAuth2 client_credentials: scrub client_id/client_secret from request body.

    The cas-server-webapp (prod) and auth-sandbox (sandbox) token endpoints
    receive ``client_id`` + ``client_secret`` in the form body when the
    client_credentials grant is sent with credentials_in_body=True.
    Rewrite both to placeholders before the cassette hits disk.
    """
    import re as _re

    host = request.host
    is_euipo_token = ("euipo.europa.eu" in host and "cas-server-webapp" in request.path) or (
        "auth-sandbox.euipo.europa.eu" in host
    )
    if is_euipo_token and request.body:
        body = request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", "ignore")
        body = _re.sub(r"client_id=[^&]*", "client_id=REDACTED_CLIENT_ID", body)
        body = _re.sub(r"client_secret=[^&]*", "client_secret=REDACTED_CLIENT_SECRET", body)
        request.body = (
            body.encode("utf-8") if isinstance(request.body, (bytes, bytearray)) else body
        )
    return request


def _scrub_euipo_token_response(response):
    """EUIPO OAuth2 token response carries an access_token.

    Replace the body with a deterministic placeholder so committed
    cassettes never contain a real bearer token. Updates Content-Length
    so httpx replay accepts the rewritten body. EUIPO responses include
    ``access_token`` + ``token_type`` + ``scope`` + ``expires_in`` —
    distinct from JPO which also has ``refresh_token`` / ``id_token``.
    """
    body = response.get("body", {})
    raw = body.get("string", "") if isinstance(body, dict) else ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if (
        isinstance(raw, str)
        and "access_token" in raw
        and "token_type" in raw
        and "refresh_token" not in raw
    ):
        new_body = (
            '{"access_token": "REDACTED_ACCESS_TOKEN", '
            '"token_type": "Bearer", '
            '"expires_in": 7200, '
            '"scope": "uid"}'
        )
        body["string"] = new_body
        headers = response.get("headers", {})
        if isinstance(headers, dict):
            new_len = str(len(new_body.encode("utf-8")))
            for key in list(headers.keys()):
                if key.lower() == "content-length":
                    headers[key] = [new_len]
    return response


def _scrub_jpo_token_request(request):
    """JPO OAuth2 password-grant: scrub username/password from request body.

    Cassettes that hit ``ip-data.jpo.go.jp/auth/token`` carry the JPO
    user's password in the form-encoded request body. We rewrite it to
    placeholders so committed cassettes never carry real credentials.
    """
    import re as _re

    if "ip-data.jpo.go.jp" in request.host and request.path == "/auth/token" and request.body:
        body = request.body
        if isinstance(body, bytes):
            body = body.decode("utf-8", "ignore")
        body = _re.sub(r"username=[^&]*", "username=REDACTED_USERNAME", body)
        body = _re.sub(r"password=[^&]*", "password=REDACTED_PASSWORD", body)
        request.body = body.encode("utf-8") if isinstance(request.body, bytes) else body
    return request


def _scrub_jpo_token_response(response):
    """JPO OAuth2 token-endpoint response carries a JWT and refresh token.

    Replace the body with deterministic placeholders so JWTs never land
    on disk. Update Content-Length so httpx replay doesn't reject the
    rewritten body.
    """
    body = response.get("body", {})
    raw = body.get("string", "") if isinstance(body, dict) else ""
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "ignore")
    if isinstance(raw, str) and "access_token" in raw and "ip-data" not in raw:
        # Heuristic: only rewrite Keycloak-shaped token responses (they
        # have access_token + token_type + (id_token or refresh_token)).
        if "token_type" in raw and ("id_token" in raw or "refresh_token" in raw):
            new_body = (
                '{"access_token": "REDACTED_ACCESS_TOKEN", '
                '"expires_in": 3600, '
                '"refresh_expires_in": 28800, '
                '"refresh_token": "REDACTED_REFRESH_TOKEN", '
                '"token_type": "Bearer", '
                '"id_token": "REDACTED_ID_TOKEN", '
                '"not-before-policy": 0, '
                '"session_state": "REDACTED", '
                '"scope": "openid profile"}'
            )
            body["string"] = new_body
            headers = response.get("headers", {})
            if isinstance(headers, dict):
                new_len = str(len(new_body.encode("utf-8")))
                for key in list(headers.keys()):
                    if key.lower() == "content-length":
                        headers[key] = [new_len]
    return response


def _match_body_unless_oauth(r1, r2) -> bool:
    """VCR body matcher that ignores the body for OAuth2 token requests.

    JPO's ``/auth/token`` and EUIPO's ``/oidc/accessToken`` and
    ``/cas-server-webapp/oidc/accessToken`` endpoints receive secrets in
    the form body. We scrub those bodies before recording, so the
    recorded body never matches the placeholder body that gets sent at
    replay. This matcher trivially passes for token requests and falls
    back to byte-equality everywhere else.
    """
    oauth_paths = {
        "/auth/token",
        "/oidc/accessToken",
        "/cas-server-webapp/oidc/accessToken",
    }
    if r1.path in oauth_paths and r2.path in oauth_paths:
        return True
    return r1.body == r2.body


def _patch_vcr_httpcore_for_str_bodies() -> None:
    """Coerce vcr-deserialized response bodies to bytes for httpcore.

    vcrpy 8.x stores YAML responses as Python strings (not bytes) when the
    body is ASCII. It then passes that ``str`` straight to
    ``httpcore.Response(content=...)``. With httpx 0.28, the
    ``AsyncHTTPTransport`` asserts that the response stream is
    ``AsyncIterable``; a ``str`` is iterable but not async-iterable, so
    the assertion fires and the request looks like it returned a
    non-streaming response. The fix is to encode the str to bytes
    before httpcore wraps it.

    We monkey-patch once at import time. This is idempotent and only
    affects the deserialization path — recording is untouched.
    """
    import vcr.stubs.httpcore_stubs as h

    if getattr(h._deserialize_response, "_patched_for_str_bodies", False):
        return

    original = h._deserialize_response

    def _patched(vcr_response):
        body = vcr_response.get("body", {})
        s = body.get("string", "") if isinstance(body, dict) else ""
        if isinstance(s, str):
            body["string"] = s.encode("utf-8")
        return original(vcr_response)

    _patched._patched_for_str_bodies = True  # type: ignore[attr-defined]
    h._deserialize_response = _patched


_patch_vcr_httpcore_for_str_bodies()


def _chain_request_scrubbers(*scrubbers):
    """Compose request scrubbers in order."""

    def _chained(request):
        for s in scrubbers:
            request = s(request)
        return request

    return _chained


def _chain_response_scrubbers(*scrubbers):
    """Compose response scrubbers in order."""

    def _chained(response):
        for s in scrubbers:
            response = s(response)
        return response

    return _chained


def _create_vcr() -> vcr.VCR:
    v = vcr.VCR(
        cassette_library_dir=str(CASSETTES_DIR),
        record_mode=_record_mode,  # type: ignore[arg-type]
        filter_headers=[
            ("authorization", "REDACTED"),
            ("x-api-key", "REDACTED"),
            ("x-ibm-client-id", "REDACTED"),
            ("uspto-api-key", "REDACTED"),
            ("cookie", "REDACTED"),
            ("set-cookie", "REDACTED"),
        ],
        filter_query_parameters=[
            ("api_key", "REDACTED"),
            ("apiKey", "REDACTED"),
        ],
        before_record_request=_chain_request_scrubbers(
            _scrub_jpo_token_request,
            _scrub_euipo_token_request,
        ),
        before_record_response=_chain_response_scrubbers(
            _scrub_jpo_token_response,
            _scrub_euipo_token_response,
        ),
        decode_compressed_response=True,
        match_on=["method", "scheme", "host", "port", "path", "query", "oauth_safe_body"],
    )
    v.register_matcher("oauth_safe_body", _match_body_unless_oauth)
    return v


@pytest.fixture(scope="session")
def jpo_tools_registered() -> None:
    """Assert that the env-gated JPO MCP tools registered during test setup.

    Guards the conftest setup at the top of this file: if the placeholder
    JPO_API_USERNAME / JPO_API_PASSWORD vars aren't set BEFORE
    ``patent_client_agents.mcp.tools.international`` is imported, the
    ``@conditional_tool`` decorator skips registration and every JPO
    dispatcher test fails with a confusing AttributeError. Asserting at
    least one ``get_jpo_*`` tool is on ``international_mcp`` here turns
    that failure mode into a clear, single-line error.
    """
    import asyncio

    from patent_client_agents.mcp.tools.international import international_mcp

    tools = asyncio.run(international_mcp.list_tools())
    jpo_names = [t.name for t in tools if t.name.startswith("get_jpo_")]
    assert jpo_names, (
        "No get_jpo_* tools registered on international_mcp. "
        "Check that conftest.py sets JPO_API_USERNAME and JPO_API_PASSWORD "
        "before patent_client_agents.mcp imports occur."
    )


@pytest.fixture
def vcr_cassette(request: pytest.FixtureRequest):
    """Wrap a test in a VCR cassette keyed by its nodeid."""
    cassette_name = _sanitize_cassette_name(request.node.nodeid)
    cassette_path = CASSETTES_DIR / cassette_name

    my_vcr = _create_vcr()
    with my_vcr.use_cassette(str(cassette_path)):  # type: ignore[attr-defined]
        yield cassette_path
