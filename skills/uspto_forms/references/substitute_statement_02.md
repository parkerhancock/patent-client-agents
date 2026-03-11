# Substitute Statement (PTO/AIA/02) — AcroForm Field Map

Form: Substitute Statement in Lieu of an Oath or Declaration for Utility or Design Patent Application
PDF type: **AcroForm** (38 widgets)
Template: `templates/aia0002_substitute_statement.pdf` (3 pages; page 3 is Privacy Act text with no widgets)
Library: `PyMuPDF` (fitz)

## Purpose

Filed when one or more inventors cannot or will not sign the oath/declaration under 37 CFR 1.63. Covers four circumstances: inventor deceased, legally incapacitated, unreachable after diligent effort, or refusal to sign. The person executing the statement must have standing (assignee, obligee, joint inventor, or legal representative) and must identify the circumstance and the inventor. Filed per-inventor — one form per missing oath.

## Complete Field Inventory

### Page 1 — Application & Inventor Identification

| Field Name | Type | Description |
|-----------|------|-------------|
| `Title of Invent ion` | Text | Title of the invention (note: embedded space in field name) |
| `The attached application` | CheckBox | Check if statement is for the attached (new) application |
| `United States application or PCT international application number` | CheckBox | Check if statement is for an existing application/PCT |
| `PCT Number` | Text | Application or PCT number (when existing-app box checked) |
| `Filed On` | Text | Filing date of the application (MM/DD/YYYY) |
| `Eg Given Name first and middle if any and Family Name or Surname` | Text | Legal name of the inventor to whom this statement applies |
| `City` | Text | Inventor residence — city |
| `State1` | Text | Inventor residence — state |
| `Country1` | Text | Inventor residence — country |
| `Mailing Address except for a deceased or legally incapacitated inventor` | Text | Inventor mailing address (street line) |
| `City_2` | Text | Inventor mailing address — city |
| `State2` | Text | Inventor mailing address — state |
| `Zip2` | Text | Inventor mailing address — zip |
| `Country2` | Text | Inventor mailing address — country |

### Page 1 — Relationship to Inventor

| Field Name | Type | Description |
|-----------|------|-------------|
| `Legal Representative for deceased or legally incapacitated inventor only` | CheckBox | Signer is legal representative |
| `Assignee` | CheckBox | Signer is assignee of the invention |
| `Person to whom the inventor is under an obligation to assign` | CheckBox | Signer is obligation-to-assign party |
| `Person who otherwise shows a sufficient proprietary interest in the matter petition under 37 CFR 146 is required or` | CheckBox | Signer has sufficient proprietary interest (petition required) |
| `Joint Inventor` | CheckBox | Signer is a joint inventor |

### Page 2 — Circumstances Permitting Execution

| Field Name | Type | Description |
|-----------|------|-------------|
| `Inventor is deceased` | CheckBox | Inventor is deceased |
| `Inventor is under legal incapacity` | CheckBox | Inventor is legally incapacitated |
| `Inventor cannot be found or reached after diligent effort or` | CheckBox | Inventor unreachable after diligent effort |
| `Inventor has refused to execute the oath or declaration under 37 CFR 163` | CheckBox | Inventor refused to sign |

### Page 2 — Joint Inventor ADS Status

| Field Name | Type | Description |
|-----------|------|-------------|
| `An application data sheet under 37 CFR 176 PTO14 or equivalent naming the entire inventive entity has been` | CheckBox | ADS naming all inventors has been or is being submitted |
| `An application data sheet under 37 CFR 176 PTO14 or equivalent has not been submitted Thus a Substitute` | CheckBox | ADS not submitted; supplemental sheet attached |

### Page 2 — Signer Information

| Field Name | Type | Description |
|-----------|------|-------------|
| `1DPH` | Text | Printed name of person executing the statement |
| `fill_3` | Text | Date of signature (MM/DD/YYYY) |
| `Signature` | Text | Signature (e.g., "/Parker Hancock/") |
| `Applicant Name` | Text | Name of applicant (may differ from signer) |
| `Title of Person Executing This Substitute Statement` | Text | Signer's title or role |

### Page 2 — Signer Residence & Mailing Address

| Field Name | Type | Description |
|-----------|------|-------------|
| `City3` | Text | Signer residence — city |
| `State3` | Text | Signer residence — state |
| `City State Country` | Text | Signer residence — country |
| `Mailing Address2` | Text | Signer mailing address (street line) |
| `City_3` | Text | Signer mailing address — city |
| `State` | Text | Signer mailing address — state |
| `Zip3` | Text | Signer mailing address — zip |
| `Country3` | Text | Signer mailing address — country |

## Fill Example

```python
import fitz

def fill_substitute_statement(template_path: str, output_path: str, data: dict) -> int:
    doc = fitz.open(template_path)
    filled = 0
    for page in doc:
        for widget in page.widgets():
            if widget.field_name in data:
                val = data[widget.field_name]
                if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                    widget.field_value = widget.on_state() if val else "Off"
                else:
                    widget.field_value = str(val)
                widget.update()
                filled += 1
    doc.save(output_path)
    doc.close()
    return filled

statement_data = {
    # Application identification
    "Title of Invent ion": "Method and System for Widget Processing",
    "United States application or PCT international application number": True,
    "PCT Number": "18/123,456",
    "Filed On": "01/15/2026",

    # Inventor who cannot sign
    "Eg Given Name first and middle if any and Family Name or Surname": "John Q. Inventor",
    "City": "Austin",
    "State1": "TX",
    "Country1": "US",
    "Mailing Address except for a deceased or legally incapacitated inventor": "123 Main St",
    "City_2": "Austin",
    "State2": "TX",
    "Zip2": "78701",
    "Country2": "US",

    # Relationship — signer is assignee
    "Assignee": True,

    # Circumstance — inventor refused to sign
    "Inventor has refused to execute the oath or declaration under 37 CFR 163": True,

    # Joint inventor ADS status
    "An application data sheet under 37 CFR 176 PTO14 or equivalent naming the entire inventive entity has been": True,

    # Signer information
    "1DPH": "Parker Hancock",
    "fill_3": "03/11/2026",
    "Signature": "/Parker Hancock/",
    "Applicant Name": "Acme Corp.",
    "Title of Person Executing This Substitute Statement": "Patent Counsel",

    # Signer address
    "City3": "Dallas",
    "State3": "TX",
    "City State Country": "US",
    "Mailing Address2": "456 Commerce St, Suite 200",
    "City_3": "Dallas",
    "State": "TX",
    "Zip3": "75201",
    "Country3": "US",
}

fill_substitute_statement(
    "aia0002_substitute_statement.pdf",
    "substitute_statement_filled.pdf",
    statement_data,
)
```
