from __future__ import annotations

import yaml

from scripts import build_coverage


def test_manifest_id_maps_cross_prefix_source_to_entity() -> None:
    source = {"id": "CA/CanLII", "name": "CanLII"}
    state = {
        "entities": [
            {
                "id": "CA/CIPO",
                "name": "CIPO Canada",
                "manifest_ids": ["CA/CanLII"],
            }
        ]
    }

    payload = build_coverage.build_atlas_payload([source], state)

    assert payload["entities"][0]["shipped_sources"] == [
        {
            "id": "CA/CanLII",
            "name": "CanLII",
            "rights": [],
            "data_types": [],
            "access_method": None,
            "auth": None,
            "status": None,
            "module": None,
        }
    ]
    assert payload["unattached_sources"] == []


def test_repository_atlas_has_only_classified_standalone_sources() -> None:
    sources = yaml.safe_load(build_coverage.SOURCES_YAML.read_text())["sources"]
    state = yaml.safe_load(build_coverage.STATE_YAML.read_text())

    payload = build_coverage.build_atlas_payload(sources, state)
    standalone = payload["unattached_sources"]

    assert len(standalone) == 12
    assert all(source.get("atlas_standalone_reason") for source in standalone)
    assert {source["id"] for source in standalone} == {
        "BR/LPI/Statute",
        "CA/FederalCourt/CourtFiles",
        "CN/SPC_IPCourt/HearingNotices",
        "JP/IPHC/PatentUtilityModelCaseLists",
        "US/CAFC/Opinions",
        "US/USITC/DataWeb",
        "US/USITC/EDIS",
        "US/USITC/HTS",
        "US/USITC/IDS",
        "WO/Google/Patents",
        "WO/PCT/Guidelines",
        "WO/WIPO/Fees/PCT",
    }


def test_repository_cross_prefix_sources_resolve_to_expected_entities() -> None:
    sources = yaml.safe_load(build_coverage.SOURCES_YAML.read_text())["sources"]
    state = yaml.safe_load(build_coverage.STATE_YAML.read_text())

    payload = build_coverage.build_atlas_payload(sources, state)
    source_owner = {
        source["id"]: entity["id"]
        for entity in payload["entities"]
        for source in entity["shipped_sources"]
    }

    assert source_owner["EP/EPC/Statute"] == "EP/EPO"
    assert source_owner["UP/EPO/UPGuidelines"] == "EP/EPO"
    assert source_owner["EP/EUIPO/Fees/Trademarks"] == "EM/EUIPO"
    assert source_owner["EP/EUIPO/Fees/Designs"] == "EM/EUIPO"
    assert source_owner["CA/CanLII"] == "CA/CIPO"
    assert source_owner["FR/Legifrance/IP"] == "FR/INPI"
    assert source_owner["AU/IPAU/Fees/Patents"] == "AU/IPAustralia"
    assert source_owner["IN/IPIN/Fees/Patents"] == "IN/IPO"
    assert source_owner["TW/MOJ/TradeSecretsAct"] == "TW/TIPO"
    assert source_owner["WO/WIPO/Fees/Madrid"] == "WO/WIPO/Madrid"
    assert source_owner["WO/WIPO/Fees/Hague"] == "WO/WIPO/Hague"
