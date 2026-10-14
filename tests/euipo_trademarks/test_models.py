"""Pydantic model tests for euipo_trademarks.

Drives the models with fixtures captured from a real sandbox response
(see ``tests/fixtures/euipo/``) and synthetic edge cases. No network.
"""

from __future__ import annotations

import json
from pathlib import Path

from patent_client_agents.euipo_trademarks import (
    GoodsAndServicesClass,
    MarkBasis,
    MarkFeature,
    Status,
    Trademark,
    TrademarkSearchResult,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "euipo"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_search_result_parses_full_register_listing() -> None:
    data = _load("tm_list_size10.json")
    result = TrademarkSearchResult.model_validate(data)

    assert len(result.trademarks) == 10
    assert result.total_elements == 2_354_583
    assert result.total_pages == 235_459
    assert result.page == 0
    assert result.size == 10

    first = result.trademarks[0]
    assert first.application_number == "000274084"
    assert first.status == Status.EXPIRED
    assert first.mark_feature == MarkFeature.FIGURATIVE
    assert first.mark_basis == MarkBasis.EU_TRADEMARK
    assert first.nice_classes == [25, 34]
    assert first.word_mark_specification is not None
    assert first.word_mark_specification.verbal_element == "RIZLA+ INTERNATIONAL"
    assert first.applicants[0].name == "John Player & Sons Limited"
    assert first.applicants[0].office == "EM"
    assert first.publications[0].bulletin_number == "1998/054"


def test_search_result_apple_query() -> None:
    data = _load("tm_apple_size10.json")
    result = TrademarkSearchResult.model_validate(data)
    assert result.total_elements > 100  # 739 at capture time
    verbals = {
        tm.word_mark_specification.verbal_element
        for tm in result.trademarks
        if tm.word_mark_specification is not None
    }
    # At least one result references "Apple" in some form
    assert any("apple" in v.lower() for v in verbals)


def test_is_live_and_is_registered_helpers() -> None:
    expired = _payload(status="EXPIRED", appno="000000001")
    registered = _payload(status="REGISTERED", appno="000000002")

    assert not Trademark.model_validate(expired).is_live
    assert not Trademark.model_validate(expired).is_registered
    assert Trademark.model_validate(registered).is_live
    assert Trademark.model_validate(registered).is_registered


def test_goods_and_services_terms_in() -> None:
    cls = GoodsAndServicesClass.model_validate(
        {
            "classNumber": 25,
            "description": [
                {"language": "en", "terms": ["shirts", "trousers"]},
                {"language": "fr", "terms": ["chemises", "pantalons"]},
            ],
        }
    )
    assert cls.class_number == 25
    assert cls.terms_in("en") == ["shirts", "trousers"]
    assert cls.terms_in("fr") == ["chemises", "pantalons"]
    assert cls.terms_in("xx") == []


def test_extra_fields_allowed() -> None:
    """Forward-compat: unknown fields shouldn't break parsing."""
    payload = _payload(status="REGISTERED", appno="000000003")
    payload["mysteryFutureField"] = {"a": 1}
    tm = Trademark.model_validate(payload)
    assert tm.application_number == "000000003"
    # Field is preserved on the model instance (extra="allow")
    assert tm.mysteryFutureField == {"a": 1}


def _payload(*, status: str, appno: str) -> dict:
    """Minimal valid Trademark payload for testing helpers."""
    return {
        "applicationNumber": appno,
        "status": status,
        "statusDate": "2020-01-01",
        "markFeature": "WORD",
        "niceClasses": [9],
        "applicationLanguage": "en",
        "goodsAndServices": [],
    }
