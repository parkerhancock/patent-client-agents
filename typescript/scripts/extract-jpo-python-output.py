"""Record what the Python JPO connector makes of each converted cassette.

For every tests/cassettes/jpo-*.yaml, runs the Python models (JSON endpoints)
or parse_document_bundle (ZIP endpoints) on the recorded body and writes the
results to tests/fixtures/jpo/python-output.json, keyed by cassette name.
The TypeScript tests compare their output with it.

Run from typescript/:
    uv run --project .. python scripts/extract-jpo-python-output.py
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from patent_client_agents.jpo import models as m
from patent_client_agents.jpo.documents import parse_document_bundle

ROOT = Path(__file__).resolve().parents[1]
API = "https://ip-data.jpo.go.jp/api/"
PROGRESS = {
    "patent": m.PatentProgressData,
    "design": m.DesignProgressData,
    "trademark": m.TrademarkProgressData,
}
SIMPLE = {**PROGRESS, "patent": m.SimplifiedPatentProgressData}
DOC_KIND = {
    "app_doc_cont_opinion_amendment": "application",
    "app_doc_cont_refusal_reason_decision": "mailed",
    "app_doc_cont_refusal_reason": "refusal",
}


def convert(ip: str, endpoint: str, number: str, response: dict) -> object:
    body = response["body"]
    if endpoint in DOC_KIND:
        zip_bytes = bytes.fromhex(body["content"]) if body["type"] == "binary" else None
        bundle = parse_document_bundle(
            zip_bytes, DOC_KIND[endpoint], ip, application_number=number
        )
        return bundle.model_dump()
    result = m.ApiResult.model_validate(json.loads(body["content"])["result"])
    if not result.has_data or not result.data:
        return None
    data = result.data
    match endpoint:
        case "app_progress":
            return PROGRESS[ip].model_validate(data).model_dump()
        case "app_progress_simple":
            return SIMPLE[ip].model_validate(data).model_dump()
        case "priority_right_app_info":
            return [
                m.PriorityInfo.model_validate(p).model_dump()
                for p in data.get("priorityRightInformation", [])
            ]
        case "applicant_attorney_cd":
            return data.get("applicantAttorneyName") or None
        case "applicant_attorney":
            return [
                m.ApplicantAttorney.model_validate(a).model_dump()
                for a in data.get("applicantAttorney", [])
            ]
        case "case_number_reference":
            return m.NumberReference.model_validate(data).model_dump()
        case "cite_doc_info":
            return m.CitedDocumentsData.model_validate(data).model_dump()
        case "registration_info":
            return m.RegistrationInfo.model_validate(data).model_dump()
        case "jpp_fixed_address":
            return data.get("URL") or data.get("jplatpatUrl") or None
        case "pct_national_phase_application_number":
            return m.PctNationalPhaseData.model_validate(data).model_dump()
        case "divisional_app_info":
            return m.DivisionalAppInfoData.model_validate(data).model_dump()
    raise ValueError(f"Unmapped endpoint {endpoint}")


def main() -> None:
    output: dict[str, object] = {}
    for path in sorted((ROOT / "tests" / "cassettes").glob("jpo-*.yaml")):
        request, response = (
            yaml.safe_load(path.read_text())["interactions"][1][key]
            for key in ("request", "response")
        )
        ip, _, endpoint, *rest = request["uri"].removeprefix(API).split("/")
        output[path.stem] = convert(ip, endpoint, rest[-1], response)
    target = ROOT / "tests" / "fixtures" / "jpo" / "python-output.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(f"Wrote {len(output)} results to {target.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
