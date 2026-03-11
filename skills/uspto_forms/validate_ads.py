"""Validate ADS field data against rules extracted from the XFA template.

Extracts nullTest (required), character constraints, and conditional
visibility rules from the PTO/AIA/14 XFA template, then checks a
field_map dict against those rules.

Usage:
    from validate_ads import validate_ads, extract_rules

    errors = validate_ads(field_map)
    for e in errors:
        print(f"[{e['level']}] {e['field']}: {e['message']}")
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pikepdf

TEMPLATE = Path(__file__).parent / "templates" / "aia0014_ads.pdf"


# ---------------------------------------------------------------------------
# Rule extraction from XFA template
# ---------------------------------------------------------------------------

@dataclass
class FieldRule:
    """Validation rule for a single XFA field."""
    path: str                     # dot-separated path from us-request
    required: bool = False        # nullTest="error"
    valid_chars: str | None = None  # allowed character set (None = any)
    script_test: str | None = None  # "warning" or "error"


def extract_rules(template_path: Path = TEMPLATE) -> list[FieldRule]:
    """Parse the XFA template and return validation rules for every field."""
    pdf = pikepdf.Pdf.open(str(template_path))
    xfa = pdf.Root.AcroForm.XFA
    template_xml = xfa[5].read_bytes().decode("utf-8")
    pdf.close()

    # Strip default namespace and processing instructions for ET parsing
    clean = re.sub(r'\s*xmlns="[^"]*"', '', template_xml, count=1)
    clean = re.sub(r'<\?[^?]*\?>', '', clean)
    root = ET.fromstring(clean)

    rules: list[FieldRule] = []

    def _walk(elem: ET.Element, path: str = "") -> None:
        tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        name = elem.get('name', '')
        current = f"{path}.{name}" if name and path else (name or path)

        if tag == 'field':
            rule = FieldRule(path=current)

            for child in elem.iter():
                child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                if child_tag == 'validate':
                    if child.get('nullTest') == 'error':
                        rule.required = True
                    if child.get('scriptTest'):
                        rule.script_test = child.get('scriptTest')
                if child_tag == 'script' and child.text:
                    # ValidChars strings may contain escaped quotes (\")
                    vc = re.search(r'var ValidChars = "((?:[^"\\]|\\.)*)"', child.text)
                    if vc:
                        rule.valid_chars = vc.group(1).replace('\\"', '"')

            if rule.required or rule.valid_chars:
                rules.append(rule)

        for child in elem:
            _walk(child, current)

    _walk(root)
    return rules


# ---------------------------------------------------------------------------
# Conditional groups — which required fields are mutually exclusive
# ---------------------------------------------------------------------------

# These encode the visibility toggle logic from the XFA JavaScript.
# Key = condition (field path suffix -> value), Value = list of field path
# suffixes that become active (visible) when that condition is met.
# Fields in inactive groups are not required.

CONDITIONAL_GROUPS: dict[str, list[dict[str, Any]]] = {
    # Residency: US vs non-US vs military
    "residency": [
        {
            "trigger": "sfAppResChk.resCheck.ResidencyRadio",
            "value": "us-residency",
            "active_fields": [
                "sfAppResChk.sfUSres.rsCityTxt",
                "sfAppResChk.sfUSres.rsStTxt",
                "sfAppResChk.sfUSres.rsCtryTxt",
            ],
        },
        {
            "trigger": "sfAppResChk.resCheck.ResidencyRadio",
            "value": "non-us-residency",
            "active_fields": [
                "sfAppResChk.sfNonUSRes.nonresCity",
                "sfAppResChk.sfNonUSRes.nonresCtryList",
            ],
        },
    ],
    # Correspondence: customer number vs manual address
    "correspondence": [
        {
            "trigger": "ContentArea2.sfCorrCustNo.customerNumber",
            "has_value": True,
            "active_fields": ["sfCorrCustNo.customerNumber"],
            "inactive_fields": [
                "sfCorrAddress.Name1",
                "sfCorrAddress.address1",
                "sfCorrAddress.city",
                "sfCorrAddress.corrCountry",
            ],
        },
        {
            "trigger": "ContentArea2.sfCorrAddress.Name1",
            "has_value": True,
            "active_fields": [
                "sfCorrAddress.Name1",
                "sfCorrAddress.address1",
                "sfCorrAddress.city",
                "sfCorrAddress.corrCountry",
            ],
            "inactive_fields": ["sfCorrCustNo.customerNumber"],
        },
    ],
    # Attorney: customer number vs named attorney vs CFR 1.19
    "attorney": [
        {
            "trigger": "sfAttorny.sfrepheader.attornyChoice",
            "value": "customer-number",
            "active_fields": [
                "sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt",
            ],
            "inactive_fields": [
                "sfAttorny.sfAttornyFlow.sfAttrynyName.first-name",
                "sfAttorny.sfAttornyFlow.sfAttrynyName.last-name",
                "sfAttorny.sfAttornyFlow.sfAttrynyName.attrnyRegNameTxt",
                "sfAttorny.sfAttornyFlow.sfrepcfr119.first-name",
                "sfAttorny.sfAttornyFlow.sfrepcfr119.last-name",
            ],
        },
        {
            "trigger": "sfAttorny.sfrepheader.attornyChoice",
            "value": "us-attorney-or-agent",
            "active_fields": [
                "sfAttorny.sfAttornyFlow.sfAttrynyName.first-name",
                "sfAttorny.sfAttornyFlow.sfAttrynyName.last-name",
                "sfAttorny.sfAttornyFlow.sfAttrynyName.attrnyRegNameTxt",
            ],
            "inactive_fields": [
                "sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt",
                "sfAttorny.sfAttornyFlow.sfrepcfr119.first-name",
                "sfAttorny.sfAttornyFlow.sfrepcfr119.last-name",
            ],
        },
    ],
    # Assignee: org vs individual
    "assignee": [
        {
            "trigger": "sfAssigneeInformation.sfAssigneorgChoice.chkOrg",
            "value": "1",
            "active_fields": [
                "sfAssigneeInformation.sfAssigneorgChoice.sforgName.orgName",
            ],
            "inactive_fields": [
                "sfAssigneeInformation.sfAssigneorgChoice.sfApplicantName.first-name",
                "sfAssigneeInformation.sfAssigneorgChoice.sfApplicantName.last-name",
            ],
        },
        {
            "trigger": "sfAssigneeInformation.sfAssigneorgChoice.chkOrg",
            "value": "0",
            "active_fields": [
                "sfAssigneeInformation.sfAssigneorgChoice.sfApplicantName.first-name",
                "sfAssigneeInformation.sfAssigneorgChoice.sfApplicantName.last-name",
            ],
            "inactive_fields": [
                "sfAssigneeInformation.sfAssigneorgChoice.sforgName.orgName",
            ],
        },
    ],
}

# Sections that are only required when populated (repeating optional subforms).
# If the user adds a domestic continuity entry, its fields become required.
# If not populated at all, the entire section is optional.
OPTIONAL_SECTIONS = [
    "sfDomesticContinuity",
    "sfForeignPriorityInfo",
    "sfAssigneeInformation",
    "sfNonApplicantInfo",
]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class ValidationError:
    level: str        # "error" or "warning"
    field: str        # field path
    message: str      # human-readable description
    rule: str         # rule type: "required", "chars", "format"


def _match_key(key: str, suffix: str) -> bool:
    """Check if a field_map key matches a path suffix.

    Handles the mismatch between template paths (deep nesting like
    ContentArea2.sfApplication.sfAppInfo.sfInvTitle.invention-title) and
    datasets paths (flat like invention-title or ContentArea1-relative).
    """
    if key == suffix:
        return True
    if key.endswith(f".{suffix}"):
        return True
    # Match by leaf name (last segment)
    leaf = suffix.rsplit(".", 1)[-1]
    key_leaf = key.rsplit(".", 1)[-1]
    if key_leaf == leaf:
        # Avoid false positives: only match leaves that are unique-ish
        # (e.g., "invention-title" but not generic "city" or "address1")
        return leaf not in _AMBIGUOUS_LEAVES
    return False


# Field names that appear in multiple sections — require full path match
_AMBIGUOUS_LEAVES = {
    "address1", "address-1", "address2", "city", "state", "postcode",
    "corrCountry", "mailCountry", "phone", "fax", "first-name", "last-name",
    "orgName", "Name1", "Name2", "prefix", "suffix",
}


def _field_has_value(field_map: dict[str, str], suffix: str) -> bool:
    """Check if any key in field_map has a non-empty value matching suffix."""
    for key in field_map:
        if _match_key(key, suffix):
            val = field_map[key]
            if val and str(val).strip():
                return True
    return False


def _get_field_value(field_map: dict[str, str], suffix: str) -> str | None:
    """Get value for a field matching a path suffix."""
    for key in field_map:
        if _match_key(key, suffix):
            return field_map[key]
    return None


def _section_is_populated(field_map: dict[str, str], section: str) -> bool:
    """Check if any field in an optional section has been filled."""
    for key, val in field_map.items():
        if section in key and val and str(val).strip():
            return True
    return False


def _is_inactive(field_path: str, field_map: dict[str, str]) -> bool:
    """Check if a required field is inactive due to conditional visibility.

    A field is inactive when another condition in the same group is active
    and this field is in that condition's inactive list.
    """
    field_suffix = field_path.split("us-request.")[-1] if "us-request." in field_path else field_path

    for group_name, conditions in CONDITIONAL_GROUPS.items():
        for condition in conditions:
            trigger = condition["trigger"]
            inactive = condition.get("inactive_fields", [])

            # Check if this field is in the inactive list
            matches_inactive = any(
                field_suffix.endswith(f) or f in field_suffix
                for f in inactive
            )
            if not matches_inactive:
                continue

            # Check if the trigger condition is met (making this field inactive)
            if "value" in condition:
                trigger_val = _get_field_value(field_map, trigger)
                if trigger_val == condition["value"]:
                    return True
            elif "has_value" in condition:
                if _field_has_value(field_map, trigger):
                    return True

        # Also: if this field belongs to a group but NO condition is active,
        # check if another condition in the group IS active (making this one inactive).
        # E.g., if residency=us-residency, non-US fields are inactive even though
        # no condition explicitly lists them as inactive for that trigger.
        for condition in conditions:
            active = condition.get("active_fields", [])
            matches_active = any(
                field_suffix.endswith(f) or f in field_suffix
                for f in active
            )
            if matches_active:
                # This field is in an active list — check if the trigger IS met
                trigger = condition["trigger"]
                if "value" in condition:
                    trigger_val = _get_field_value(field_map, trigger)
                    if trigger_val != condition["value"]:
                        # Trigger doesn't match, so this field's group is inactive
                        return True

    return False


def validate_ads(
    field_map: dict[str, str],
    template_path: Path = TEMPLATE,
    *,
    rules: list[FieldRule] | None = None,
) -> list[ValidationError]:
    """Validate an ADS field_map against XFA template rules.

    Args:
        field_map: Dict of dot-path keys to string values (same format
                   as fill_ads_xfa).
        template_path: Path to ADS PDF template.
        rules: Pre-extracted rules (avoids re-parsing template each call).

    Returns:
        List of ValidationError objects, sorted by severity then field.
    """
    if rules is None:
        rules = extract_rules(template_path)

    errors: list[ValidationError] = []

    for rule in rules:
        # Strip "us-request." prefix to match field_map keys
        short_path = rule.path
        if short_path.startswith("us-request."):
            short_path = short_path[len("us-request."):]

        # Also try matching by the path from ContentArea
        value = _get_field_value(field_map, short_path)

        # --- Required field check ---
        if rule.required:
            has_val = value is not None and str(value).strip() != ""

            if not has_val:
                # Skip if field is in an inactive conditional group
                if _is_inactive(rule.path, field_map):
                    continue

                # Skip if field belongs to an optional section that's not populated
                in_optional = any(s in rule.path for s in OPTIONAL_SECTIONS)
                if in_optional and not _section_is_populated(field_map, next(
                    s for s in OPTIONAL_SECTIONS if s in rule.path
                )):
                    continue

                errors.append(ValidationError(
                    level="error",
                    field=short_path,
                    message=f"Required field is empty",
                    rule="required",
                ))

        # --- Character validation ---
        if rule.valid_chars and value:
            invalid = [c for c in str(value) if c not in rule.valid_chars]
            if invalid:
                unique_invalid = sorted(set(invalid))
                errors.append(ValidationError(
                    level="error",
                    field=short_path,
                    message=f"Invalid characters: {unique_invalid!r}. "
                            f"Allowed: {_describe_charset(rule.valid_chars)}",
                    rule="chars",
                ))

    # Sort: errors first, then by field path
    errors.sort(key=lambda e: (0 if e.level == "error" else 1, e.field))
    return errors


def _describe_charset(chars: str) -> str:
    """Human-readable description of allowed character set."""
    parts = []
    has_upper = any(c.isupper() for c in chars)
    has_lower = any(c.islower() for c in chars)
    has_digit = any(c.isdigit() for c in chars)
    specials = [c for c in chars if not c.isalnum() and c != ' ']
    has_space = ' ' in chars

    if has_upper and has_lower:
        parts.append("letters")
    elif has_upper:
        parts.append("uppercase letters")
    elif has_lower:
        parts.append("lowercase letters")
    if has_digit:
        parts.append("digits")
    if has_space:
        parts.append("spaces")
    if specials:
        parts.append(f"special chars: {''.join(specials)}")
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Demo: validate an empty field map
    print("Extracting rules from ADS template...")
    rules = extract_rules()
    print(f"Found {len(rules)} rules ({sum(1 for r in rules if r.required)} required, "
          f"{sum(1 for r in rules if r.valid_chars)} char-validated)\n")

    # Validate a minimal filing
    sample = {
        "invention-title": "Test Invention",
        "ContentArea1.sfApplicantInformation.sfApplicantName.firstName": "John",
        "ContentArea1.sfApplicantInformation.sfApplicantName.lastName": "Inventor",
        "ContentArea1.sfApplicantInformation.sfAppResChk.resCheck.ResidencyRadio": "us-residency",
        "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCityTxt": "Austin",
        "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsStTxt": "TX",
        "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCtryTxt": "US",
        "ContentArea1.sfApplicantInformation.sfApplicantMail.address1": "123 Main St",
        "ContentArea1.sfApplicantInformation.sfApplicantMail.city": "Austin",
        "ContentArea2.sfCorrCustNo.customerNumber": "23640",
        "ContentArea2.sfAttorny.sfrepheader.attornyChoice": "customer-number",
        "ContentArea2.sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt": "23640",
        "ContentArea2.sfApplication.sfAppInfo.sfAppinfoFlow.sfAppPos.application_type": "REGULAR",
        "ContentArea2.sfApplication.sfAppInfo.sfAppinfoFlow.sfAppPos.us_submission_type": "UTL",
    }

    print("Validating sample data...")
    errors = validate_ads(sample, rules=rules)
    if errors:
        for e in errors:
            print(f"  [{e.level.upper()}] {e.field}: {e.message}")
    else:
        print("  No errors!")
