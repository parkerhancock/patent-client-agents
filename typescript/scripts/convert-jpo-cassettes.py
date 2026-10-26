"""Convert the Python JPO vcrpy cassettes into Cassetter cassettes.

No JPO credentials exist for a fresh TypeScript recording, so the
TypeScript tests replay the Python live recordings of May 7, 2026
(tests/cassettes/tests_jpo_test_live_py_*.yaml). Each distinct GET becomes
one cassette, ``tests/cassettes/jpo-<ip>-<endpoint>-<number>.yaml``, holding
that request and the token exchange before it.

The Python recorder already replaced the username, password and every token
with REDACTED placeholders; this script re-checks that and drops the
authorization header, AWS request ids and the stale Content-Length of the
scrubbed token body.

Run from typescript/:
    uv run --project .. python scripts/convert-jpo-cassettes.py
"""

from __future__ import annotations

import json
import re
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "tests" / "cassettes"
TARGET = ROOT / "tests" / "cassettes"
API = "https://ip-data.jpo.go.jp/api/"
DROP_HEADERS = {
    "authorization",
    "content-length",
    "content-encoding",
    "set-cookie",
    "x-amz-cf-id",
    "x-amz-cf-pop",
    "x-amzn-trace-id",
    "x-amz-apigw-id",
    "x-amzn-requestid",
}
SECRET = re.compile(r"eyJ[A-Za-z0-9_-]{10,}|Bearer [A-Za-z0-9]")


class Literal(str):
    pass


def literal(dumper: yaml.Dumper, value: Literal) -> yaml.Node:
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")


yaml.add_representer(Literal, literal)


def headers(raw: dict) -> dict:
    return {
        key.lower(): [str(v) for v in values]
        for key, values in raw.items()
        if key.lower() not in DROP_HEADERS
    }


def body(content: object) -> dict:
    if isinstance(content, bytes):
        return {"type": "binary", "content": content.hex()}
    text = str(content or "")
    if not text:
        return {"type": "none"}
    return {"type": "text", "content": Literal(text) if "\n" in text else text}


def token_body(text: str) -> str:
    data = json.loads(text)
    for key in ("access_token", "refresh_token", "id_token", "session_state"):
        if key in data:
            data[key] = "[FILTERED]"
    return json.dumps(data)


def interaction(item: dict, *, token: bool) -> dict:
    request, response = item["request"], item["response"]
    content = response["body"]["string"]
    if token:
        content = token_body(content)
    date = (response["headers"].get("Date") or [None])[0]
    recorded = parsedate_to_datetime(date).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    return {
        "request": {
            "method": request["method"],
            "uri": request["uri"],
            "headers": {
                "accept": [
                    "application/json" if token else "application/json, application/zip"
                ]
            },
            "body": (
                {"type": "text", "content": "grant_type=password&username=[FILTERED]&password=[FILTERED]"}
                if token
                else {"type": "none"}
            ),
        },
        "response": {
            "status": response["status"]["code"],
            "headers": headers(response["headers"]),
            "body": body(content),
        },
        "recorded_at": recorded,
    }


def name_for(uri: str) -> str:
    ip, _, endpoint, *rest = uri.removeprefix(API).split("/")
    number = unquote(rest[-1])
    if not number.isascii():
        number = "name"
    kind = f"{rest[0].replace('_', '-')}-" if len(rest) == 2 else ""
    return f"jpo-{ip}-{endpoint.replace('_', '-')}-{kind}{number}"


def main() -> int:
    written: dict[str, dict] = {}
    for path in sorted(SOURCE.glob("tests_jpo_test_live_py_*.yaml")):
        items = yaml.safe_load(path.read_text())["interactions"]
        token = None
        for item in items:
            uri = item["request"]["uri"]
            if uri.endswith("/auth/token"):
                token = item
                continue
            name = name_for(uri)
            if name in written or token is None:
                continue
            written[name] = {
                "version": 1,
                "interactions": [
                    interaction(token, token=True),
                    interaction(item, token=False),
                ],
            }
    for name, cassette in written.items():
        text = yaml.dump(cassette, allow_unicode=True, sort_keys=False, width=100)
        if SECRET.search(text):
            print(f"{name}: credential-shaped text found; not written", file=sys.stderr)
            return 1
        (TARGET / f"{name}.yaml").write_text(text)
    print(f"Wrote {len(written)} cassettes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
