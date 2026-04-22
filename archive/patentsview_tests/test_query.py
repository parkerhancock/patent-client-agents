"""Tests for PatentsView query builder."""

from ip_tools.patentsview import PatentsViewQuery


class TestPatentsViewQuery:
    """Tests for the fluent query builder."""

    def test_empty_query(self):
        """Empty query returns empty dict."""
        query = PatentsViewQuery().build()
        assert query == {}

    def test_single_equals(self):
        """Single equals condition returns bare condition."""
        query = PatentsViewQuery().equals("patent_number", "10000000").build()
        assert query == {"patent_number": "10000000"}

    def test_single_gte(self):
        """Single gte condition returns bare condition."""
        query = PatentsViewQuery().gte("patent_date", "2020-01-01").build()
        assert query == {"_gte": {"patent_date": "2020-01-01"}}

    def test_single_lte(self):
        """Single lte condition."""
        query = PatentsViewQuery().lte("patent_date", "2023-12-31").build()
        assert query == {"_lte": {"patent_date": "2023-12-31"}}

    def test_single_gt(self):
        """Single gt condition."""
        query = PatentsViewQuery().gt("patent_num_claims", "10").build()
        assert query == {"_gt": {"patent_num_claims": "10"}}

    def test_single_lt(self):
        """Single lt condition."""
        query = PatentsViewQuery().lt("patent_num_claims", "50").build()
        assert query == {"_lt": {"patent_num_claims": "50"}}

    def test_text_any(self):
        """Text any condition."""
        query = PatentsViewQuery().text_any("patent_title", "machine learning").build()
        assert query == {"_text_any": {"patent_title": "machine learning"}}

    def test_text_all(self):
        """Text all condition."""
        query = PatentsViewQuery().text_all("patent_abstract", "neural network").build()
        assert query == {"_text_all": {"patent_abstract": "neural network"}}

    def test_text_phrase(self):
        """Text phrase condition."""
        query = PatentsViewQuery().text_phrase("claim_text", "comprising the steps").build()
        assert query == {"_text_phrase": {"claim_text": "comprising the steps"}}

    def test_begins(self):
        """Begins with condition."""
        query = PatentsViewQuery().begins("patent_number", "100").build()
        assert query == {"_begins": {"patent_number": "100"}}

    def test_contains(self):
        """Contains condition."""
        query = PatentsViewQuery().contains("assignee_organization", "Google").build()
        assert query == {"_contains": {"assignee_organization": "Google"}}

    def test_multiple_conditions_wrapped_in_and(self):
        """Multiple conditions are wrapped in _and."""
        query = PatentsViewQuery().cpc("H04L63").since("2020-01-01").build()
        assert query == {
            "_and": [
                {"_text_any": {"cpc_group_id": "H04L63"}},
                {"_gte": {"patent_date": "2020-01-01"}},
            ]
        }

    def test_convenience_methods(self):
        """Test convenience methods produce correct queries."""
        # patent_number
        q = PatentsViewQuery().patent_number("10000000").build()
        assert q == {"patent_number": "10000000"}

        # patent_id
        q = PatentsViewQuery().patent_id("abc123").build()
        assert q == {"patent_id": "abc123"}

        # cpc
        q = PatentsViewQuery().cpc("G06F").build()
        assert q == {"_text_any": {"cpc_group_id": "G06F"}}

        # cpc_subgroup
        q = PatentsViewQuery().cpc_subgroup("G06F21/00").build()
        assert q == {"_text_any": {"cpc_subgroup_id": "G06F21/00"}}

        # assignee
        q = PatentsViewQuery().assignee("Microsoft").build()
        assert q == {"_text_any": {"assignee_organization": "Microsoft"}}

        # inventor
        q = PatentsViewQuery().inventor("Smith").build()
        assert q == {"_text_any": {"inventor_last_name": "Smith"}}

        # title
        q = PatentsViewQuery().title("wireless").build()
        assert q == {"_text_any": {"patent_title": "wireless"}}

        # abstract
        q = PatentsViewQuery().abstract("encryption").build()
        assert q == {"_text_any": {"patent_abstract": "encryption"}}

        # since/until
        q = PatentsViewQuery().since("2020-01-01").until("2023-12-31").build()
        assert q == {
            "_and": [
                {"_gte": {"patent_date": "2020-01-01"}},
                {"_lte": {"patent_date": "2023-12-31"}},
            ]
        }

        # patent_type
        q = PatentsViewQuery().patent_type("utility").build()
        assert q == {"patent_type": "utility"}

    def test_chaining(self):
        """Test method chaining works correctly."""
        query = (
            PatentsViewQuery()
            .cpc("H04L63")
            .assignee("Google")
            .since("2020-01-01")
            .until("2023-12-31")
            .build()
        )
        assert query == {
            "_and": [
                {"_text_any": {"cpc_group_id": "H04L63"}},
                {"_text_any": {"assignee_organization": "Google"}},
                {"_gte": {"patent_date": "2020-01-01"}},
                {"_lte": {"patent_date": "2023-12-31"}},
            ]
        }


class TestStaticCombinators:
    """Tests for static and_/or_/not_ methods."""

    def test_and_empty(self):
        """AND with no queries returns empty."""
        assert PatentsViewQuery.and_() == {}
        assert PatentsViewQuery.and_({}, {}) == {}

    def test_and_single(self):
        """AND with single query returns that query."""
        q = {"patent_number": "10000000"}
        assert PatentsViewQuery.and_(q) == q
        assert PatentsViewQuery.and_({}, q) == q

    def test_and_multiple(self):
        """AND with multiple queries wraps them."""
        q1 = {"patent_number": "10000000"}
        q2 = {"_gte": {"patent_date": "2020-01-01"}}
        result = PatentsViewQuery.and_(q1, q2)
        assert result == {"_and": [q1, q2]}

    def test_or_empty(self):
        """OR with no queries returns empty."""
        assert PatentsViewQuery.or_() == {}

    def test_or_single(self):
        """OR with single query returns that query."""
        q = {"patent_number": "10000000"}
        assert PatentsViewQuery.or_(q) == q

    def test_or_multiple(self):
        """OR with multiple queries wraps them."""
        q1 = {"assignee_organization": "Google"}
        q2 = {"assignee_organization": "Microsoft"}
        result = PatentsViewQuery.or_(q1, q2)
        assert result == {"_or": [q1, q2]}

    def test_not_empty(self):
        """NOT with empty query returns empty."""
        assert PatentsViewQuery.not_({}) == {}

    def test_not_query(self):
        """NOT wraps a query."""
        q = {"patent_type": "design"}
        result = PatentsViewQuery.not_(q)
        assert result == {"_not": q}

    def test_complex_combination(self):
        """Complex nested combination."""
        # Find Google OR Microsoft patents in H04L63, excluding design patents
        google_or_ms = PatentsViewQuery.or_(
            {"_text_any": {"assignee_organization": "Google"}},
            {"_text_any": {"assignee_organization": "Microsoft"}},
        )
        cpc = {"_text_any": {"cpc_group_id": "H04L63"}}
        not_design = PatentsViewQuery.not_({"patent_type": "design"})

        result = PatentsViewQuery.and_(google_or_ms, cpc, not_design)
        assert result == {
            "_and": [
                {
                    "_or": [
                        {"_text_any": {"assignee_organization": "Google"}},
                        {"_text_any": {"assignee_organization": "Microsoft"}},
                    ]
                },
                {"_text_any": {"cpc_group_id": "H04L63"}},
                {"_not": {"patent_type": "design"}},
            ]
        }
