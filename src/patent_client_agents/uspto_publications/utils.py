from __future__ import annotations

import re
from itertools import zip_longest

import lxml.html as lh

__all__ = ["html_to_text", "ClaimsParser", "normalize_publication_number"]

_NEWLINE_RE = re.compile(r"<br\s*/?>\s*", flags=re.IGNORECASE)


def html_to_text(html: str | None) -> str | None:
    if not html:
        return None
    text = _NEWLINE_RE.sub("\n\n", html)
    return "".join(lh.fromstring(text).itertext())


SPLIT_RE = re.compile(
    r"^\s*([\d\-\.]+[\)\.]|\.Iadd\.[\d\-\.]+\.|\.\[[\d\-\.]+\.)",
    flags=re.MULTILINE,
)
NUMERIC_RE = re.compile(r"\d")
LIMITATION_RE = re.compile(r"(\s*[:;]\s*and|\s*[:;]\s*)", flags=re.IGNORECASE)
NUMBER_RE = re.compile(r"(?P<number>\d+)[\)\.]\s+")
WHITESPACE_RE = re.compile(r"\s+")
CLAIM_INTRO_RE = re.compile(r"^[^\d\.\[]+")
DEPENDENCY_RE = re.compile(r"claims? (?P<number>[\d,or ]+)", flags=re.IGNORECASE)
DEPENDENT_CLAIMS_RE = re.compile(r"(?P<number>\d+)([^\d]|$)")
DEPEND_ALL_RE = re.compile(
    r"(any of the foregoing claims|any of the previous claims)",
    flags=re.IGNORECASE,
)


def _clean_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def _grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


class ClaimsParser:
    """Minimal claim parser adapted from patent-client."""

    def parse(self, claim_text: str | None) -> list[dict]:
        if not claim_text:
            return []
        claim_strings = self._split_and_clean_claims(claim_text)
        claim_data = [self._parse_claim_string(string) for string in claim_strings]
        claim_dictionary = {c["number"]: c for c in claim_data}
        for claim in claim_data:
            for dependency in claim["depends_on"]:
                parent = claim_dictionary.get(dependency)
                if parent is not None:
                    parent["dependent_claims"].append(claim["number"])
        return claim_data

    def _split_and_clean_claims(self, claim_text: str) -> list[str]:
        cleaned = CLAIM_INTRO_RE.sub("", claim_text)
        claim_strs = [claim.strip() for claim in SPLIT_RE.split(cleaned)]
        while claim_strs and not NUMERIC_RE.search(claim_strs[0]):
            claim_strs.pop(0)
        grouped = list(_grouper(claim_strs, 2))
        claims: list[str] = []
        for claim_number, claim_body in grouped:
            if claim_number is None:
                continue
            if "-" in claim_number:
                claim_number = claim_number.replace(".", "")
                start, end, *_ = re.split(r"[^\d]+", claim_number)
                for num in range(int(start), int(end) + 1):
                    claims.append(f"{num}. {claim_body}")
            else:
                claims.append(" ".join(part for part in (claim_number, claim_body) if part))
        return claims

    def _parse_claim_string(self, text: str) -> dict:
        match = NUMBER_RE.search(text)
        if match is None:
            return {
                "number": 0,
                "limitations": [_clean_text(text)],
                "depends_on": [],
                "dependent_claims": [],
            }
        number = int(match.group("number"))
        remainder = NUMBER_RE.sub("", text, count=1)
        limitations = [
            _clean_text("".join(chunk)) for chunk in _grouper(LIMITATION_RE.split(remainder), 2, "")
        ]
        return {
            "number": number,
            "limitations": [lim for lim in limitations if lim],
            "depends_on": self._parse_dependency(remainder, number),
            "dependent_claims": [],
        }

    def _parse_dependency(self, text: str, number: int) -> list[int]:
        dependency = DEPENDENCY_RE.search(text)
        if dependency is not None:
            claims = dependency.groupdict()["number"]
            return [
                int(match.groupdict()["number"]) for match in DEPENDENT_CLAIMS_RE.finditer(claims)
            ]
        if DEPEND_ALL_RE.search(text):
            return list(range(1, number))
        return []


PUB_NUMBER_CLEAN_RE = re.compile(r"[^A-Z0-9]")


_KIND_CODE_RE = re.compile(r"[A-Z]\d$")


def normalize_publication_number(value: str | None) -> str:
    """Normalize a publication number for PPUBS PN searches.

    Strips country prefix, kind codes, and non-alphanumeric characters.
    PPUBS does not index kind codes in the .pn. field, so including them
    causes zero results.
    """
    if not value:
        return ""
    cleaned = PUB_NUMBER_CLEAN_RE.sub("", value.upper())
    if cleaned.startswith("US"):
        cleaned = cleaned[2:]
    cleaned = _KIND_CODE_RE.sub("", cleaned)
    return cleaned
