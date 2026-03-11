"""Comprehensive tests for USPTO form filling.

Tests cover:
- ADS (XFA): pikepdf XML manipulation, field creation, round-trip verification
- ADS multiple inventors via repeating subforms
- POA 82A/82B/82C (AcroForm): split forms, independent fill, merge
- Declaration, Substitute Statement, IDS (AcroForm)
- Edge cases: empty fields, special characters, all fields filled
"""

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

import fitz  # PyMuPDF
import pikepdf
import pytest

TEMPLATES = Path(__file__).parent.parent / "skills" / "uspto_forms" / "templates"
ADS_PDF = TEMPLATES / "aia0014_ads.pdf"
POA_PDF = TEMPLATES / "aia0082_poa.pdf"
POA_82A_PDF = TEMPLATES / "aia0082a_transmittal.pdf"
POA_82B_PDF = TEMPLATES / "aia0082b_client_poa.pdf"
POA_82C_PDF = TEMPLATES / "aia0082c_practitioner_list.pdf"
DECLARATION_PDF = TEMPLATES / "aia0001_declaration.pdf"
SUBSTITUTE_PDF = TEMPLATES / "aia0002_substitute_statement.pdf"
IDS_08A_PDF = TEMPLATES / "sb0008a_ids.pdf"
IDS_08B_PDF = TEMPLATES / "sb0008b_ids_cont.pdf"

XFA_NS = {"xfa": "http://www.xfa.org/schema/xfa-data/1.0/"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def fill_acroform(template: Path, output: Path, data: dict) -> int:
    """Fill an AcroForm PDF and return count of fields filled."""
    doc = fitz.open(str(template))
    filled = 0
    for page in doc:
        for widget in page.widgets():
            if widget.field_name in data:
                widget.field_value = data[widget.field_name]
                widget.update()
                filled += 1
    doc.save(str(output))
    doc.close()
    return filled


def read_acroform_values(path: Path) -> dict:
    """Read all non-empty field values from an AcroForm PDF."""
    doc = fitz.open(str(path))
    values = {}
    for page in doc:
        for widget in page.widgets():
            if widget.field_value:
                values[widget.field_name] = widget.field_value
    doc.close()
    return values


def get_xfa_data(path: Path) -> ET.Element:
    """Extract the xfa:data element from an XFA PDF."""
    pdf = pikepdf.Pdf.open(str(path))
    xml_bytes = pdf.Root.AcroForm.XFA[7].read_bytes()
    root = ET.fromstring(xml_bytes.decode("utf-8"))
    data = root.find(".//xfa:data", XFA_NS)
    pdf.close()
    return data


def set_xfa_field(parent: ET.Element, path: str, value: str) -> bool:
    """Set a field in XFA XML by dot-separated path, creating missing elements."""
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
    target.text = value
    return True


def fill_ads_xfa(template: Path, output: Path, field_map: dict[str, str]) -> None:
    """Fill ADS XFA form. field_map keys are dot-paths from us-request."""
    pdf = pikepdf.Pdf.open(str(template))
    xfa = pdf.Root.AcroForm.XFA
    datasets_xml = xfa[7].read_bytes().decode("utf-8")
    root = ET.fromstring(datasets_xml)
    xfa_data = root.find(".//xfa:data", XFA_NS)
    us_req = xfa_data.find("us-request")

    for path, value in field_map.items():
        set_xfa_field(us_req, path, value)

    modified = ET.tostring(root, encoding="unicode")
    xfa[7] = pikepdf.Stream(pdf, modified.encode("utf-8"))
    pdf.save(str(output))
    pdf.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_pdf(tmp_path):
    """Return a function that generates a temp PDF path."""
    counter = [0]

    def _make(name="output"):
        counter[0] += 1
        return tmp_path / f"{name}_{counter[0]}.pdf"

    return _make


# ---------------------------------------------------------------------------
# ADS (XFA) Tests
# ---------------------------------------------------------------------------


class TestADSStructure:
    """Verify the ADS PDF has the expected XFA structure."""

    def test_is_xfa_form(self):
        pdf = pikepdf.Pdf.open(str(ADS_PDF))
        assert "/AcroForm" in pdf.Root
        assert "/XFA" in pdf.Root.AcroForm
        pdf.close()

    def test_has_no_acroform_widgets(self):
        doc = fitz.open(str(ADS_PDF))
        widgets = []
        for page in doc:
            widgets.extend(list(page.widgets()))
        doc.close()
        assert len(widgets) == 0, "ADS should be XFA-only with no AcroForm widgets"

    def test_xfa_array_structure(self):
        pdf = pikepdf.Pdf.open(str(ADS_PDF))
        xfa = pdf.Root.AcroForm.XFA
        assert len(xfa) == 22, "XFA array should have 22 entries (11 name-stream pairs)"

        # Verify names at even indices
        names = [str(xfa[i]) for i in range(0, len(xfa), 2)]
        assert "datasets" in names
        assert "template" in names
        assert "config" in names
        pdf.close()

    def test_datasets_is_at_index_7(self):
        pdf = pikepdf.Pdf.open(str(ADS_PDF))
        xfa = pdf.Root.AcroForm.XFA
        assert str(xfa[6]) == "datasets"
        assert isinstance(xfa[7], pikepdf.Stream)
        pdf.close()

    def test_datasets_is_valid_xml(self):
        data = get_xfa_data(ADS_PDF)
        assert data is not None
        us_req = data.find("us-request")
        assert us_req is not None

    def test_datasets_has_expected_sections(self):
        data = get_xfa_data(ADS_PDF)
        us_req = data.find("us-request")
        assert us_req.find("ContentArea1") is not None
        assert us_req.find("ContentArea2") is not None
        assert us_req.find("invention-title") is not None
        assert us_req.find("attorney-docket-number") is not None


class TestADSFilling:
    """Test filling ADS XFA fields."""

    def test_fill_invention_title(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "invention-title": "Method for Automated Form Filling",
        })
        data = get_xfa_data(out)
        us_req = data.find("us-request")
        assert us_req.find("invention-title").text == "Method for Automated Form Filling"

    def test_fill_docket_number(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "attorney-docket-number": "ACME-2026-001",
        })
        data = get_xfa_data(out)
        us_req = data.find("us-request")
        assert us_req.find("attorney-docket-number").text == "ACME-2026-001"

    def test_fill_applicant_name_creates_missing_elements(self, tmp_pdf):
        """firstName/middleName/lastName are not in the default XML — must be created."""
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea1.sfApplicantInformation.sfApplicantName.firstName": "John",
            "ContentArea1.sfApplicantInformation.sfApplicantName.middleName": "Quincy",
            "ContentArea1.sfApplicantInformation.sfApplicantName.lastName": "Inventor",
        })
        data = get_xfa_data(out)
        us_req = data.find("us-request")
        app_name = us_req.find(".//sfApplicantName")
        assert app_name.find("firstName").text == "John"
        assert app_name.find("middleName").text == "Quincy"
        assert app_name.find("lastName").text == "Inventor"

    def test_fill_residency(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea1.sfApplicantInformation.sfAppResChk.resCheck.ResidencyRadio": "us-residency",
            "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCityTxt": "Houston",
            "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsStTxt": "TX",
            "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCtryTxt": "US",
        })
        data = get_xfa_data(out)
        us_req = data.find("us-request")
        assert us_req.find(".//rsCityTxt").text == "Houston"
        assert us_req.find(".//rsStTxt").text == "TX"

    def test_fill_mailing_address(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea1.sfApplicantInformation.sfApplicantMail.address1": "123 Main St",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.city": "Houston",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.state": "TX",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.postcode": "77002",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.mailCountry": "US",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfApplicantMail/address1").text == "123 Main St"
        assert data.find(".//sfApplicantMail/postcode").text == "77002"

    def test_fill_customer_number(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfCorrCustNo.customerNumber": "12345",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfCorrCustNo/customerNumber").text == "12345"

    def test_fill_attorney_by_customer_number(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfAttorny.sfrepheader.attornyChoice": "customer-number",
            "ContentArea2.sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt": "54321",
        })
        data = get_xfa_data(out)
        assert data.find(".//attornyChoice").text == "customer-number"
        assert data.find(".//customerNumberTxt").text == "54321"

    def test_fill_signature(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfSignature.sfSig.signature": "/Parker Hancock/",
            "ContentArea2.sfSignature.sfSig.date": "03/11/2026",
            "ContentArea2.sfSignature.sfSig.first-name": "Parker",
            "ContentArea2.sfSignature.sfSig.last-name": "Hancock",
            "ContentArea2.sfSignature.sfSig.registration-number": "99999",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfSig/signature").text == "/Parker Hancock/"
        assert data.find(".//sfSig/date").text == "03/11/2026"

    def test_fill_assignee_org(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfAssigneeInformation.sfAssigneorgChoice.chkOrg": "1",
            "ContentArea2.sfAssigneeInformation.sfAssigneorgChoice.sforgName.orgName": "Acme Corp",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfAssigneeInformation//orgName").text == "Acme Corp"

    def test_fill_correspondence_address(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfCorrAddress.Name1": "Baker Botts L.L.P.",
            "ContentArea2.sfCorrAddress.address1": "910 Louisiana St",
            "ContentArea2.sfCorrAddress.city": "Houston",
            "ContentArea2.sfCorrAddress.state": "TX",
            "ContentArea2.sfCorrAddress.postcode": "77002",
            "ContentArea2.sfCorrAddress.corrCountry": "US",
            "ContentArea2.sfCorrAddress.phone": "713-229-1234",
            "ContentArea2.sfemail.email": "test@bakerbotts.com",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfCorrAddress/Name1").text == "Baker Botts L.L.P."
        assert data.find(".//sfCorrAddress/city").text == "Houston"
        assert data.find(".//sfemail/email").text == "test@bakerbotts.com"

    def test_fill_application_info(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfAppinfoFlow.sfAppPos.us-total_number_of_drawing-sheets": "10",
            "ContentArea2.sfAppinfoFlow.sfAppPos.us-suggested_representative_figure": "1",
            "ContentArea2.sfAppinfoFlow.sfAppPos.chkSmallEntity": "1",
        })
        data = get_xfa_data(out)
        assert data.find(".//us-total_number_of_drawing-sheets").text == "10"
        assert data.find(".//chkSmallEntity").text == "1"

    def test_fill_foreign_priority(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfForeignPriorityInfo.frprAppNum": "JP2025-123456",
            "ContentArea2.sfForeignPriorityInfo.frprctryList": "JP",
            "ContentArea2.sfForeignPriorityInfo.frprParentDate": "01/15/2025",
        })
        data = get_xfa_data(out)
        assert data.find(".//frprAppNum").text == "JP2025-123456"

    def test_fill_domestic_continuity(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea2.sfDomesticContinuity.sfDomesContInfo.domappNumber": "17/999,888",
            "ContentArea2.sfDomesticContinuity.sfDomesContInfo.domPriorAppNum": "63/111,222",
            "ContentArea2.sfDomesticContinuity.sfDomesContInfo.DateTimeField1": "06/01/2024",
        })
        data = get_xfa_data(out)
        assert data.find(".//domappNumber").text == "17/999,888"

    def test_special_characters_in_title(self, tmp_pdf):
        out = tmp_pdf("ads")
        title = 'Method for Processing α-Amino Acids & "Complex" Compounds <v2>'
        fill_ads_xfa(ADS_PDF, out, {"invention-title": title})
        data = get_xfa_data(out)
        assert data.find(".//invention-title").text == title

    def test_full_ads_roundtrip(self, tmp_pdf):
        """Fill many fields at once and verify all survive round-trip."""
        out = tmp_pdf("ads")
        fields = {
            "invention-title": "Automated Patent Filing System",
            "attorney-docket-number": "BB-2026-042",
            "ContentArea1.sfApplicantInformation.sfApplicantName.firstName": "Jane",
            "ContentArea1.sfApplicantInformation.sfApplicantName.lastName": "Smith",
            "ContentArea1.sfApplicantInformation.sfAppResChk.resCheck.ResidencyRadio": "us-residency",
            "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCityTxt": "Austin",
            "ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsStTxt": "TX",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.address1": "456 Oak Ave",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.city": "Austin",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.state": "TX",
            "ContentArea1.sfApplicantInformation.sfApplicantMail.postcode": "78701",
            "ContentArea2.sfCorrCustNo.customerNumber": "99999",
            "ContentArea2.sfAttorny.sfrepheader.attornyChoice": "customer-number",
            "ContentArea2.sfAttorny.sfAttornyFlow.sfcustomerNumber.customerNumberTxt": "99999",
            "ContentArea2.sfSignature.sfSig.signature": "/Jane Smith/",
            "ContentArea2.sfSignature.sfSig.date": "03/11/2026",
        }
        fill_ads_xfa(ADS_PDF, out, fields)

        # Verify every field
        data = get_xfa_data(out)
        us_req = data.find("us-request")
        assert us_req.find("invention-title").text == "Automated Patent Filing System"
        assert us_req.find("attorney-docket-number").text == "BB-2026-042"
        assert us_req.find(".//sfApplicantName/firstName").text == "Jane"
        assert us_req.find(".//sfApplicantName/lastName").text == "Smith"
        assert us_req.find(".//rsCityTxt").text == "Austin"
        assert us_req.find(".//customerNumberTxt").text == "99999"
        assert us_req.find(".//sfSig/signature").text == "/Jane Smith/"

    def test_output_is_valid_pdf(self, tmp_pdf):
        """Filled ADS can be opened by both pikepdf and PyMuPDF."""
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {"invention-title": "Test"})

        # pikepdf can open it
        pdf = pikepdf.Pdf.open(str(out))
        assert "/AcroForm" in pdf.Root
        pdf.close()

        # PyMuPDF can open it
        doc = fitz.open(str(out))
        assert len(doc) >= 1
        doc.close()


class TestADSMultipleInventors:
    """Test adding multiple inventors via XFA repeating subforms."""

    @staticmethod
    def _add_inventors(template: Path, output: Path, inventors: list[dict]) -> None:
        """Fill ADS with multiple inventors."""
        pdf = pikepdf.Pdf.open(str(template))
        xfa = pdf.Root.AcroForm.XFA
        datasets_xml = xfa[7].read_bytes().decode("utf-8")
        root = ET.fromstring(datasets_xml)
        data = root.find(".//{http://www.xfa.org/schema/xfa-data/1.0/}data")
        us_req = data.find("us-request")
        ca1 = us_req.find("ContentArea1")
        app_info = ca1.find("sfApplicantInformation")

        # Fill first inventor into existing block
        set_xfa_field(app_info, "sfAuth.appSeq", "1")
        for key, value in inventors[0].items():
            set_xfa_field(app_info, key, value)

        # Add additional inventors as copies
        for i, inv_data in enumerate(inventors[1:], 2):
            new_block = copy.deepcopy(app_info)
            for elem in new_block.iter():
                if elem.text and elem.text.strip():
                    elem.text = None
            set_xfa_field(new_block, "sfAuth.appSeq", str(i))
            for key, value in inv_data.items():
                set_xfa_field(new_block, key, value)
            # Insert after last sfApplicantInformation
            all_blocks = ca1.findall("sfApplicantInformation")
            last_idx = list(ca1).index(all_blocks[-1])
            ca1.insert(last_idx + 1, new_block)

        modified_xml = ET.tostring(root, encoding="unicode")
        xfa[7] = pikepdf.Stream(pdf, modified_xml.encode("utf-8"))
        pdf.save(str(output))
        pdf.close()

    def test_two_inventors(self, tmp_pdf):
        out = tmp_pdf("ads_2inv")
        self._add_inventors(ADS_PDF, out, [
            {"sfApplicantName.firstName": "John", "sfApplicantName.lastName": "Inventor"},
            {"sfApplicantName.firstName": "Jane", "sfApplicantName.lastName": "Coinventor"},
        ])
        data = get_xfa_data(out)
        ca1 = data.find(".//ContentArea1")
        invs = ca1.findall("sfApplicantInformation")
        assert len(invs) == 2
        assert invs[0].find(".//firstName").text == "John"
        assert invs[1].find(".//firstName").text == "Jane"
        assert invs[0].find(".//appSeq").text == "1"
        assert invs[1].find(".//appSeq").text == "2"

    def test_three_inventors_with_details(self, tmp_pdf):
        out = tmp_pdf("ads_3inv")
        self._add_inventors(ADS_PDF, out, [
            {
                "sfApplicantName.firstName": "Alice",
                "sfApplicantName.lastName": "Alpha",
                "sfAppResChk.resCheck.ResidencyRadio": "us-residency",
                "sfAppResChk.sfUSres.rsCityTxt": "Austin",
                "sfAppResChk.sfUSres.rsStTxt": "TX",
            },
            {
                "sfApplicantName.firstName": "Bob",
                "sfApplicantName.lastName": "Beta",
                "sfAppResChk.resCheck.ResidencyRadio": "us-residency",
                "sfAppResChk.sfUSres.rsCityTxt": "Dallas",
                "sfAppResChk.sfUSres.rsStTxt": "TX",
            },
            {
                "sfApplicantName.firstName": "Carol",
                "sfApplicantName.lastName": "Gamma",
                "sfAppResChk.resCheck.ResidencyRadio": "non-us-residency",
                "sfAppResChk.sfNonUSRes.nonresCity": "Tokyo",
                "sfAppResChk.sfNonUSRes.nonresCtryList": "JP",
            },
        ])
        data = get_xfa_data(out)
        ca1 = data.find(".//ContentArea1")
        invs = ca1.findall("sfApplicantInformation")
        assert len(invs) == 3
        assert invs[0].find(".//lastName").text == "Alpha"
        assert invs[1].find(".//lastName").text == "Beta"
        assert invs[2].find(".//lastName").text == "Gamma"
        assert invs[2].find(".//nonresCity").text == "Tokyo"
        # Verify appSeq numbering
        for i, inv in enumerate(invs, 1):
            assert inv.find(".//appSeq").text == str(i)

    def test_single_inventor_still_works(self, tmp_pdf):
        """Calling with one inventor should not duplicate blocks."""
        out = tmp_pdf("ads_1inv")
        self._add_inventors(ADS_PDF, out, [
            {"sfApplicantName.firstName": "Solo", "sfApplicantName.lastName": "Inventor"},
        ])
        data = get_xfa_data(out)
        ca1 = data.find(".//ContentArea1")
        invs = ca1.findall("sfApplicantInformation")
        assert len(invs) == 1
        assert invs[0].find(".//firstName").text == "Solo"

    def test_roundtrip_preserves_all_inventors(self, tmp_pdf):
        """Write 4 inventors, re-read, verify all survive."""
        out = tmp_pdf("ads_4inv")
        names = [("Inv1First", "Inv1Last"), ("Inv2First", "Inv2Last"),
                 ("Inv3First", "Inv3Last"), ("Inv4First", "Inv4Last")]
        inventors = [
            {"sfApplicantName.firstName": fn, "sfApplicantName.lastName": ln}
            for fn, ln in names
        ]
        self._add_inventors(ADS_PDF, out, inventors)

        data = get_xfa_data(out)
        ca1 = data.find(".//ContentArea1")
        invs = ca1.findall("sfApplicantInformation")
        assert len(invs) == 4
        for i, (fn, ln) in enumerate(names):
            assert invs[i].find(".//firstName").text == fn
            assert invs[i].find(".//lastName").text == ln

    def test_repeating_subform_template_allows_unlimited(self):
        """Verify the XFA template declares max=-1 on sfApplicantInformation."""
        pdf = pikepdf.Pdf.open(str(ADS_PDF))
        template_xml = pdf.Root.AcroForm.XFA[5].read_bytes().decode("utf-8")
        pdf.close()
        # Find the occur element after sfApplicantInformation
        import re
        match = re.search(
            r'name="sfApplicantInformation"[^>]*>.*?<occur\s+max="(-?\d+)"',
            template_xml, re.DOTALL
        )
        assert match is not None
        assert match.group(1) == "-1", "sfApplicantInformation should allow unlimited repeats"


# ---------------------------------------------------------------------------
# POA (AcroForm) Tests
# ---------------------------------------------------------------------------


class TestPOAStructure:
    """Verify the POA PDF has the expected AcroForm structure."""

    def test_is_acroform(self):
        doc = fitz.open(str(POA_PDF))
        assert doc.is_form_pdf > 0
        doc.close()

    def test_has_no_xfa(self):
        pdf = pikepdf.Pdf.open(str(POA_PDF))
        xfa = pdf.Root.AcroForm.get("/XFA")
        assert xfa is None or str(xfa) == "null"
        pdf.close()

    def test_has_63_fields(self):
        doc = fitz.open(str(POA_PDF))
        fields = []
        for page in doc:
            fields.extend(list(page.widgets()))
        doc.close()
        assert len(fields) == 63

    def test_has_expected_field_names(self):
        doc = fitz.open(str(POA_PDF))
        names = set()
        for page in doc:
            for w in page.widgets():
                names.add(w.field_name)
        doc.close()
        expected = {
            "Application Number", "Filing Date", "First Named Inventor",
            "Title", "Art Unit", "Attorney Docket Number", "Signature",
            "Name", "Registration Number", "Customer Number",
        }
        assert expected.issubset(names)

    def test_has_checkbox_fields(self):
        doc = fitz.open(str(POA_PDF))
        checkboxes = []
        for page in doc:
            for w in page.widgets():
                if w.field_type_string == "CheckBox":
                    checkboxes.append(w.field_name)
        doc.close()
        assert len(checkboxes) > 0
        assert "Inventor or Joint inventor" in checkboxes

    def test_has_practitioner_rows(self):
        doc = fitz.open(str(POA_PDF))
        names = set()
        for page in doc:
            for w in page.widgets():
                names.add(w.field_name)
        doc.close()
        for i in range(1, 11):
            assert f"NameRow{i}" in names
            assert f"Registration NumberRow{i}" in names


class TestPOAFilling:
    """Test filling POA AcroForm fields."""

    def test_fill_text_fields(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {
            "Application Number": "18/123,456",
            "Filing Date": "03/11/2026",
            "First Named Inventor": "John Inventor",
            "Title": "Test Widget",
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 4

        values = read_acroform_values(out)
        assert values["Application Number"] == "18/123,456"
        assert values["First Named Inventor"] == "John Inventor"

    def test_fill_checkbox(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {
            "Inventor or Joint inventor": True,
            "Appoint attorneys listed under customer number": True,
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 2

        values = read_acroform_values(out)
        assert values["Inventor or Joint inventor"] == "Yes"

    def test_fill_signature_fields(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {
            "Signature": "/Parker Hancock/",
            "Date Optional": "03/11/2026",
            "Name": "Parker Hancock",
            "Registration Number": "99999",
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 4

        values = read_acroform_values(out)
        assert values["Signature"] == "/Parker Hancock/"

    def test_fill_practitioner_list(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {}
        practitioners = [
            ("Alice Attorney", "11111"),
            ("Bob Barrister", "22222"),
            ("Carol Counsel", "33333"),
        ]
        for i, (name, reg) in enumerate(practitioners, 1):
            data[f"NameRow{i}"] = name
            data[f"Registration NumberRow{i}"] = reg

        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 6

        values = read_acroform_values(out)
        assert values["NameRow1"] == "Alice Attorney"
        assert values["Registration NumberRow3"] == "33333"

    def test_fill_customer_number_appointment(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "12345",
            "The address with the above mentioned customer number": True,
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 3

        values = read_acroform_values(out)
        assert values["Customer Number"] == "12345"

    def test_fill_correspondence_address(self, tmp_pdf):
        out = tmp_pdf("poa")
        data = {
            "Box for Firm or Individual Name": True,
            "Firm or Individual Name": "Baker Botts L.L.P.",
            "Street Address": "910 Louisiana St",
            "City": "Houston",
            "State_2": "TX",
            "Zip": "77002",
            "Country": "US",
            "Telephone Number": "713-229-1234",
            "Email Address": "test@bakerbotts.com",
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == 9

        values = read_acroform_values(out)
        assert values["Firm or Individual Name"] == "Baker Botts L.L.P."
        assert values["City"] == "Houston"

    def test_full_poa_roundtrip(self, tmp_pdf):
        """Fill all major sections and verify round-trip."""
        out = tmp_pdf("poa")
        data = {
            "Application Number": "18/999,888",
            "Filing Date": "01/15/2026",
            "First Named Inventor": "Jane Doe",
            "Title": "Quantum Widget Processor",
            "Art Unit": "3600",
            "Attorney Docket Number": "QWP-001",
            "Signature": "/Parker Hancock/",
            "Date Optional": "03/11/2026",
            "Name": "Parker Hancock",
            "Registration Number": "99999",
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "54321",
            "Inventor or Joint inventor": True,
            "Signature of the applicant for patent": "/Jane Doe/",
            "Name of the Signer": "Jane Doe",
            "Date Optional_2": "03/11/2026",
        }
        filled = fill_acroform(POA_PDF, out, data)
        assert filled == len(data)

        values = read_acroform_values(out)
        for key, expected in data.items():
            if isinstance(expected, bool):
                assert values.get(key) == "Yes"
            else:
                assert values.get(key) == expected, f"Mismatch on {key}"

    def test_unfilled_fields_remain_empty(self, tmp_pdf):
        """Fields not in data dict should remain empty."""
        out = tmp_pdf("poa")
        fill_acroform(POA_PDF, out, {"Title": "Only This"})

        values = read_acroform_values(out)
        assert values.get("Title") == "Only This"
        assert "Application Number" not in values
        assert "First Named Inventor" not in values


# ---------------------------------------------------------------------------
# POA Split Forms (82A / 82B / 82C) Tests
# ---------------------------------------------------------------------------


class TestPOASplitStructure:
    """Verify the split POA PDFs have correct structure."""

    def test_82a_has_15_fields(self):
        doc = fitz.open(str(POA_82A_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 15

    def test_82b_has_28_fields(self):
        doc = fitz.open(str(POA_82B_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 28

    def test_82c_has_20_fields(self):
        doc = fitz.open(str(POA_82C_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 20

    def test_82a_is_single_page(self):
        doc = fitz.open(str(POA_82A_PDF))
        assert len(doc) == 1
        doc.close()

    def test_82b_is_single_page(self):
        doc = fitz.open(str(POA_82B_PDF))
        assert len(doc) == 1
        doc.close()

    def test_82c_is_single_page(self):
        doc = fitz.open(str(POA_82C_PDF))
        assert len(doc) == 1
        doc.close()

    def test_82a_has_app_number_field(self):
        doc = fitz.open(str(POA_82A_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        assert "Application Number" in names
        assert "Signature" in names
        assert "Attorney Docket Number" in names

    def test_82b_has_client_signature_field(self):
        doc = fitz.open(str(POA_82B_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        assert "Signature of the applicant for patent" in names
        assert "Customer Number" in names
        assert "Inventor or Joint inventor" in names

    def test_82c_has_practitioner_rows(self):
        doc = fitz.open(str(POA_82C_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        for i in range(1, 11):
            assert f"NameRow{i}" in names
            assert f"Registration NumberRow{i}" in names

    def test_split_fields_sum_to_combined(self):
        """82A + 82B + 82C fields should equal the original 82 (minus privacy page)."""
        total_split = 0
        for path in [POA_82A_PDF, POA_82B_PDF, POA_82C_PDF]:
            doc = fitz.open(str(path))
            total_split += sum(1 for page in doc for _ in page.widgets())
            doc.close()
        assert total_split == 63  # matches original 82's field count


class TestPOA82AFilling:
    """Test filling the 82A transmittal (per-application)."""

    def test_fill_application_info(self, tmp_pdf):
        out = tmp_pdf("82a")
        data = {
            "Application Number": "18/123,456",
            "Filing Date": "03/11/2026",
            "First Named Inventor": "John Q. Inventor",
            "Title": "Widget Processor",
            "Art Unit": "2100",
            "Attorney Docket Number": "ACME-001",
        }
        filled = fill_acroform(POA_82A_PDF, out, data)
        assert filled == 6
        values = read_acroform_values(out)
        assert values["Application Number"] == "18/123,456"
        assert values["Title"] == "Widget Processor"

    def test_fill_attorney_signature(self, tmp_pdf):
        out = tmp_pdf("82a")
        data = {
            "Signature": "/Parker Hancock/",
            "Date Optional": "03/11/2026",
            "Name": "Parker Hancock",
            "Registration Number": "99999",
        }
        filled = fill_acroform(POA_82A_PDF, out, data)
        assert filled == 4
        values = read_acroform_values(out)
        assert values["Signature"] == "/Parker Hancock/"

    def test_fill_82a_for_multiple_apps(self, tmp_pdf):
        """Same template, different app numbers — core reuse pattern."""
        apps = [
            ("18/111,111", "Widget A", "ACME-001"),
            ("18/222,222", "Widget B", "ACME-002"),
            ("18/333,333", "Widget C", "ACME-003"),
        ]
        for app_num, title, docket in apps:
            out = tmp_pdf("82a")
            data = {
                "Application Number": app_num,
                "Title": title,
                "Attorney Docket Number": docket,
                "Signature": "/Parker Hancock/",
                "Name": "Parker Hancock",
                "Registration Number": "99999",
            }
            fill_acroform(POA_82A_PDF, out, data)
            values = read_acroform_values(out)
            assert values["Application Number"] == app_num
            assert values["Attorney Docket Number"] == docket


class TestPOA82BFilling:
    """Test filling the 82B client signature page."""

    def test_fill_customer_number_appointment(self, tmp_pdf):
        out = tmp_pdf("82b")
        data = {
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "12345",
            "The address with the above mentioned customer number": True,
        }
        filled = fill_acroform(POA_82B_PDF, out, data)
        assert filled == 3
        values = read_acroform_values(out)
        assert values["Customer Number"] == "12345"
        assert values["Appoint attorneys listed under customer number"] == "Yes"

    def test_fill_client_signature(self, tmp_pdf):
        out = tmp_pdf("82b")
        data = {
            "Assignee": True,
            "Applicant Name (if applicant is a juristic entity)": "Acme Corporation",
            "Signature of the applicant for patent": "/Craig Schwartz/",
            "Name of the Signer": "Craig Schwartz",
            "Title of the Signer": "General Counsel",
            "Date Optional_2": "03/11/2026",
        }
        filled = fill_acroform(POA_82B_PDF, out, data)
        assert filled == 6
        values = read_acroform_values(out)
        assert values["Signature of the applicant for patent"] == "/Craig Schwartz/"
        assert values["Title of the Signer"] == "General Counsel"

    def test_fill_manual_correspondence_address(self, tmp_pdf):
        out = tmp_pdf("82b")
        data = {
            "Box for Firm or Individual Name": True,
            "Firm or Individual Name": "Baker Botts L.L.P.",
            "Street Address": "910 Louisiana St",
            "City": "Houston",
            "State_2": "TX",
            "Zip": "77002",
            "Country": "US",
            "Telephone Number": "713-229-1234",
            "Email Address": "patent@bakerbotts.com",
        }
        filled = fill_acroform(POA_82B_PDF, out, data)
        assert filled == 9
        values = read_acroform_values(out)
        assert values["City"] == "Houston"

    def test_full_82b_roundtrip(self, tmp_pdf):
        out = tmp_pdf("82b")
        data = {
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "12345",
            "The address with the above mentioned customer number": True,
            "Assignee": True,
            "Applicant Name (if applicant is a juristic entity)": "Acme Corp",
            "Signature of the applicant for patent": "/Jane Doe/",
            "Name of the Signer": "Jane Doe",
            "Title of the Signer": "CEO",
            "Date Optional_2": "03/11/2026",
        }
        filled = fill_acroform(POA_82B_PDF, out, data)
        assert filled == len(data)
        values = read_acroform_values(out)
        for key, expected in data.items():
            if isinstance(expected, bool):
                assert values.get(key) == "Yes"
            else:
                assert values.get(key) == expected


class TestPOA82CFilling:
    """Test filling the 82C practitioner list."""

    def test_fill_practitioners(self, tmp_pdf):
        out = tmp_pdf("82c")
        practitioners = [
            ("Parker Hancock", "99999"),
            ("Alice Attorney", "11111"),
            ("Bob Barrister", "22222"),
        ]
        data = {}
        for i, (name, reg) in enumerate(practitioners, 1):
            data[f"NameRow{i}"] = name
            data[f"Registration NumberRow{i}"] = reg

        filled = fill_acroform(POA_82C_PDF, out, data)
        assert filled == 6
        values = read_acroform_values(out)
        assert values["NameRow1"] == "Parker Hancock"
        assert values["Registration NumberRow3"] == "22222"

    def test_fill_all_10_practitioners(self, tmp_pdf):
        out = tmp_pdf("82c")
        data = {}
        for i in range(1, 11):
            data[f"NameRow{i}"] = f"Attorney {i}"
            data[f"Registration NumberRow{i}"] = str(10000 + i)

        filled = fill_acroform(POA_82C_PDF, out, data)
        assert filled == 20
        values = read_acroform_values(out)
        assert values["NameRow10"] == "Attorney 10"
        assert values["Registration NumberRow10"] == "10010"


class TestPOAMerge:
    """Test merging split POA forms into a single filing PDF."""

    def test_merge_82a_and_82b(self, tmp_pdf):
        """Standard filing: transmittal + client signature."""
        out_a = tmp_pdf("82a")
        out_b = tmp_pdf("82b")
        merged = tmp_pdf("merged")

        fill_acroform(POA_82A_PDF, out_a, {
            "Application Number": "18/123,456",
            "Title": "Test Widget",
            "Signature": "/Parker Hancock/",
            "Name": "Parker Hancock",
            "Registration Number": "99999",
        })
        fill_acroform(POA_82B_PDF, out_b, {
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "12345",
            "Signature of the applicant for patent": "/Jane Doe/",
            "Name of the Signer": "Jane Doe",
            "Date Optional_2": "03/11/2026",
        })

        # Merge
        doc = fitz.open(str(out_a))
        doc.insert_pdf(fitz.open(str(out_b)))
        doc.save(str(merged))
        doc.close()

        # Verify merged PDF
        doc = fitz.open(str(merged))
        assert len(doc) == 2
        doc.close()

    def test_merge_all_three(self, tmp_pdf):
        """Full filing: 82A + 82B + 82C."""
        out_a = tmp_pdf("82a")
        out_b = tmp_pdf("82b")
        out_c = tmp_pdf("82c")
        merged = tmp_pdf("merged")

        fill_acroform(POA_82A_PDF, out_a, {"Application Number": "18/123,456"})
        fill_acroform(POA_82B_PDF, out_b, {"Customer Number": "12345"})
        fill_acroform(POA_82C_PDF, out_c, {"NameRow1": "Parker Hancock", "Registration NumberRow1": "99999"})

        doc = fitz.open(str(out_a))
        doc.insert_pdf(fitz.open(str(out_b)))
        doc.insert_pdf(fitz.open(str(out_c)))
        doc.save(str(merged))
        doc.close()

        doc = fitz.open(str(merged))
        assert len(doc) == 3
        doc.close()

    def test_reuse_82b_with_multiple_82a(self, tmp_pdf):
        """Core workflow: one client signature, multiple transmittals."""
        out_b = tmp_pdf("82b")
        fill_acroform(POA_82B_PDF, out_b, {
            "Appoint attorneys listed under customer number": True,
            "Customer Number": "12345",
            "Assignee": True,
            "Signature of the applicant for patent": "/Jane Doe/",
            "Name of the Signer": "Jane Doe",
            "Date Optional_2": "03/11/2026",
        })

        apps = [
            ("18/111,111", "Widget A"),
            ("18/222,222", "Widget B"),
            ("18/333,333", "Widget C"),
        ]
        for app_num, title in apps:
            out_a = tmp_pdf("82a")
            merged = tmp_pdf("merged")
            fill_acroform(POA_82A_PDF, out_a, {
                "Application Number": app_num,
                "Title": title,
                "Signature": "/Parker Hancock/",
                "Name": "Parker Hancock",
            })
            doc = fitz.open(str(out_a))
            doc.insert_pdf(fitz.open(str(out_b)))
            doc.save(str(merged))
            doc.close()

            # Each merged PDF should be 2 pages
            doc = fitz.open(str(merged))
            assert len(doc) == 2
            doc.close()


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases across all form types."""

    def test_empty_data_produces_valid_pdf_acroform(self, tmp_pdf):
        out = tmp_pdf("poa_empty")
        filled = fill_acroform(POA_PDF, out, {})
        assert filled == 0
        doc = fitz.open(str(out))
        assert len(doc) > 0
        doc.close()

    def test_empty_data_produces_valid_pdf_xfa(self, tmp_pdf):
        out = tmp_pdf("ads_empty")
        fill_ads_xfa(ADS_PDF, out, {})
        pdf = pikepdf.Pdf.open(str(out))
        assert "/AcroForm" in pdf.Root
        pdf.close()

    def test_nonexistent_field_ignored_acroform(self, tmp_pdf):
        out = tmp_pdf("poa")
        filled = fill_acroform(POA_PDF, out, {"Nonexistent Field": "value"})
        assert filled == 0

    def test_long_text_in_field(self, tmp_pdf):
        out = tmp_pdf("poa")
        long_title = "A" * 500
        fill_acroform(POA_PDF, out, {"Title": long_title})
        values = read_acroform_values(out)
        assert values["Title"] == long_title

    def test_unicode_in_acroform(self, tmp_pdf):
        out = tmp_pdf("poa")
        fill_acroform(POA_PDF, out, {"First Named Inventor": "José García-López"})
        values = read_acroform_values(out)
        assert values["First Named Inventor"] == "José García-López"

    def test_unicode_in_xfa(self, tmp_pdf):
        out = tmp_pdf("ads")
        fill_ads_xfa(ADS_PDF, out, {
            "ContentArea1.sfApplicantInformation.sfApplicantName.firstName": "Müller",
            "ContentArea1.sfApplicantInformation.sfApplicantName.lastName": "Schröder",
        })
        data = get_xfa_data(out)
        assert data.find(".//sfApplicantName/firstName").text == "Müller"
        assert data.find(".//sfApplicantName/lastName").text == "Schröder"

    def test_slash_signature_format(self, tmp_pdf):
        """USPTO e-signatures use /FirstName LastName/ format."""
        out = tmp_pdf("poa")
        fill_acroform(POA_PDF, out, {"Signature": "/John Q. Inventor/"})
        values = read_acroform_values(out)
        assert values["Signature"] == "/John Q. Inventor/"

    def test_multiple_fills_overwrite(self, tmp_pdf):
        """Filling twice should overwrite previous values."""
        intermediate = tmp_pdf("poa_v1")
        final = tmp_pdf("poa_v2")

        fill_acroform(POA_PDF, intermediate, {"Title": "First Title"})
        fill_acroform(intermediate, final, {"Title": "Second Title"})

        values = read_acroform_values(final)
        assert values["Title"] == "Second Title"


# ---------------------------------------------------------------------------
# Declaration (AIA/01) Tests
# ---------------------------------------------------------------------------


class TestDeclarationStructure:
    """Verify the Declaration PDF has the expected AcroForm structure."""

    def test_is_acroform(self):
        doc = fitz.open(str(DECLARATION_PDF))
        assert doc.is_form_pdf > 0
        doc.close()

    def test_has_8_fields(self):
        doc = fitz.open(str(DECLARATION_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 8

    def test_has_2_pages(self):
        doc = fitz.open(str(DECLARATION_PDF))
        assert len(doc) == 2
        doc.close()

    def test_all_fields_on_page_1(self):
        doc = fitz.open(str(DECLARATION_PDF))
        page1_fields = list(doc[0].widgets())
        page2_fields = list(doc[1].widgets())
        doc.close()
        assert len(page1_fields) == 8
        assert len(page2_fields) == 0

    def test_has_expected_fields(self):
        doc = fitz.open(str(DECLARATION_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        assert "Title of Invention" in names
        assert "Inventor" in names
        assert "Date Optional" in names
        assert "This declaration" in names


class TestDeclarationFilling:
    """Test filling Declaration form fields."""

    def test_fill_attached_application(self, tmp_pdf):
        out = tmp_pdf("decl")
        data = {
            "Title of Invention": "Widget Processing Method",
            "This declaration": True,
            "Inventor": "John Q. Inventor",
            "Date Optional": "03/11/2026",
            "Text4": "123 Main St, Austin, TX 78701",
        }
        filled = fill_acroform(DECLARATION_PDF, out, data)
        assert filled == 5
        values = read_acroform_values(out)
        assert values["Title of Invention"] == "Widget Processing Method"
        assert values["Inventor"] == "John Q. Inventor"

    def test_fill_previously_filed_application(self, tmp_pdf):
        out = tmp_pdf("decl")
        data = {
            "Title of Invention": "Widget Processing Method",
            "undefined": True,
            "United States application or PCT international application number": "18/123,456",
            "filed on": "01/15/2025",
            "Inventor": "John Q. Inventor",
        }
        filled = fill_acroform(DECLARATION_PDF, out, data)
        assert filled == 5
        values = read_acroform_values(out)
        assert values["United States application or PCT international application number"] == "18/123,456"
        assert values["filed on"] == "01/15/2025"

    def test_roundtrip_all_fields(self, tmp_pdf):
        out = tmp_pdf("decl")
        data = {
            "Title of Invention": "Test Invention",
            "This declaration": True,
            "Inventor": "Jane Smith",
            "Date Optional": "03/11/2026",
            "Text4": "456 Oak Ave, Dallas, TX 75201",
        }
        fill_acroform(DECLARATION_PDF, out, data)
        values = read_acroform_values(out)
        assert values["This declaration"] in ("Yes", "On")  # checkbox on-state varies by form
        assert values["Inventor"] == "Jane Smith"
        assert values["Text4"] == "456 Oak Ave, Dallas, TX 75201"


# ---------------------------------------------------------------------------
# Substitute Statement (AIA/02) Tests
# ---------------------------------------------------------------------------


class TestSubstituteStatementStructure:
    """Verify the Substitute Statement PDF has the expected structure."""

    def test_is_acroform(self):
        doc = fitz.open(str(SUBSTITUTE_PDF))
        assert doc.is_form_pdf > 0
        doc.close()

    def test_has_38_fields(self):
        doc = fitz.open(str(SUBSTITUTE_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 38

    def test_has_3_pages(self):
        doc = fitz.open(str(SUBSTITUTE_PDF))
        assert len(doc) == 3
        doc.close()

    def test_page3_has_no_fields(self):
        doc = fitz.open(str(SUBSTITUTE_PDF))
        page3_fields = list(doc[2].widgets())
        doc.close()
        assert len(page3_fields) == 0

    def test_has_expected_fields(self):
        doc = fitz.open(str(SUBSTITUTE_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        # Note: "Title of Invent ion" has embedded space (form typo)
        assert "Title of Invent ion" in names
        assert "Assignee" in names
        assert "Inventor is deceased" in names
        assert "Signature" in names


class TestSubstituteStatementFilling:
    """Test filling Substitute Statement form fields."""

    def test_fill_inventor_info(self, tmp_pdf):
        out = tmp_pdf("sub")
        data = {
            "Title of Invent ion": "Widget Processing Method",
            "The attached application": True,
            "Eg Given Name first and middle if any and Family Name or Surname": "John Q. Inventor",
            "City": "Austin",
            "State1": "TX",
            "Country1": "US",
        }
        filled = fill_acroform(SUBSTITUTE_PDF, out, data)
        assert filled == 6
        values = read_acroform_values(out)
        assert values["Title of Invent ion"] == "Widget Processing Method"
        assert values["City"] == "Austin"

    def test_fill_relationship_and_circumstance(self, tmp_pdf):
        out = tmp_pdf("sub")
        data = {
            "Assignee": True,
            "Inventor has refused to execute the oath or declaration under 37 CFR 163": True,
        }
        filled = fill_acroform(SUBSTITUTE_PDF, out, data)
        assert filled == 2
        values = read_acroform_values(out)
        assert values["Assignee"] in ("Yes", "On")

    def test_fill_signer_info(self, tmp_pdf):
        out = tmp_pdf("sub")
        data = {
            "1DPH": "Parker Hancock",
            "fill_3": "03/11/2026",
            "Signature": "/Parker Hancock/",
            "Applicant Name": "Acme Corp.",
            "Title of Person Executing This Substitute Statement": "Patent Counsel",
        }
        filled = fill_acroform(SUBSTITUTE_PDF, out, data)
        assert filled == 5
        values = read_acroform_values(out)
        assert values["1DPH"] == "Parker Hancock"
        assert values["Signature"] == "/Parker Hancock/"

    def test_full_roundtrip(self, tmp_pdf):
        out = tmp_pdf("sub")
        data = {
            "Title of Invent ion": "Widget Processing Method",
            "The attached application": True,
            "Eg Given Name first and middle if any and Family Name or Surname": "John Inventor",
            "City": "Austin",
            "State1": "TX",
            "Country1": "US",
            "Assignee": True,
            "Inventor cannot be found or reached after diligent effort or": True,
            "1DPH": "Parker Hancock",
            "fill_3": "03/11/2026",
            "Signature": "/Parker Hancock/",
            "Applicant Name": "Acme Corp.",
        }
        filled = fill_acroform(SUBSTITUTE_PDF, out, data)
        assert filled == 12
        values = read_acroform_values(out)
        assert values["Eg Given Name first and middle if any and Family Name or Surname"] == "John Inventor"
        assert values["Assignee"] in ("Yes", "On")
        assert values["1DPH"] == "Parker Hancock"


# ---------------------------------------------------------------------------
# IDS Main (SB/08a) Tests
# ---------------------------------------------------------------------------


class TestIDS08aStructure:
    """Verify the IDS main form has the expected structure."""

    def test_is_acroform(self):
        doc = fitz.open(str(IDS_08A_PDF))
        assert doc.is_form_pdf > 0
        doc.close()

    def test_has_139_fields(self):
        doc = fitz.open(str(IDS_08A_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 139

    def test_has_2_pages(self):
        doc = fitz.open(str(IDS_08A_PDF))
        assert len(doc) == 2
        doc.close()

    def test_all_fields_on_page_1(self):
        doc = fitz.open(str(IDS_08A_PDF))
        page1_fields = list(doc[0].widgets())
        page2_fields = list(doc[1].widgets())
        doc.close()
        assert len(page1_fields) == 139
        assert len(page2_fields) == 0

    def test_has_header_fields(self):
        doc = fitz.open(str(IDS_08A_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        for f in ["text3", "text4", "text5", "text6", "text7", "text8", "Text1", "text2"]:
            assert f in names, f"Missing header field {f}"

    def test_has_us_patent_fields(self):
        """19 rows x 5 fields = 95 US patent fields."""
        doc = fitz.open(str(IDS_08A_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        for row in range(19):
            base = 9 + row * 5
            for offset in range(5):
                assert f"text{base + offset}" in names

    def test_has_foreign_patent_checkboxes(self):
        doc = fitz.open(str(IDS_08A_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        # Irregular checkbox names per reference doc
        for box in ["box109", "box115", "box21", "box127", "box133", "box39"]:
            assert box in names, f"Missing foreign patent checkbox {box}"


class TestIDS08aFilling:
    """Test filling IDS main form fields."""

    def test_fill_header(self, tmp_pdf):
        out = tmp_pdf("ids")
        data = {
            "text3": "18/123,456",
            "text4": "03/11/2026",
            "text5": "John Q. Inventor",
            "text6": "2100",
            "text7": "Smith, Jane",
            "text8": "ACME-001",
            "Text1": "1",
            "text2": "2",
        }
        filled = fill_acroform(IDS_08A_PDF, out, data)
        assert filled == 8
        values = read_acroform_values(out)
        assert values["text3"] == "18/123,456"
        assert values["text5"] == "John Q. Inventor"
        assert values["Text1"] == "1"

    def test_fill_us_patent_rows(self, tmp_pdf):
        out = tmp_pdf("ids")
        us_patents = [
            ("A1", "10,234,567 B2", "01-15-2020", "Smith, John", "Col. 3, lines 1-25"),
            ("A2", "2021/0012345 A1", "06-30-2021", "Jones, Alice", "Fig. 2; para [0045]"),
        ]
        data = {}
        for i, (cite, doc_num, pub_date, patentee, pages) in enumerate(us_patents):
            base = 9 + i * 5
            data[f"text{base}"] = cite
            data[f"text{base + 1}"] = doc_num
            data[f"text{base + 2}"] = pub_date
            data[f"text{base + 3}"] = patentee
            data[f"text{base + 4}"] = pages
        filled = fill_acroform(IDS_08A_PDF, out, data)
        assert filled == 10
        values = read_acroform_values(out)
        assert values["text9"] == "A1"
        assert values["text10"] == "10,234,567 B2"
        assert values["text14"] == "A2"

    def test_fill_foreign_patent_with_translation(self, tmp_pdf):
        out = tmp_pdf("ids")
        # Row 1 foreign patent
        data = {
            "text104": "B1",
            "text105": "EP-1234567-A1",
            "text106": "03-22-2019",
            "text107": "Muller, Hans",
            "text108": "pp. 5-8",
            "box109": True,  # translation attached
        }
        filled = fill_acroform(IDS_08A_PDF, out, data)
        assert filled == 6
        values = read_acroform_values(out)
        assert values["text105"] == "EP-1234567-A1"
        assert values["box109"] == "Yes"

    def test_fill_all_19_us_rows(self, tmp_pdf):
        """Fill all 19 US patent rows to verify field name pattern."""
        out = tmp_pdf("ids")
        data = {}
        for i in range(19):
            base = 9 + i * 5
            data[f"text{base}"] = f"A{i + 1}"
            data[f"text{base + 1}"] = f"{10000000 + i} B2"
            data[f"text{base + 2}"] = f"01-{i + 1:02d}-2020"
            data[f"text{base + 3}"] = f"Inventor {i + 1}"
            data[f"text{base + 4}"] = f"Col. {i + 1}"
        filled = fill_acroform(IDS_08A_PDF, out, data)
        assert filled == 95
        values = read_acroform_values(out)
        assert values["text99"] == "A19"
        assert values["text103"] == "Col. 19"

    def test_foreign_row3_checkbox_is_box21(self, tmp_pdf):
        """Row 3's checkbox is box21 (not box121) — a naming error in the template."""
        out = tmp_pdf("ids")
        data = {
            "text116": "B3",
            "text117": "CN-112233-A",
            "box21": True,
        }
        filled = fill_acroform(IDS_08A_PDF, out, data)
        assert filled == 3
        values = read_acroform_values(out)
        assert values["box21"] == "Yes"


# ---------------------------------------------------------------------------
# IDS Continuation (SB/08b) Tests
# ---------------------------------------------------------------------------


class TestIDS08bStructure:
    """Verify the IDS continuation form has the expected structure."""

    def test_is_acroform(self):
        doc = fitz.open(str(IDS_08B_PDF))
        assert doc.is_form_pdf > 0
        doc.close()

    def test_has_38_fields(self):
        doc = fitz.open(str(IDS_08B_PDF))
        fields = [w for page in doc for w in page.widgets()]
        doc.close()
        assert len(fields) == 38

    def test_has_2_pages(self):
        doc = fitz.open(str(IDS_08B_PDF))
        assert len(doc) == 2
        doc.close()

    def test_has_header_fields(self):
        doc = fitz.open(str(IDS_08B_PDF))
        names = {w.field_name for page in doc for w in page.widgets()}
        doc.close()
        # Note: "text 6" has a space
        for f in ["text1", "text2", "text3", "text4", "text5", "text 6", "text7", "text8"]:
            assert f in names, f"Missing header field {f!r}"


class TestIDS08bFilling:
    """Test filling IDS continuation form fields."""

    def test_fill_header(self, tmp_pdf):
        out = tmp_pdf("ids_cont")
        data = {
            "text3": "18/123,456",
            "text4": "03/11/2026",
            "text5": "John Q. Inventor",
            "text 6": "2100",  # note space
            "text7": "Smith, Jane",
            "text8": "ACME-001",
            "text1": "2",
            "text2": "3",
        }
        filled = fill_acroform(IDS_08B_PDF, out, data)
        assert filled == 8
        values = read_acroform_values(out)
        assert values["text3"] == "18/123,456"
        assert values["text 6"] == "2100"

    def test_fill_npl_rows(self, tmp_pdf):
        out = tmp_pdf("ids_cont")
        npl_rows = [
            ("NL1", "SMITH, J., \"Machine Learning,\" J. IP Law, vol. 42, pp. 100-115, 2025.", False),
            ("NL2", "TANAKA, K., \"Automated Claims,\" Proc. AIPPI, pp. 50-62, 2024.", True),
        ]
        data = {}
        for i, (cite, citation, has_translation) in enumerate(npl_rows):
            base = 9 + i * 3
            data[f"text{base}"] = cite
            data[f"text{base + 1}"] = citation
            if has_translation:
                data[f"text{base + 2}"] = True
        filled = fill_acroform(IDS_08B_PDF, out, data)
        assert filled == 5  # 2 cite + 2 citation + 1 checkbox
        values = read_acroform_values(out)
        assert values["text9"] == "NL1"
        assert "Machine Learning" in values["text10"]
        assert values["text14"] == "Yes"  # translation checkbox for row 2

    def test_fill_all_10_npl_rows(self, tmp_pdf):
        """Fill all 10 NPL rows to verify field name pattern."""
        out = tmp_pdf("ids_cont")
        data = {}
        for i in range(10):
            base = 9 + i * 3
            data[f"text{base}"] = f"NL{i + 1}"
            data[f"text{base + 1}"] = f"Reference {i + 1}, Journal {i + 1}, 2025."
        filled = fill_acroform(IDS_08B_PDF, out, data)
        assert filled == 20  # 10 cite + 10 citation
        values = read_acroform_values(out)
        assert values["text36"] == "NL10"
        assert "Reference 10" in values["text37"]

    def test_text_6_space_in_name(self, tmp_pdf):
        """Verify the 'text 6' field (with space) works correctly."""
        out = tmp_pdf("ids_cont")
        fill_acroform(IDS_08B_PDF, out, {"text 6": "3700"})
        values = read_acroform_values(out)
        assert values["text 6"] == "3700"


# ---------------------------------------------------------------------------
# ADS Validation Tests
# ---------------------------------------------------------------------------

# Import validator from skill directory
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "uspto_forms"))
from validate_ads import ValidationError, extract_rules, validate_ads


class TestADSValidation:
    """Test ADS field validation against XFA template rules."""

    @pytest.fixture(scope="class")
    def rules(self):
        """Extract rules once for all tests in this class."""
        return extract_rules()

    def _base_valid(self) -> dict[str, str]:
        """Return a minimal valid ADS field_map."""
        return {
            "invention-title": "Method for Processing Widgets",
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

    def test_extract_rules_count(self, rules):
        assert len(rules) >= 50
        required = [r for r in rules if r.required]
        char_rules = [r for r in rules if r.valid_chars]
        assert len(required) == 42
        assert len(char_rules) >= 25

    def test_valid_filing_no_errors(self, rules):
        errors = validate_ads(self._base_valid(), rules=rules)
        assert len(errors) == 0

    def test_missing_inventor_name(self, rules):
        data = self._base_valid()
        del data["ContentArea1.sfApplicantInformation.sfApplicantName.firstName"]
        del data["ContentArea1.sfApplicantInformation.sfApplicantName.lastName"]
        errors = validate_ads(data, rules=rules)
        error_fields = {e.field for e in errors}
        assert any("firstName" in f for f in error_fields)
        assert any("lastName" in f for f in error_fields)

    def test_missing_title(self, rules):
        data = self._base_valid()
        del data["invention-title"]
        errors = validate_ads(data, rules=rules)
        assert any("invention-title" in e.field for e in errors)

    def test_invalid_customer_number_chars(self, rules):
        data = self._base_valid()
        data["ContentArea2.sfCorrCustNo.customerNumber"] = "ABC123"
        errors = validate_ads(data, rules=rules)
        char_errors = [e for e in errors if e.rule == "chars"]
        assert len(char_errors) >= 1
        assert any("customerNumber" in e.field for e in char_errors)

    def test_us_residency_suppresses_non_us(self, rules):
        """US residency should NOT require non-US city/country."""
        data = self._base_valid()
        errors = validate_ads(data, rules=rules)
        error_fields = {e.field for e in errors}
        assert not any("nonresCity" in f for f in error_fields)
        assert not any("nonresCtryList" in f for f in error_fields)

    def test_non_us_residency_requires_non_us_fields(self, rules):
        data = self._base_valid()
        data["ContentArea1.sfApplicantInformation.sfAppResChk.resCheck.ResidencyRadio"] = "non-us-residency"
        # Remove US-specific fields
        del data["ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCityTxt"]
        del data["ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsStTxt"]
        del data["ContentArea1.sfApplicantInformation.sfAppResChk.sfUSres.rsCtryTxt"]
        errors = validate_ads(data, rules=rules)
        error_fields = {e.field for e in errors}
        assert any("nonresCity" in f for f in error_fields)
        assert any("nonresCtryList" in f for f in error_fields)

    def test_customer_number_attorney_suppresses_named(self, rules):
        """Attorney by customer number should NOT require named attorney fields."""
        data = self._base_valid()
        errors = validate_ads(data, rules=rules)
        error_fields = {e.field for e in errors}
        assert not any("attrnyRegNameTxt" in f for f in error_fields)

    def test_optional_sections_not_required_when_empty(self, rules):
        """Continuity, foreign priority, assignee sections are optional."""
        data = self._base_valid()
        errors = validate_ads(data, rules=rules)
        error_fields = {e.field for e in errors}
        assert not any("sfDomesticContinuity" in f for f in error_fields)
        assert not any("sfForeignPriorityInfo" in f for f in error_fields)
        assert not any("sfAssigneeInformation" in f for f in error_fields)

    def test_postcode_allows_hyphen(self, rules):
        data = self._base_valid()
        data["ContentArea1.sfApplicantInformation.sfApplicantMail.postcode"] = "78701-1234"
        errors = validate_ads(data, rules=rules)
        char_errors = [e for e in errors if e.rule == "chars" and "postcode" in e.field]
        assert len(char_errors) == 0

    def test_all_errors_are_validation_error(self, rules):
        errors = validate_ads({}, rules=rules)
        for e in errors:
            assert isinstance(e, ValidationError)
            assert e.level in ("error", "warning")
            assert e.rule in ("required", "chars", "format")
