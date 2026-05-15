"""Tests for the response envelope (CONNECTOR_STANDARDS.md §5.9)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from law_tools_core.envelope import (
    ListEnvelope,
    Provenance,
    ResponseEnvelope,
    configure,
    decode_cursor,
    encode_cursor,
    make_provenance,
)


class _Record(BaseModel):
    id: str
    name: str


def _fixed_provenance() -> Provenance:
    return Provenance(
        retrieved_at=datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC),
        source_url="https://example.test/api/foo",
        source_name="Example",
        cache_hit=False,
        connector_version="0.10.0",
    )


class TestProvenance:
    def test_required_fields(self):
        with pytest.raises(ValidationError):
            Provenance(  # type: ignore[call-arg]
                source_url="https://x",
                source_name="x",
                connector_version="0.1.0",
            )

    def test_substantive_law_fields_optional(self):
        p = _fixed_provenance()
        assert p.corpus_synced_at is None
        assert p.corpus_version is None

    def test_substantive_law_fields_set(self):
        synced = datetime(2026, 1, 1, tzinfo=UTC)
        p = Provenance(
            retrieved_at=datetime(2026, 5, 15, tzinfo=UTC),
            source_url="x",
            source_name="x",
            connector_version="0.1.0",
            corpus_synced_at=synced,
            corpus_version="R-07.2022",
        )
        assert p.corpus_synced_at == synced
        assert p.corpus_version == "R-07.2022"

    def test_frozen(self):
        p = _fixed_provenance()
        with pytest.raises(ValidationError):
            p.cache_hit = True  # type: ignore[misc]


class TestMakeProvenance:
    def test_defaults_retrieved_at_to_now(self):
        before = datetime.now(UTC)
        p = make_provenance("https://x", "X")
        after = datetime.now(UTC)
        assert before <= p.retrieved_at <= after

    def test_uses_configured_connector_version(self):
        configure("9.9.9-test")
        try:
            p = make_provenance("https://x", "X")
            assert p.connector_version == "9.9.9-test"
        finally:
            configure("unknown")

    def test_explicit_connector_version_overrides(self):
        configure("9.9.9-test")
        try:
            p = make_provenance("https://x", "X", connector_version="1.2.3")
            assert p.connector_version == "1.2.3"
        finally:
            configure("unknown")

    def test_passes_through_corpus_fields(self):
        synced = datetime(2026, 1, 1, tzinfo=UTC)
        p = make_provenance(
            "https://x",
            "X",
            corpus_synced_at=synced,
            corpus_version="R-07.2022",
            connector_version="0.1.0",
        )
        assert p.corpus_synced_at == synced
        assert p.corpus_version == "R-07.2022"


class TestResponseEnvelope:
    def test_round_trip(self):
        env: ResponseEnvelope[_Record] = ResponseEnvelope(
            summary="One record.",
            details=_Record(id="abc", name="Acme"),
            provenance=_fixed_provenance(),
        )
        dumped = env.model_dump()
        assert dumped["summary"] == "One record."
        assert dumped["details"] == {"id": "abc", "name": "Acme"}
        assert dumped["provenance"]["source_name"] == "Example"


class TestListEnvelope:
    def test_empty(self):
        env: ListEnvelope[_Record] = ListEnvelope(
            summary="No results.",
            items=[],
            provenance=_fixed_provenance(),
        )
        assert env.items == []
        assert env.next_cursor is None
        assert env.more_available is False

    def test_with_items_and_cursor(self):
        env: ListEnvelope[_Record] = ListEnvelope(
            summary="2 of 5 records.",
            items=[_Record(id="a", name="A"), _Record(id="b", name="B")],
            next_cursor=encode_cursor({"offset": 2}),
            more_available=True,
            provenance=_fixed_provenance(),
        )
        assert len(env.items) == 2
        assert env.more_available
        assert decode_cursor(env.next_cursor) == {"offset": 2}


class TestCursors:
    def test_round_trip(self):
        payload = {"offset": 100, "limit": 25, "filter": "patent"}
        token = encode_cursor(payload)
        assert decode_cursor(token) == payload

    def test_token_is_url_safe(self):
        token = encode_cursor({"a" * 50: "b" * 50})
        assert "+" not in token
        assert "/" not in token
        assert "=" not in token  # padding stripped

    def test_deterministic(self):
        a = encode_cursor({"b": 2, "a": 1})
        b = encode_cursor({"a": 1, "b": 2})
        assert a == b

    def test_decode_rejects_garbage(self):
        with pytest.raises(ValueError, match="not valid base64"):
            decode_cursor("!!!not base64!!!")

    def test_decode_rejects_non_object(self):
        import base64
        import json

        raw = json.dumps([1, 2, 3]).encode("utf-8")
        bad_token = base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
        with pytest.raises(ValueError, match="must be a JSON object"):
            decode_cursor(bad_token)

    def test_decode_handles_missing_padding(self):
        token = encode_cursor({"x": 1})
        # token has no padding by construction
        assert decode_cursor(token) == {"x": 1}
