# POA Practitioner List (PTO/AIA/82C) — AcroForm Field Map

Form: Power of Attorney by Applicant — Practitioner List
PDF type: **AcroForm** (20 widgets)
Template: `templates/aia0082c_practitioner_list.pdf` (single page, extracted from 82)
Library: `PyMuPDF` (fitz)

## Purpose

Lists up to 10 patent practitioners by name and registration number. Only needed when appointing attorneys by name rather than by customer number. If using a customer number on the 82B, this page is not required.

## Complete Field Inventory

10 rows of name + registration number pairs:

| Field Name | Type | Description |
|-----------|------|-------------|
| `NameRow1` | Text | Practitioner 1 name |
| `Registration NumberRow1` | Text | Practitioner 1 reg number |
| `NameRow2` | Text | Practitioner 2 name |
| `Registration NumberRow2` | Text | Practitioner 2 reg number |
| `NameRow3` | Text | Practitioner 3 name |
| `Registration NumberRow3` | Text | Practitioner 3 reg number |
| `NameRow4` | Text | Practitioner 4 name |
| `Registration NumberRow4` | Text | Practitioner 4 reg number |
| `NameRow5` | Text | Practitioner 5 name |
| `Registration NumberRow5` | Text | Practitioner 5 reg number |
| `NameRow6` | Text | Practitioner 6 name |
| `Registration NumberRow6` | Text | Practitioner 6 reg number |
| `NameRow7` | Text | Practitioner 7 name |
| `Registration NumberRow7` | Text | Practitioner 7 reg number |
| `NameRow8` | Text | Practitioner 8 name |
| `Registration NumberRow8` | Text | Practitioner 8 reg number |
| `NameRow9` | Text | Practitioner 9 name |
| `Registration NumberRow9` | Text | Practitioner 9 reg number |
| `NameRow10` | Text | Practitioner 10 name |
| `Registration NumberRow10` | Text | Practitioner 10 reg number |

## Fill Example

```python
import fitz

practitioners = [
    ("Parker Hancock", "99999"),
    ("Alice Attorney", "11111"),
    ("Bob Barrister", "22222"),
]

data = {}
for i, (name, reg) in enumerate(practitioners, 1):
    data[f"NameRow{i}"] = name
    data[f"Registration NumberRow{i}"] = reg

doc = fitz.open("aia0082c_practitioner_list.pdf")
for page in doc:
    for widget in page.widgets():
        if widget.field_name in data:
            widget.field_value = data[widget.field_name]
            widget.update()
doc.save("82c_filled.pdf")
doc.close()
```
