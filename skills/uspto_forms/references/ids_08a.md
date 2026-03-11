# IDS Main Form (PTO/SB/08a) — AcroForm Field Map

Form: Information Disclosure Statement by Applicant — U.S. Patents and Foreign Patent Documents
PDF type: **AcroForm** (139 widgets)
Template: `templates/sb0008a_ids.pdf` (2 pages; all fields on page 1, page 2 is Privacy Act)
Library: `PyMuPDF` (fitz)

## Purpose

Primary IDS form listing U.S. patent document citations and foreign patent document citations. Each sheet provides 19 rows for U.S. patents and 6 rows for foreign patents. Use SB/08b continuation sheets for Non Patent Literature (NPL) citations. File as many sheets as needed, numbering them with the Sheet/Of fields.

## Complete Field Inventory

### Application Identification (Header)

| Field Name | Type | Description |
|-----------|------|-------------|
| `text3` | Text | Application number (e.g., "18/123,456") |
| `text4` | Text | Filing date (MM/DD/YYYY) |
| `text5` | Text | First named inventor |
| `text6` | Text | Art unit |
| `text7` | Text | Examiner name |
| `text8` | Text | Attorney docket number |

### Sheet Numbering

| Field Name | Type | Description |
|-----------|------|-------------|
| `Text1` | Text | Current sheet number (note: capital T) |
| `text2` | Text | Total number of sheets |

### U.S. Patent Document Rows (19 rows)

Each row has 5 fields: cite number, document number (with "US-" prefix printed on form), publication date, name of patentee, and relevant pages/columns/lines.

| Row | Cite No | Document Number | Publication Date | Name of Patentee | Pages/Columns/Lines |
|-----|---------|----------------|-----------------|------------------|---------------------|
| 1 | `text9` | `text10` | `text11` | `text12` | `text13` |
| 2 | `text14` | `text15` | `text16` | `text17` | `text18` |
| 3 | `text19` | `text20` | `text21` | `text22` | `text23` |
| 4 | `text24` | `text25` | `text26` | `text27` | `text28` |
| 5 | `text29` | `text30` | `text31` | `text32` | `text33` |
| 6 | `text34` | `text35` | `text36` | `text37` | `text38` |
| 7 | `text39` | `text40` | `text41` | `text42` | `text43` |
| 8 | `text44` | `text45` | `text46` | `text47` | `text48` |
| 9 | `text49` | `text50` | `text51` | `text52` | `text53` |
| 10 | `text54` | `text55` | `text56` | `text57` | `text58` |
| 11 | `text59` | `text60` | `text61` | `text62` | `text63` |
| 12 | `text64` | `text65` | `text66` | `text67` | `text68` |
| 13 | `text69` | `text70` | `text71` | `text72` | `text73` |
| 14 | `text74` | `text75` | `text76` | `text77` | `text78` |
| 15 | `text79` | `text80` | `text81` | `text82` | `text83` |
| 16 | `text84` | `text85` | `text86` | `text87` | `text88` |
| 17 | `text89` | `text90` | `text91` | `text92` | `text93` |
| 18 | `text94` | `text95` | `text96` | `text97` | `text98` |
| 19 | `text99` | `text100` | `text101` | `text102` | `text103` |

#### U.S. Patent Field Name Pattern

For row `n` (1-indexed), the field names follow:
- Cite No: `text{9 + (n-1)*5}`
- Document Number: `text{10 + (n-1)*5}`
- Publication Date (MM-DD-YYYY): `text{11 + (n-1)*5}`
- Name of Patentee: `text{12 + (n-1)*5}`
- Pages/Columns/Lines: `text{13 + (n-1)*5}`

Note: The form prints "US-" before each document number field. Enter only the number and kind code (e.g., "10,234,567 B2"), not the "US-" prefix.

### Foreign Patent Document Rows (6 rows)

Each row has 6 fields: cite number, foreign document number (country code-number-kind code), publication date, name of patentee, relevant pages/columns/lines, and a checkbox for English translation attached.

| Row | Cite No | Document Number | Publication Date | Name of Patentee | Pages/Columns/Lines | Translation |
|-----|---------|----------------|-----------------|------------------|---------------------|-------------|
| 1 | `text104` | `text105` | `text106` | `text107` | `text108` | `box109` (CheckBox) |
| 2 | `text110` | `text111` | `text112` | `text113` | `text114` | `box115` (CheckBox) |
| 3 | `text116` | `text117` | `text118` | `text119` | `text120` | `box21` (CheckBox) |
| 4 | `text122` | `text123` | `text124` | `text125` | `text126` | `box127` (CheckBox) |
| 5 | `text128` | `text129` | `text130` | `text131` | `text132` | `box133` (CheckBox) |
| 6 | `text134` | `text135` | `text136` | `text137` | `text138` | `box39` (CheckBox) |

#### Foreign Patent Field Name Pattern

The foreign patent section does NOT follow a simple arithmetic pattern. The text fields are mostly sequential (text104-text138, skipping text109/115/121), but the checkbox field names are irregular: `box109`, `box115`, `box21`, `box127`, `box133`, `box39`. Use the explicit mapping table above rather than computing field names.

Note: Row 3's checkbox is `box21` (not `box121`) and row 6's checkbox is `box39` (not `box139`). These appear to be naming errors in the original PDF template.

### Foreign Patent Row Lookup (for programmatic use)

```python
FOREIGN_ROWS = [
    # (cite_no, doc_number, pub_date, patentee, pages, translation_checkbox)
    ("text104", "text105", "text106", "text107", "text108", "box109"),
    ("text110", "text111", "text112", "text113", "text114", "box115"),
    ("text116", "text117", "text118", "text119", "text120", "box21"),
    ("text122", "text123", "text124", "text125", "text126", "box127"),
    ("text128", "text129", "text130", "text131", "text132", "box133"),
    ("text134", "text135", "text136", "text137", "text138", "box39"),
]
```

## Fill Example

```python
import fitz

def fill_08a(template_path: str, output_path: str, data: dict) -> int:
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

# Header data
header = {
    "text3": "18/123,456",
    "text4": "03/11/2026",
    "text5": "John Q. Inventor",
    "text6": "2100",
    "text7": "Smith, Jane",
    "text8": "ACME-001",
    "Text1": "1",   # Sheet 1 (capital T)
    "text2": "2",   # of 2
}

# U.S. Patent citations — 19 rows max per sheet
us_patents = [
    ("A1", "10,234,567 B2", "01-15-2020", "Smith, John", "Col. 3, lines 1-25"),
    ("A2", "2021/0012345 A1", "06-30-2021", "Jones, Alice", "Fig. 2; para [0045]"),
    ("A3", "9,876,543 B1", "11-05-2018", "Chen, Wei", "Abstract"),
]

us_data = {}
for i, (cite, doc_num, pub_date, patentee, pages) in enumerate(us_patents):
    base = 9 + i * 5
    us_data[f"text{base}"] = cite
    us_data[f"text{base + 1}"] = doc_num
    us_data[f"text{base + 2}"] = pub_date
    us_data[f"text{base + 3}"] = patentee
    us_data[f"text{base + 4}"] = pages

# Foreign patent citations — 6 rows max per sheet
# Use the FOREIGN_ROWS lookup for field names
FOREIGN_ROWS = [
    ("text104", "text105", "text106", "text107", "text108", "box109"),
    ("text110", "text111", "text112", "text113", "text114", "box115"),
    ("text116", "text117", "text118", "text119", "text120", "box21"),
    ("text122", "text123", "text124", "text125", "text126", "box127"),
    ("text128", "text129", "text130", "text131", "text132", "box133"),
    ("text134", "text135", "text136", "text137", "text138", "box39"),
]

foreign_patents = [
    ("B1", "EP-1234567-A1", "03-22-2019", "Muller, Hans", "pp. 5-8", False),
    ("B2", "JP-2020-123456-A", "09-10-2020", "Tanaka, Kenji", "Figs. 1-3", True),
]

foreign_data = {}
for i, (cite, doc_num, pub_date, patentee, pages, has_translation) in enumerate(foreign_patents):
    cite_f, doc_f, date_f, pat_f, pages_f, trans_f = FOREIGN_ROWS[i]
    foreign_data[cite_f] = cite
    foreign_data[doc_f] = doc_num
    foreign_data[date_f] = pub_date
    foreign_data[pat_f] = patentee
    foreign_data[pages_f] = pages
    if has_translation:
        foreign_data[trans_f] = True

fill_08a(
    "sb0008a_ids.pdf",
    "ids_main_filled.pdf",
    {**header, **us_data, **foreign_data},
)
```
