# POA Transmittal (PTO/AIA/82A) — AcroForm Field Map

Form: Transmittal for Power of Attorney to One or More Registered Practitioners
PDF type: **AcroForm** (15 widgets)
Template: `templates/aia0082a_transmittal.pdf` (single page, extracted from 82)
Library: `PyMuPDF` (fitz)

## Purpose

Attorney fills this per application. Identifies the application and includes the attorney's signature transmitting the POA. Filed together with a signed 82B.

## Complete Field Inventory

### Application Identification

| Field Name | Type | Description |
|-----------|------|-------------|
| `Application Number` | Text | Application number (e.g., "18/123,456") |
| `Filing Date` | Text | Filing date (MM/DD/YYYY) |
| `First Named Inventor` | Text | First named inventor |
| `Title` | Text | Invention title |
| `Art Unit` | Text | Art unit number |
| `Examiner Name` | Text | Examiner name |
| `Attorney Docket Number` | Text | Docket number |

### Attorney/Agent Signature

| Field Name | Type | Description |
|-----------|------|-------------|
| `Signature` | Text | Attorney signature (e.g., "/Parker Hancock/") |
| `Date Optional` | Text | Signature date (MM/DD/YYYY) |
| `Name` | Text | Attorney printed name |
| `Registration Number` | Text | USPTO registration number |

### Juristic Entity (if applicant is not an individual)

| Field Name | Type | Description |
|-----------|------|-------------|
| `Title if Applicant is a juristic entity` | Text | Signer's title at entity |
| `Applicant Name if Applicant is a juristic entity` | Text | Entity name |

### 82B Form Count

| Field Name | Type | Description |
|-----------|------|-------------|
| `Number of forms` | Text | Number of 82B forms attached |
| `Number of forms being submitted` | CheckBox | Check if submitting 82B forms |

## Fill Example

```python
import fitz

def fill_82a(template_path: str, output_path: str, data: dict) -> int:
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

transmittal_data = {
    "Application Number": "18/123,456",
    "Filing Date": "03/11/2026",
    "First Named Inventor": "John Q. Inventor",
    "Title": "Method and System for Widget Processing",
    "Art Unit": "2100",
    "Attorney Docket Number": "ACME-001",
    "Signature": "/Parker Hancock/",
    "Date Optional": "03/11/2026",
    "Name": "Parker Hancock",
    "Registration Number": "99999",
    "Number of forms being submitted": True,
    "Number of forms": "1",
}

fill_82a("aia0082a_transmittal.pdf", "82a_filled.pdf", transmittal_data)
```
