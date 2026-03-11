# Declaration (PTO/AIA/01) — AcroForm Field Map

Form: Declaration (37 CFR 1.63) for Utility or Design Application Using an Application Data Sheet (37 CFR 1.76)
PDF type: **AcroForm** (8 widgets across 2 pages; page 2 has no widgets)
Template: `templates/aia0001_declaration.pdf`
Library: `PyMuPDF` (fitz)

## Purpose

Inventor declaration under 37 CFR 1.63. Each inventor signs to declare they believe they are the original or an original joint inventor of the claimed invention. Filed with an Application Data Sheet (ADS, 37 CFR 1.76) which carries the inventor's detailed residence/mailing information. One declaration per inventor.

## Complete Field Inventory

### Invention Identification

| Field Name | Type | Description |
|-----------|------|-------------|
| `Title of Invention` | Text | Title of the invention (large field spanning most of page width) |

### Application Reference (check one)

| Field Name | Type | Description |
|-----------|------|-------------|
| `This declaration` | CheckBox | Check if directed to the attached application |
| `undefined` | CheckBox | Check if directed to a previously filed application (mutually exclusive with above) |
| `United States application or PCT international application number` | Text | Application or PCT number for a previously filed application |
| `filed on` | Text | Filing date of the previously filed application (MM/DD/YYYY) |

### Inventor Signature

| Field Name | Type | Description |
|-----------|------|-------------|
| `Inventor` | Text | Inventor's legal name |
| `Date Optional` | Text | Date of signature (MM/DD/YYYY) |
| `Text4` | Text | Residence / mailing address or additional inventor information |

## Fill Example

```python
import fitz

def fill_declaration(template_path: str, output_path: str, data: dict) -> int:
    doc = fitz.open(template_path)
    filled = 0
    for page in doc:
        for widget in page.widgets():
            if widget.field_name in data:
                val = data[widget.field_name]
                if widget.field_type == 2:  # CheckBox
                    widget.field_value = "Yes" if val else "Off"
                else:
                    widget.field_value = str(val)
                widget.update()
                filled += 1
    doc.save(output_path)
    doc.close()
    return filled

# Example: declaration for attached application
declaration_data = {
    "Title of Invention": "Method and System for Widget Processing",
    "This declaration": True,          # directed to the attached application
    "Inventor": "John Q. Inventor",
    "Date Optional": "03/11/2026",
    "Text4": "123 Main St, Austin, TX 78701",
}

fill_declaration("aia0001_declaration.pdf", "declaration_filled.pdf", declaration_data)

# Example: declaration for previously filed application
declaration_data_prior = {
    "Title of Invention": "Method and System for Widget Processing",
    "undefined": True,                 # directed to a previously filed application
    "United States application or PCT international application number": "18/123,456",
    "filed on": "01/15/2025",
    "Inventor": "John Q. Inventor",
    "Date Optional": "03/11/2026",
    "Text4": "123 Main St, Austin, TX 78701",
}

fill_declaration("aia0001_declaration.pdf", "declaration_prior.pdf", declaration_data_prior)
```
