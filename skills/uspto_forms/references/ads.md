# ADS (PTO/AIA/14) — XFA Field Map

Form: Application Data Sheet (PTO/AIA/14)
PDF type: **XFA-only** (0 AcroForm widgets, 178 XFA fields)
Source: `aia0014.pdf` from USPTO
Library: `pikepdf` + `xml.etree.ElementTree`

## XFA Structure

The XFA array has 11 named streams. Only `datasets` (index 7) needs modification:

| Index | Name | Purpose | Size |
|-------|------|---------|------|
| 0-1 | xdp:xdp | Namespace preamble | 162 B |
| 2-3 | config | LiveCycle settings | 2 KB |
| 4-5 | template | Form layout/field definitions | 401 KB |
| **6-7** | **datasets** | **Field values (fill target)** | **10 KB** |
| 8-9 | localeSet | Locale settings | 2.5 KB |
| 10-11 | connectionSet | Data connections | 408 B |
| 12-13 | schema | XML schema | 29 KB |
| 14-15 | xmpmeta | XMP metadata | 1 KB |
| 16-17 | xfdf | XFDF data | 80 B |
| 18-19 | form | Form state | 6 KB |
| 20-21 | \</xdp:xdp\> | Closing tag | 10 B |

## Accessing the Datasets

```python
import pikepdf
import xml.etree.ElementTree as ET

pdf = pikepdf.Pdf.open("aia0014.pdf")
xfa = pdf.Root.AcroForm.XFA
datasets_xml = xfa[7].read_bytes().decode("utf-8")
ns = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}
root = ET.fromstring(datasets_xml)
data = root.find(".//xfa:data", ns)
us_req = data.find("us-request")
```

## Complete Field Tree

Root path: `xfa:data > us-request`

### Top-Level Fields (direct children of `us-request`)

| XML Path | Description |
|----------|-------------|
| `invention-title` | Title of invention |
| `attorney-docket-number` | Attorney docket number |
| `version-info` | Form version (default "2.1") |
| `numofpages` | Number of pages (default "8") |

### ContentArea1 — Applicant Information

Base: `us-request > ContentArea1`

**Repeating subform.** `sfApplicantInformation` has `<occur max="-1"/>` in the XFA template — unlimited inventors. The default datasets XML contains one instance. Add more by deep-copying the block, clearing values, setting `sfAuth.appSeq` to the inventor number, and inserting as a sibling in `ContentArea1`.

Other repeating subforms: `sfDomesticContinuity`, `sfForeignPriorityInfo`, `sfAssigneeInformation`, `sfSignature` (all `max="-1"`). `sfAttrynyName` allows up to 10. `sfAssigneeEmail` allows up to 3.

```python
import copy

# Add inventor 2 (inventor 1 is the existing block)
inv1 = ca1.find("sfApplicantInformation")
inv2 = copy.deepcopy(inv1)
for elem in inv2.iter():
    if elem.text and elem.text.strip():
        elem.text = None
_set(inv2, "sfAuth.appSeq", "2")
_set(inv2, "sfApplicantName.firstName", "Jane")
_set(inv2, "sfApplicantName.lastName", "Coinventor")
# ... fill residency, citizenship, mailing address ...
ca1.insert(list(ca1).index(inv1) + 1, inv2)
```

#### Applicant Name
Path: `ContentArea1 > sfApplicantInformation > sfApplicantName`

| Field | Description |
|-------|-------------|
| `prefix` | Name prefix (Dr., Mr., etc.) |
| `firstName` | First name — **NOTE: missing from default XML, must add via SubElement** |
| `middleName` | Middle name — **also missing, add via SubElement** |
| `lastName` | Last name — **also missing, add via SubElement** |
| `suffix` | Name suffix (Jr., III, etc.) |

**Important:** The default datasets XML only has `<prefix/>` and `<suffix/>` under `sfApplicantName`. The `firstName`, `middleName`, and `lastName` elements must be created with `ET.SubElement()`.

#### Residency
Path: `ContentArea1 > sfApplicantInformation > sfAppResChk`

**Country codes:** All country fields use WIPO ST.3 two-letter codes (same as PCT): `US`, `FR`, `GB`, `DE`, `JP`, `CN`, `BR`, `KR`, etc. Do NOT use full country names.

| Field | Path from sfAppResChk | Values |
|-------|----------------------|--------|
| Residency type | `resCheck > ResidencyRadio` | `us-residency`, `non-us-residency`, `active-us-military` |
| US city | `sfUSres > rsCityTxt` | Free text |
| US state | `sfUSres > rsStTxt` | Two-letter state code |
| US country | `sfUSres > rsCtryTxt` | WIPO ST.3 code (e.g. `"US"`) |
| Non-US city | `sfNonUSRes > nonresCity` | Free text |
| Non-US country | `sfNonUSRes > nonresCtryList` | WIPO ST.3 code (e.g. `"FR"`, `"GB"`, `"DE"`) |
| Military branch | `sfMil > actMilDropDown` | Dropdown value |

#### Citizenship
Path: `ContentArea1 > sfApplicantInformation > sfCitz`

| Field | Description |
|-------|-------------|
| `CitizedDropDown` | Country of citizenship (WIPO ST.3 code, e.g. `"FR"`, `"US"`, `"CN"`) |

#### Mailing Address
Path: `ContentArea1 > sfApplicantInformation > sfApplicantMail`

| Field | Description |
|-------|-------------|
| `mailCountry` | Country (WIPO ST.3 code) |
| `postcode` | ZIP/postal code |
| `address1` | Street address line 1 |
| `address2` | Street address line 2 |
| `city` | City |
| `state` | State |

#### Inventor Representative Info
Path: `ContentArea1 > sfApplicantInformation > sfInventorRepInfo`

Sub-sections mirror applicant structure: `sfReporgChoice`, `sfRepAppResChk`, `sfRepCitz`, `sfRepApplicantMail`.

### ContentArea2 — Correspondence, Application Info, Attorney

Base: `us-request > ContentArea2`

#### Correspondence Address
Path: `ContentArea2 > sfCorrAddress`

| Field | Description |
|-------|-------------|
| `Name1` | Name line 1 |
| `Name2` | Name line 2 |
| `address1` | Street address line 1 |
| `address2` | Street address line 2 |
| `city` | City |
| `state` | State |
| `corrCountry` | Country |
| `postcode` | ZIP code |
| `phone` | Phone number |
| `fax` | Fax number |

Customer number: `ContentArea2 > sfCorrCustNo > customerNumber`
Email: `ContentArea2 > sfemail > email`

#### Application Information
Path: `ContentArea2 > sfAppinfoFlow > sfAppPos`

| Field | Description | Values |
|-------|-------------|--------|
| `chkSmallEntity` | Small entity checkbox | `"0"` / `"1"` |
| `class` | USPC class | Free text |
| `subclass` | USPC subclass | Free text |
| `us_suggested-tech_center` | Suggested tech center | Free text |
| `us-total_number_of_drawing-sheets` | Total drawing sheets | Free text (e.g. `"0"`, `"5"`) |
| `us-suggested_representative_figure` | Suggested representative figure | Free text |
| `application_type` | Application type | `"REGULAR"` (Nonprovisional), `"PROVSNL"` (Provisional) |
| `us_submission_type` | Subject matter | `"UTL"` (Utility), `"DES"` (Design), `"PLT"` (Plant) |

#### Plant Patent
Path: `ContentArea2 > sfPlant`

| Field | Description |
|-------|-------------|
| `latin_name` | Latin plant name |
| `variety` | Plant variety |

#### Filing By Reference
Path: `ContentArea2 > sffilingby`

| Field | Description |
|-------|-------------|
| `app` | Application number |
| `date` | Filing date |
| `intellectual` | Intellectual property |

#### Publication
Path: `ContentArea2 > sfPub`

| Field | Description |
|-------|-------------|
| `early` | Request early publication ("0"/"1") |
| `nonPublication` | Non-publication request |

#### Attorney/Agent
Path: `ContentArea2 > sfAttorny`

| Field | Path | Description |
|-------|------|-------------|
| Choice | `sfrepheader > attornyChoice` | `customer-number` or `us-attorney-agent` |
| Customer # | `sfAttornyFlow > sfcustomerNumber > customerNumberTxt` | USPTO customer number |
| Attorney prefix | `sfAttornyFlow > sfAttrynyName > prefix` | Name prefix |
| Attorney first | `sfAttornyFlow > sfAttrynyName > first-name` | First name |
| Attorney middle | `sfAttornyFlow > sfAttrynyName > middle-name` | Middle name |
| Attorney last | `sfAttornyFlow > sfAttrynyName > last-name` | Last name |
| Attorney suffix | `sfAttornyFlow > sfAttrynyName > suffix` | Name suffix |
| Reg number | `sfAttornyFlow > sfAttrynyName > attrnyRegNameTxt` | Registration number |

#### Domestic Continuity
Path: `ContentArea2 > sfDomesticContinuity`

| Field | Path | Description |
|-------|------|-------------|
| App status | `sfDomesContinuity > sfdomesContAppStat > domAppStatusList` | Status dropdown |
| App number | `sfDomesContInfo > domappNumber` | Application number |
| Continuity type | `sfDomesContInfo > domesContList` | Continuation type |
| Prior app number | `sfDomesContInfo > domPriorAppNum` | Prior application number |
| Filing date | `sfDomesContInfo > DateTimeField1` | Filing date |

#### Foreign Priority
Path: `ContentArea2 > sfForeignPriorityInfo`

| Field | Description |
|-------|-------------|
| `frprAppNum` | Foreign application number |
| `accessCode` | Access code |
| `frprctryList` | Country |
| `frprParentDate` | Priority date |
| `prClaim` | Priority claim |

#### Assignee
Path: `ContentArea2 > sfAssigneeInformation`

| Field | Path | Description | Values |
|-------|------|-------------|--------|
| Entity type | `sfAssigneebtn > lstInvType` | Inventor type dropdown | Free text |
| Legal entity | `sfAssigneebtn > LegalRadio` | Applicant type radio | `"assignee"`, `"legal-representative"`, `"joint-inventor"`, `"party-of-interest"` |
| Org checkbox | `sfAssigneorgChoice > chkOrg` | "0"/"1" |
| Org name | `sfAssigneorgChoice > sforgName > orgName` | Organization name |
| First name | `sfApplicantName > first-name` | Assignee first name |
| Last name | `sfApplicantName > last-name` | Assignee last name |
| Address 1 | `sfAssigneeAddress > address-1` | Street address |
| City | `sfAssigneeAddress > city` | City |
| State | `sfAssigneeAddress > state` | State |
| Postcode | `sfAssigneeAddress > postcode` | ZIP code |
| Country | `sfAssigneeAddress > txtCorrCtry` | Country |

#### Signature
Path: `ContentArea2 > sfSignature > sfSig`

| Field | Description |
|-------|-------------|
| `registration-number` | Attorney registration number |
| `first-name` | Signer first name |
| `last-name` | Signer last name |
| `signature` | Signature text (e.g., "/John Doe/") |
| `date` | Signature date |

## Complete Fill Example

```python
import pikepdf
import xml.etree.ElementTree as ET


def fill_ads(template_path: str, output_path: str, data: dict) -> None:
    pdf = pikepdf.Pdf.open(template_path)
    xfa = pdf.Root.AcroForm.XFA
    datasets_xml = xfa[7].read_bytes().decode("utf-8")
    ns = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}
    root = ET.fromstring(datasets_xml)
    xfa_data = root.find(".//xfa:data", ns)
    us_req = xfa_data.find("us-request")

    def _set(parent, path, value):
        """Set field by dot path, creating missing elements."""
        parts = path.split(".")
        current = parent
        for part in parts[:-1]:
            child = current.find(part)
            if child is None:
                child = ET.SubElement(current, part)
            current = child
        target = current.find(parts[-1])
        if target is None:
            target = ET.SubElement(current, parts[-1])
        target.text = str(value)

    # Top-level
    _set(us_req, "invention-title", data.get("title", ""))
    _set(us_req, "attorney-docket-number", data.get("docket_number", ""))

    # Applicant
    ca1 = us_req.find("ContentArea1")
    app_info = ca1.find("sfApplicantInformation")
    app_name = app_info.find("sfApplicantName")
    for field in ("firstName", "middleName", "lastName"):
        key = field.lower().replace("name", "_name")  # first_name, etc.
        if key in data:
            _set(app_name, field, data[key])

    # Residency
    if data.get("residency") == "us":
        _set(app_info, "sfAppResChk.resCheck.ResidencyRadio", "us-residency")
        _set(app_info, "sfAppResChk.sfUSres.rsCityTxt", data.get("city", ""))
        _set(app_info, "sfAppResChk.sfUSres.rsStTxt", data.get("state", ""))
        _set(app_info, "sfAppResChk.sfUSres.rsCtryTxt", "US")

    # Mailing address
    mail = app_info.find("sfApplicantMail")
    if mail is not None:
        for xml_field, key in [
            ("address1", "address1"), ("address2", "address2"),
            ("city", "city"), ("state", "state"),
            ("postcode", "zip"), ("mailCountry", "country"),
        ]:
            if key in data:
                _set(mail, xml_field, data[key])

    # Correspondence (ContentArea2)
    ca2 = us_req.find("ContentArea2")
    if data.get("customer_number"):
        _set(ca2, "sfCorrCustNo.customerNumber", data["customer_number"])

    # Attorney
    if data.get("attorney_customer_number"):
        _set(ca2, "sfAttorny.sfrepheader.attornyChoice", "customer-number")
        _set(ca2, "sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt",
             data["attorney_customer_number"])

    # Assignee
    if data.get("assignee_org"):
        _set(ca2, "sfAssigneeInformation.sfAssigneorgChoice.chkOrg", "1")
        _set(ca2, "sfAssigneeInformation.sfAssigneorgChoice.sforgName.orgName",
             data["assignee_org"])

    # Signature
    if data.get("signature"):
        _set(ca2, "sfSignature.sfSig.signature", data["signature"])
        _set(ca2, "sfSignature.sfSig.date", data.get("signature_date", ""))
        _set(ca2, "sfSignature.sfSig.first-name", data.get("signer_first", ""))
        _set(ca2, "sfSignature.sfSig.last-name", data.get("signer_last", ""))
        _set(ca2, "sfSignature.sfSig.registration-number",
             data.get("signer_reg_number", ""))

    # Write back
    modified_xml = ET.tostring(root, encoding="unicode")
    xfa[7] = pikepdf.Stream(pdf, modified_xml.encode("utf-8"))
    pdf.save(output_path)
    pdf.close()
```
