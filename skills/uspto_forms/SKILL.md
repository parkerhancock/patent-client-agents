---
name: uspto-forms
description: |
  Fill USPTO patent filing forms from structured data.
  Supports ADS, POA, Declaration, Substitute Statement, and IDS forms.
  Use when populating PTO/AIA/14, PTO/AIA/82, PTO/AIA/01, PTO/AIA/02,
  or PTO/SB/08a/08b forms programmatically with Python.
---

# USPTO Form Filling

Fill USPTO patent filing PDFs from structured Python data. Two PDF architectures: XFA (ADS only) and AcroForm (everything else).

> **No provisional cover sheet (SB/16).** Per 37 CFR 1.51(c)(1), the ADS satisfies the cover sheet requirement for provisional applications. We always file an ADS.

## Form Inventory

| Form | Number | PDF Type | Library | Reference |
|------|--------|----------|---------|-----------|
| Application Data Sheet | PTO/AIA/14 | **XFA-only** | pikepdf + xml.etree | [ads.md](references/ads.md) |
| POA Transmittal | PTO/AIA/82A | **AcroForm** | PyMuPDF (fitz) | [poa_82a.md](references/poa_82a.md) |
| POA Client Signature | PTO/AIA/82B | **AcroForm** | PyMuPDF (fitz) | [poa_82b.md](references/poa_82b.md) |
| POA Practitioner List | PTO/AIA/82C | **AcroForm** | PyMuPDF (fitz) | [poa_82c.md](references/poa_82c.md) |
| Declaration | PTO/AIA/01 | **AcroForm** | PyMuPDF (fitz) | [declaration_01.md](references/declaration_01.md) |
| Substitute Statement | PTO/AIA/02 | **AcroForm** | PyMuPDF (fitz) | [substitute_statement_02.md](references/substitute_statement_02.md) |
| IDS (US + Foreign) | PTO/SB/08a | **AcroForm** | PyMuPDF (fitz) | [ids_08a.md](references/ids_08a.md) |
| IDS Continuation (NPL) | PTO/SB/08b | **AcroForm** | PyMuPDF (fitz) | [ids_08b.md](references/ids_08b.md) |

### POA Workflow

The POA is split into three independent single-page PDFs for flexible filing:

1. **82B** — Get the client to sign once. Contains customer number appointment, correspondence address, and applicant signature. Reuse across applications.
2. **82A** — Attorney fills per application. Contains app number, title, inventor, and attorney signature.
3. **82C** — Only needed if listing practitioners by name instead of customer number.

To file: combine a filled 82A + the signed 82B (+ optionally 82C) per application.

```python
import fitz

def merge_poa(transmittal_path: str, client_poa_path: str, output_path: str,
              practitioner_list_path: str | None = None) -> None:
    """Merge filled POA pages into a single filing PDF."""
    doc = fitz.open(transmittal_path)
    doc.insert_pdf(fitz.open(client_poa_path))
    if practitioner_list_path:
        doc.insert_pdf(fitz.open(practitioner_list_path))
    doc.save(output_path)
    doc.close()
```

## Quick Decision

```
Is the form XFA? (check: pdf.Root.AcroForm.XFA exists and widgets() returns 0 fields)
├─ YES (ADS) → pikepdf: parse XFA datasets XML, set element text, write stream back
└─ NO (POA 82A/B/C) → PyMuPDF: iterate widgets, set field_value, call update()
```

## Dependencies

```python
# Both are needed
import fitz          # PyMuPDF — AcroForm widget filling
import pikepdf       # XFA datasets XML manipulation
import xml.etree.ElementTree as ET  # stdlib — parse XFA XML
```

## AcroForm Pattern (POA, Declaration, Substitute Statement, IDS)

```python
import fitz

def fill_acroform(template_path: str, output_path: str, data: dict[str, str]) -> int:
    """Fill an AcroForm PDF. Returns count of fields filled."""
    doc = fitz.open(template_path)
    filled = 0
    for page in doc:
        for widget in page.widgets():
            if widget.field_name in data:
                widget.field_value = data[widget.field_name]
                widget.update()  # CRITICAL — generates appearance stream
                filled += 1
    doc.save(output_path)
    doc.close()
    return filled
```

### Checkboxes

Checkboxes accept `True` (becomes `"Yes"`) or `"Off"` to uncheck. PyMuPDF handles the conversion.

```python
widget.field_value = True   # checks the box
widget.update()
```

### Verification

Always verify by re-reading the saved PDF:

```python
doc = fitz.open(output_path)
for page in doc:
    for widget in page.widgets():
        if widget.field_value:
            print(f"{widget.field_name} = {widget.field_value}")
```

## XFA Pattern (ADS)

The ADS form is pure XFA — PyMuPDF sees 0 widgets. Data lives in an XML stream inside the PDF.

```python
import pikepdf
import xml.etree.ElementTree as ET

def fill_ads(template_path: str, output_path: str, data: dict) -> None:
    """Fill the XFA-based ADS form."""
    pdf = pikepdf.Pdf.open(template_path)
    xfa = pdf.Root.AcroForm.XFA

    # XFA array: [name, stream, name, stream, ...]
    # datasets is at index 7 (name "datasets" at index 6)
    datasets_xml = xfa[7].read_bytes().decode("utf-8")
    ns = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}
    root = ET.fromstring(datasets_xml)
    xfa_data = root.find(".//xfa:data", ns)

    # Navigate and set fields using the XML path structure
    # (see references/ads.md for full field map)
    _populate_ads_fields(xfa_data, data)

    # Write modified XML back as a stream
    modified_xml = ET.tostring(root, encoding="unicode")
    xfa[7] = pikepdf.Stream(pdf, modified_xml.encode("utf-8"))
    pdf.save(output_path)
    pdf.close()
```

### XFA Field Access Helper

```python
def set_xfa_field(parent: ET.Element, path: str, value: str) -> bool:
    """Set a field in XFA XML by dot-separated path.

    Example: set_xfa_field(data, "us-request.ContentArea1.sfApplicantInformation.sfApplicantName.firstName", "John")
    """
    parts = path.split(".")
    current = parent
    for part in parts[:-1]:
        current = current.find(part)
        if current is None:
            return False
    target = current.find(parts[-1])
    if target is None:
        target = ET.SubElement(current, parts[-1])
    target.text = value
    return True
```

### XFA Verification

```python
pdf = pikepdf.Pdf.open(output_path)
xml_bytes = pdf.Root.AcroForm.XFA[7].read_bytes()
root = ET.fromstring(xml_bytes.decode("utf-8"))
ns = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}
data = root.find(".//xfa:data", ns)
# Check specific field
assert data.find(".//firstName").text == "John"
```

## ADS Validation

The ADS XFA template embeds 42 required-field rules, 29 character-set constraints, and conditional visibility logic. The `validate_ads` module extracts these from the template at runtime and validates a field_map before filling.

```python
import sys
sys.path.insert(0, "path/to/skills/uspto_forms")
from validate_ads import validate_ads, extract_rules

# Extract rules once, reuse across calls
rules = extract_rules()

# Validate before filling
errors = validate_ads(field_map, rules=rules)
for e in errors:
    print(f"[{e.level.upper()}] {e.field}: {e.message}")

if not errors:
    fill_ads(template_path, output_path, field_map)
```

### What it checks

1. **Required fields** (`nullTest="error"`) — inventor name, residency, mailing address, title, application type, correspondence, attorney
2. **Character constraints** — customer numbers (digits only), country codes (alpha only), postcodes (alphanumeric + hyphen), etc.
3. **Conditional rules** — US vs non-US residency, customer number vs manual address, customer number vs named attorney, org vs individual assignee
4. **Optional sections** — continuity, foreign priority, assignee, and non-applicant sections are only validated when populated

## Important Notes

1. **Always call `widget.update()`** after setting AcroForm values. Without it, the value is stored in the PDF dictionary but not rendered visually.

2. **XFA datasets index is 7** for the ADS form specifically. The XFA array is `[name, stream, name, stream, ...]` and "datasets" is the 4th pair (index 6=name, 7=stream).

3. **Do not flatten XFA forms.** Flattening (removing AcroForm) has no effect on XFA-only forms and can corrupt them.

4. **Patent Center accepts modified PDFs** as long as the structure is valid. No form authenticity check.

5. **Test in Adobe Reader.** XFA rendering only works in Adobe Acrobat/Reader. Other PDF viewers may show a blank form or a "please use Adobe Reader" message.

6. **Checkbox values for AcroForm:** Use `True`/`False` (Python bool) or `"Yes"`/`"Off"` (strings). Check `widget.field_value` after setting to confirm.

## Splitting PDFs by Page

Use `doc.select([page_indices])` to extract pages while preserving form widgets. Do NOT use `insert_pdf` — it drops AcroForm fields.

```python
import fitz

def extract_page(source_path: str, page_index: int, output_path: str) -> None:
    """Extract a single page from a PDF, preserving form fields."""
    doc = fitz.open(source_path)
    doc.select([page_index])
    doc.save(output_path)
    doc.close()
```

## Refreshing Templates

Templates are downloaded from USPTO.gov. Run `refresh_forms.py` to check for updates:

```bash
python refresh_forms.py          # Download any changed forms
python refresh_forms.py --check  # Dry run — show what's stale
python refresh_forms.py --force  # Re-download everything
```

The script compares `Last-Modified` headers against a local `.manifest.json`, downloads changed forms, auto-splits the POA into 82A/82B/82C, and verifies field counts. If a field count changes, it warns that reference docs may need updating.

## Filing Checklists

- [Provisional Filing Checklist](references/provisional-filing-checklist.md) — 53-item checklist covering ADS, specification, drawings, PDF requirements, fees, and post-filing steps (updated 2026-03-11)

## Form Field References

Each reference doc contains the complete field inventory with exact field names and XML paths:

- [ADS Field Map (XFA)](references/ads.md) — 178 XFA fields, nested XML structure
- [POA 82A Transmittal](references/poa_82a.md) — 15 fields, attorney fills per application
- [POA 82B Client Signature](references/poa_82b.md) — 28 fields, client signs once
- [POA 82C Practitioner List](references/poa_82c.md) — 20 fields, 10 name/reg rows
- [Declaration (AIA/01)](references/declaration_01.md) — 8 fields, inventor oath per 37 CFR 1.63
- [Substitute Statement (AIA/02)](references/substitute_statement_02.md) — 38 fields, when inventor can't sign
- [IDS Main (SB/08a)](references/ids_08a.md) — 139 fields, US + foreign patent citations
- [IDS Continuation (SB/08b)](references/ids_08b.md) — 38 fields, NPL citations
