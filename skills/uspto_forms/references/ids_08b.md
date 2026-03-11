# IDS Continuation (PTO/SB/08b) — AcroForm Field Map

Form: Information Disclosure Statement by Applicant — Non Patent Literature Continuation
PDF type: **AcroForm** (38 widgets)
Template: `templates/sb0008b_ids_cont.pdf` (2 pages; all fields on page 1, page 2 is Privacy Act)
Library: `PyMuPDF` (fitz)

## Purpose

Continuation sheet for an IDS when additional NPL (Non Patent Literature) citations do not fit on the main SB/08a form. Each sheet provides 10 citation rows. File as many continuation sheets as needed, numbering them with the Sheet/Of fields.

## Complete Field Inventory

### Application Identification (Header)

| Field Name | Type | Description |
|-----------|------|-------------|
| `text3` | Text | Application number (e.g., "18/123,456") |
| `text4` | Text | Filing date (MM/DD/YYYY) |
| `text5` | Text | First named inventor |
| `text 6` | Text | Art unit (note: space in field name) |
| `text7` | Text | Examiner name |
| `text8` | Text | Attorney docket number |

### Sheet Numbering

| Field Name | Type | Description |
|-----------|------|-------------|
| `text1` | Text | Current sheet number |
| `text2` | Text | Total number of sheets |

### NPL Citation Rows (10 rows)

Each row has three fields: a cite number, the citation text, and a checkbox indicating whether an English translation is attached.

| Row | Cite No (Field) | Citation Text (Field) | Translation (Field) | Translation Type |
|-----|----------------|----------------------|---------------------|-----------------|
| 1 | `text9` | `text10` | `text11` | CheckBox |
| 2 | `text12` | `text13` | `text14` | CheckBox |
| 3 | `text15` | `text16` | `text17` | CheckBox |
| 4 | `text18` | `text19` | `text20` | CheckBox |
| 5 | `text21` | `text22` | `text23` | CheckBox |
| 6 | `text24` | `text25` | `text26` | CheckBox |
| 7 | `text27` | `text28` | `text29` | CheckBox |
| 8 | `text30` | `text31` | `text32` | CheckBox |
| 9 | `text33` | `text34` | `text35` | CheckBox |
| 10 | `text36` | `text37` | `text38` | CheckBox |

### Field Name Pattern

For row `n` (1-indexed), the field names follow:
- Cite No: `text{9 + (n-1)*3}` (text types)
- Citation: `text{10 + (n-1)*3}` (text types)
- Translation: `text{11 + (n-1)*3}` (checkbox types, field_type=2)

Note: `text 6` has a space in the name — use the exact string `"text 6"` when filling.

## Fill Example

```python
import fitz

def fill_08b(template_path: str, output_path: str, data: dict) -> int:
    doc = fitz.open(template_path)
    filled = 0
    for page in doc:
        for widget in page.widgets():
            if widget.field_name in data:
                widget.field_value = data[widget.field_name]
                widget.update()
                filled += 1
    doc.save(output_path)
    doc.close()
    return filled

# Header data shared across all continuation sheets
header = {
    "text3": "18/123,456",
    "text4": "03/11/2026",
    "text5": "John Q. Inventor",
    "text 6": "2100",
    "text7": "Smith, Jane",
    "text8": "ACME-001",
    "text1": "3",   # Sheet 3
    "text2": "4",   # of 4
}

# NPL citations — 10 rows max per sheet
npl_rows = [
    ("NL1", "SMITH, John, \"Machine Learning for Patent Analysis,\" "
            "Journal of IP Law, vol. 42, pp. 100-115, Jan. 2025.", False),
    ("NL2", "TANAKA, Kenji, \"Automated Claim Construction,\" "
            "Proceedings of AIPPI, pp. 50-62, Mar. 2024.", True),
]

citation_data = {}
for i, (cite_no, citation, has_translation) in enumerate(npl_rows):
    base = 9 + i * 3
    citation_data[f"text{base}"] = cite_no
    citation_data[f"text{base + 1}"] = citation
    if has_translation:
        citation_data[f"text{base + 2}"] = True

fill_08b(
    "sb0008b_ids_cont.pdf",
    "ids_continuation_filled.pdf",
    {**header, **citation_data},
)
```
