# POA Client Signature (PTO/AIA/82B) — AcroForm Field Map

Form: Power of Attorney by Applicant
PDF type: **AcroForm** (28 widgets)
Template: `templates/aia0082b_client_poa.pdf` (single page, extracted from 82)
Library: `PyMuPDF` (fitz)

## Purpose

The client (applicant) signs this once to appoint attorneys. Revokes all previous POAs. Can be reused across multiple applications by pairing with a fresh 82A transmittal for each.

## Workflow

1. Pre-fill customer number and correspondence address
2. Send to client for signature
3. Reuse the signed PDF with each new 82A transmittal

## Complete Field Inventory

### Application Reference

| Field Name | Type | Description |
|-----------|------|-------------|
| `Application Number on 82B` | Text | Application number (can be left blank if general) |
| `Filing Date on 82B` | Text | Filing date |

### Attorney Appointment

| Field Name | Type | Description |
|-----------|------|-------------|
| `Appoint attorneys listed under customer number` | CheckBox | Appoint by customer number |
| `Appoint attorneys listed on the attached list` | CheckBox | Appoint by attached 82C list |
| `Customer Number` | Text | USPTO customer number |

### Correspondence Address

| Field Name | Type | Description |
|-----------|------|-------------|
| `The address with the above mentioned customer number` | CheckBox | Use customer number address |
| `The address associated with customer number` | CheckBox | Use associated address |
| `Customer Number2` | Text | Second customer number for correspondence |
| `Box for Firm or Individual Name` | CheckBox | Use manual address below |
| `Firm or Individual Name` | Text | Firm name |
| `Street Address` | Text | Street address |
| `City` | Text | City |
| `State_2` | Text | State |
| `Zip` | Text | ZIP code |
| `Country` | Text | Country |
| `Telephone Number` | Text | Phone |
| `Email Address` | Text | Email |

### Applicant Status

| Field Name | Type | Description |
|-----------|------|-------------|
| `Applicant Name (if applicant is a juristic entity)` | Text | Entity name |
| `Inventor or Joint inventor` | CheckBox | Applicant is inventor |
| `Legal Representative of a deceased or legally incapacitated inventor` | CheckBox | Legal representative |
| `Assignee` | CheckBox | Applicant is assignee |
| `Person who otherwise sufficient proprietary interest` | CheckBox | Proprietary interest |

### Client Signature

| Field Name | Type | Description |
|-----------|------|-------------|
| `Signature of the applicant for patent` | Text | Client signature (e.g., "/John Inventor/") |
| `Name of the Signer` | Text | Client printed name |
| `Title of the Signer` | Text | Client title (if entity) |
| `Date Optional_2` | Text | Signature date |

### Additional Forms

| Field Name | Type | Description |
|-----------|------|-------------|
| `Number of Forms` | Text | Number of additional 82B forms |
| `Total number of forms are submitted` | CheckBox | Check if additional forms |

## Fill Example — Pre-fill Before Client Signature

```python
import fitz

client_poa_data = {
    # Attorney appointment
    "Appoint attorneys listed under customer number": True,
    "Customer Number": "12345",
    # Correspondence
    "The address with the above mentioned customer number": True,
    # Applicant type
    "Assignee": True,
    "Applicant Name (if applicant is a juristic entity)": "Acme Corporation",
    # Client fills these by hand or via e-signature:
    # "Signature of the applicant for patent": "/Craig Schwartz/",
    # "Name of the Signer": "Craig Schwartz",
    # "Title of the Signer": "General Counsel",
    # "Date Optional_2": "03/11/2026",
}

doc = fitz.open("aia0082b_client_poa.pdf")
for page in doc:
    for widget in page.widgets():
        if widget.field_name in client_poa_data:
            widget.field_value = client_poa_data[widget.field_name]
            widget.update()
doc.save("82b_prefilled.pdf")
doc.close()
```
