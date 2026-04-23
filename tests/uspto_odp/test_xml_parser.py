"""Tests for USPTO ODP ST.96 XML parser."""

from patent_client_agents.uspto_odp.xml_parser import (
    parse_claims_xml,
    parse_document_xml,
    parse_grant_claims_xml,
    parse_spec_xml,
)

CLAIMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<uspat:ClaimsDocument xmlns:uspat="urn:us:gov:doc:uspto:patent"
    xmlns:com="http://www.wipo.int/standards/XMLSchema/ST96/Common"
    xmlns:pat="http://www.wipo.int/standards/XMLSchema/ST96/Patent"
    xmlns:uscom="urn:us:gov:doc:uspto:common"
    com:id="DOC1" com:st96Version="V2_1" com:ipoVersion="US_V7_1">
<uspat:DocumentMetadata com:id="ID-00001">
<uscom:DocumentCode>CLM</uscom:DocumentCode>
<uscom:ApplicationNumberText>16999555</uscom:ApplicationNumberText>
<com:PageTotalQuantity>2</com:PageTotalQuantity>
<uscom:OfficialDate>2023-01-15</uscom:OfficialDate>
</uspat:DocumentMetadata>
<uspat:ClaimStatement> WHAT IS CLAIMED IS:</uspat:ClaimStatement>
<uspat:Claims com:id="CLM-00000">
<uspat:Claim com:id="CLM-00001"><pat:ClaimNumber>1</pat:ClaimNumber>
<uspat:ClaimText>1.   A widget comprising: </uspat:ClaimText>
<uspat:ClaimText>a first component; and </uspat:ClaimText>
<uspat:ClaimText>a second component coupled to the first component. </uspat:ClaimText>
</uspat:Claim>
<uspat:Claim com:id="CLM-00002"><pat:ClaimNumber>2</pat:ClaimNumber>
<uspat:ClaimText>2.   The widget of claim <uspat:ClaimReference com:idrefs="CLM-00001">\
1</uspat:ClaimReference> wherein the first component is red.</uspat:ClaimText>
</uspat:Claim>
<uspat:Claim com:id="CLM-00003"><pat:ClaimNumber>3</pat:ClaimNumber>
<uspat:ClaimText>3.   A method of making a widget.</uspat:ClaimText>
</uspat:Claim>
</uspat:Claims>
</uspat:ClaimsDocument>
"""

SPEC_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<uspat:SpecificationDocument xmlns:uspat="urn:us:gov:doc:uspto:patent"
    xmlns:com="http://www.wipo.int/standards/XMLSchema/ST96/Common"
    xmlns:uscom="urn:us:gov:doc:uspto:common"
    com:id="DOC2" com:st96Version="V2_1" com:ipoVersion="US_V7_1">
<uspat:DocumentMetadata com:id="ID-00001">
<uscom:DocumentCode>SPEC</uscom:DocumentCode>
<uscom:ApplicationNumberText>16999555</uscom:ApplicationNumberText>
<com:PageTotalQuantity>10</com:PageTotalQuantity>
<uscom:ParagraphTotalQuantity>25</uscom:ParagraphTotalQuantity>
<uscom:OfficialDate>2023-01-15</uscom:OfficialDate>
</uspat:DocumentMetadata>
<uscom:Heading com:id="h-1">WIDGET TITLE</uscom:Heading>
<uscom:Heading com:id="h-2">BACKGROUND</uscom:Heading>
<uscom:P com:id="p-1" uscom:pNumber="001">Widgets are well known.</uscom:P>
<uscom:P com:id="p-2" uscom:pNumber="002">Prior widgets have problems.</uscom:P>
<uscom:BoundaryDataReference com:idref="BDR-0001"/>
<uscom:Heading com:id="h-3">SUMMARY</uscom:Heading>
<uscom:P com:id="p-3" uscom:pNumber="003">The present invention solves these problems.</uscom:P>
</uspat:SpecificationDocument>
"""

ABST_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<uspat:SpecificationDocument xmlns:uspat="urn:us:gov:doc:uspto:patent"
    xmlns:com="http://www.wipo.int/standards/XMLSchema/ST96/Common"
    xmlns:uscom="urn:us:gov:doc:uspto:common"
    com:id="DOC3" com:st96Version="V2_1" com:ipoVersion="US_V7_1">
<uspat:DocumentMetadata com:id="ID-00001">
<uscom:DocumentCode>ABST</uscom:DocumentCode>
<uscom:ApplicationNumberText>16999555</uscom:ApplicationNumberText>
<com:PageTotalQuantity>1</com:PageTotalQuantity>
<uscom:ParagraphTotalQuantity>1</uscom:ParagraphTotalQuantity>
<uscom:OfficialDate>2023-01-15</uscom:OfficialDate>
</uspat:DocumentMetadata>
<uscom:Heading com:id="h-1">ABSTRACT</uscom:Heading>
<uscom:P com:id="p-1">A widget for doing widget things efficiently.</uscom:P>
</uspat:SpecificationDocument>
"""


class TestParseClaimsXml:
    def test_metadata(self):
        result = parse_claims_xml(CLAIMS_XML)
        assert result["documentCode"] == "CLM"
        assert result["applicationNumber"] == "16999555"
        assert result["officialDate"] == "2023-01-15"
        assert result["pageTotalQuantity"] == 2

    def test_claim_statement(self):
        result = parse_claims_xml(CLAIMS_XML)
        assert result["claimStatement"] == "WHAT IS CLAIMED IS:"

    def test_claim_count(self):
        result = parse_claims_xml(CLAIMS_XML)
        assert len(result["claims"]) == 3

    def test_independent_claim(self):
        result = parse_claims_xml(CLAIMS_XML)
        c1 = result["claims"][0]
        assert c1["claim_number"] == 1
        assert c1["claim_type"] == "independent"
        assert c1["depends_on"] is None
        assert "A widget comprising:" in c1["claim_text"]
        assert "a first component" in c1["claim_text"]

    def test_dependent_claim(self):
        result = parse_claims_xml(CLAIMS_XML)
        c2 = result["claims"][1]
        assert c2["claim_number"] == 2
        assert c2["claim_type"] == "dependent"
        assert c2["depends_on"] == 1
        assert "first component is red" in c2["claim_text"]

    def test_claim_number_preserved_in_text(self):
        result = parse_claims_xml(CLAIMS_XML)
        # Claim text should include the leading claim number (e.g. "1.   A widget")
        for claim in result["claims"]:
            assert claim["claim_text"].startswith(f"{claim['claim_number']}.")

    def test_flat_claims_newline_separated(self):
        result = parse_claims_xml(CLAIMS_XML)
        c1 = result["claims"][0]
        # Flat sibling ClaimText elements should be separated by newlines
        assert "\n" in c1["claim_text"]
        assert "a first component" in c1["claim_text"]
        assert "a second component" in c1["claim_text"]

    def test_second_independent_claim(self):
        result = parse_claims_xml(CLAIMS_XML)
        c3 = result["claims"][2]
        assert c3["claim_number"] == 3
        assert c3["claim_type"] == "independent"
        assert c3["depends_on"] is None


NESTED_CLAIMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<uspat:ClaimsDocument xmlns:uspat="urn:us:gov:doc:uspto:patent"
    xmlns:com="http://www.wipo.int/standards/XMLSchema/ST96/Common"
    xmlns:pat="http://www.wipo.int/standards/XMLSchema/ST96/Patent"
    xmlns:uscom="urn:us:gov:doc:uspto:common"
    com:id="DOC1" com:st96Version="V2_1" com:ipoVersion="US_V7_1">
<uspat:Claims com:id="CLM-00000">
<uspat:Claim com:id="CLM-00001"><pat:ClaimNumber>1</pat:ClaimNumber>
<uspat:ClaimText>1.   An apparatus comprising:
<uspat:ClaimText>a machine readable medium having stored thereon instructions to:
<uspat:ClaimText>determine whether a device is authorized;</uspat:ClaimText>
<uspat:ClaimText>determine whether a user is authorized;</uspat:ClaimText>
</uspat:ClaimText>
<uspat:ClaimText>a processor coupled to the medium.</uspat:ClaimText>
</uspat:ClaimText>
</uspat:Claim>
</uspat:Claims>
</uspat:ClaimsDocument>
"""


class TestNestedClaimText:
    def test_preserves_newlines(self):
        result = parse_claims_xml(NESTED_CLAIMS_XML)
        text = result["claims"][0]["claim_text"]
        assert "\n" in text

    def test_indentation_depth(self):
        result = parse_claims_xml(NESTED_CLAIMS_XML)
        text = result["claims"][0]["claim_text"]
        lines = text.split("\n")
        # Preamble at depth 0 (no indent), includes claim number
        assert lines[0] == "1.   An apparatus comprising:"
        # Body elements at depth 1 (4 spaces)
        assert lines[1].startswith("    ")
        assert "a machine readable medium" in lines[1]
        # Sub-elements at depth 2 (8 spaces)
        assert lines[2].startswith("        ")
        assert "determine whether a device" in lines[2]

    def test_sibling_at_same_depth(self):
        result = parse_claims_xml(NESTED_CLAIMS_XML)
        text = result["claims"][0]["claim_text"]
        lines = text.split("\n")
        # "a processor coupled..." should be at depth 1, same as "a machine readable..."
        processor_line = next(line for line in lines if "a processor" in line)
        assert processor_line.startswith("    ") and not processor_line.startswith("        ")


GRANT_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE us-patent-grant SYSTEM "us-patent-grant.dtd">
<us-patent-grant>
<us-claim-statement>What is claimed is:</us-claim-statement>
<claims id="claims">
<claim id="CLM-00001" num="00001">
<claim-text>1. An apparatus comprising:
<claim-text>a first component configured to:
<claim-text>perform action A; and</claim-text>
<claim-text>perform action B;</claim-text>
</claim-text>
<claim-text>a second component coupled to the first component.</claim-text>
</claim-text>
</claim>
<claim id="CLM-00002" num="00002">
<claim-text>2. The apparatus of <claim-ref idref="CLM-00001">claim 1</claim-ref>\
, wherein the first component is red.</claim-text>
</claim>
</claims>
</us-patent-grant>
"""


class TestParseGrantClaimsXml:
    def test_claim_count(self):
        result = parse_grant_claims_xml(GRANT_XML)
        assert len(result) == 2

    def test_independent_claim_formatted(self):
        result = parse_grant_claims_xml(GRANT_XML)
        c1 = result[0]
        assert c1["claim_number"] == 1
        assert c1["claim_type"] == "independent"
        assert c1["depends_on"] is None
        lines = c1["claim_text"].split("\n")
        assert lines[0] == "1. An apparatus comprising:"
        assert lines[1].startswith("    ")
        assert "a first component" in lines[1]
        # Depth 2
        assert lines[2].startswith("        ")
        assert "perform action A" in lines[2]

    def test_dependent_claim(self):
        result = parse_grant_claims_xml(GRANT_XML)
        c2 = result[1]
        assert c2["claim_number"] == 2
        assert c2["claim_type"] == "dependent"
        assert c2["depends_on"] == 1
        assert "first component is red" in c2["claim_text"]

    def test_claim_ref_inline(self):
        result = parse_grant_claims_xml(GRANT_XML)
        c2 = result[1]
        # claim-ref text should be inlined, not on a separate line
        assert "claim 1" in c2["claim_text"]
        assert "\n" not in c2["claim_text"]


class TestParseSpecXml:
    def test_metadata(self):
        result = parse_spec_xml(SPEC_XML)
        assert result["documentCode"] == "SPEC"
        assert result["applicationNumber"] == "16999555"
        assert result["pageTotalQuantity"] == 10
        assert result["paragraphTotalQuantity"] == 25

    def test_markdown_headings(self):
        result = parse_spec_xml(SPEC_XML)
        assert "## BACKGROUND" in result["description"]
        assert "## SUMMARY" in result["description"]

    def test_paragraphs_present(self):
        result = parse_spec_xml(SPEC_XML)
        assert "Widgets are well known." in result["description"]
        assert "Prior widgets have problems." in result["description"]
        assert "The present invention solves these problems." in result["description"]

    def test_boundary_data_stripped(self):
        result = parse_spec_xml(SPEC_XML)
        assert "BDR-" not in result["description"]
        assert "BoundaryData" not in result["description"]


class TestParseAbstractXml:
    def test_abstract_text(self):
        result = parse_spec_xml(ABST_XML)
        assert result["documentCode"] == "ABST"
        assert "A widget for doing widget things" in result["description"]

    def test_abstract_heading(self):
        result = parse_spec_xml(ABST_XML)
        assert "## ABSTRACT" in result["description"]


class TestParseDocumentXml:
    def test_dispatches_claims(self):
        result = parse_document_xml(CLAIMS_XML)
        assert "claims" in result
        assert len(result["claims"]) == 3

    def test_dispatches_spec(self):
        result = parse_document_xml(SPEC_XML)
        assert "description" in result
        assert "## BACKGROUND" in result["description"]

    def test_dispatches_abstract(self):
        result = parse_document_xml(ABST_XML)
        assert "description" in result
