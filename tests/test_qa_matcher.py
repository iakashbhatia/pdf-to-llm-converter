"""Unit tests for QAMatcher."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from pdf_to_llm_converter.models import Document, DocumentSection, PageContent, ExtractedContent, TextBlock, Table, PageClassification
from pdf_to_llm_converter.qa_matcher import QAMatcher


@pytest.fixture(scope="module")
def matcher():
    """Shared matcher instance to avoid reloading the model per test."""
    return QAMatcher()


def _make_section(title: str, content: str, page_start: int = 1, page_end: int = 1, subsections=None) -> DocumentSection:
    return DocumentSection(
        title=title,
        level=1,
        content=content,
        page_start=page_start,
        page_end=page_end,
        subsections=subsections or [],
    )


class TestQAMatcherMatch:
    """Tests for QAMatcher.match()."""

    def test_empty_questions_returns_empty(self, matcher):
        sections = [_make_section("S1", "Some content")]
        result = matcher.match([], sections)
        assert result == []

    def test_empty_sections_flags_all_unmatched(self, matcher):
        result = matcher.match(["What is X?"], [])
        assert len(result) == 1
        assert result[0].is_unmatched is True
        assert result[0].matches == []

    def test_basic_matching_returns_results(self, matcher):
        sections = [
            _make_section("Python Overview", "Python is a high-level programming language used for web development, data science, and automation."),
            _make_section("Java Overview", "Java is a statically typed object-oriented programming language used in enterprise applications."),
            _make_section("Cooking Recipes", "This section contains recipes for pasta, pizza, and salads."),
        ]
        result = matcher.match(["What is Python?"], sections, top_n=2)
        assert len(result) == 1
        assert not result[0].is_unmatched
        assert len(result[0].matches) > 0
        # The top match should be the Python section
        assert result[0].matches[0].section_title == "Python Overview"

    def test_top_n_limits_matches(self, matcher):
        sections = [_make_section(f"Section {i}", f"Content about topic {i}") for i in range(10)]
        result = matcher.match(["Tell me about topic 1"], sections, top_n=2, min_similarity=0.0)
        assert len(result) == 1
        assert len(result[0].matches) <= 2

    def test_min_similarity_filters_low_scores(self, matcher):
        sections = [
            _make_section("Unrelated", "The quick brown fox jumps over the lazy dog near the river bank."),
        ]
        # Very high threshold should flag as unmatched
        result = matcher.match(["What is quantum computing?"], sections, min_similarity=0.99)
        assert len(result) == 1
        assert result[0].is_unmatched is True
        assert result[0].matches == []

    def test_match_result_fields_populated(self, matcher):
        sections = [
            _make_section("Legal Terms", "This section defines legal terms and conditions for the contract.", page_start=5, page_end=10),
        ]
        result = matcher.match(["What are the legal terms?"], sections, top_n=3, min_similarity=0.0)
        assert len(result) == 1
        match = result[0].matches[0]
        assert match.section_title == "Legal Terms"
        assert match.page_range == (5, 10)
        assert 0.0 <= match.similarity_score <= 1.0
        assert len(match.text_excerpt) > 0

    def test_text_excerpt_truncated_to_500_chars(self, matcher):
        long_content = "A" * 1000
        sections = [_make_section("Long Section", long_content)]
        result = matcher.match(["anything"], sections, top_n=1, min_similarity=0.0)
        assert len(result[0].matches) == 1
        assert len(result[0].matches[0].text_excerpt) == 500

    def test_matches_sorted_by_descending_similarity(self, matcher):
        sections = [
            _make_section("Exact Match", "What is machine learning and how does it work in practice?"),
            _make_section("Related", "Artificial intelligence and deep learning are subfields of computer science."),
            _make_section("Unrelated", "Cooking pasta requires boiling water and adding salt."),
        ]
        result = matcher.match(["What is machine learning?"], sections, top_n=3, min_similarity=0.0)
        scores = [m.similarity_score for m in result[0].matches]
        assert scores == sorted(scores, reverse=True)

    def test_multiple_questions(self, matcher):
        sections = [
            _make_section("Python", "Python is a programming language."),
            _make_section("Cooking", "Recipes for making bread and cakes."),
        ]
        result = matcher.match(
            ["What is Python?", "How to bake bread?"],
            sections,
            top_n=1,
            min_similarity=0.0,
        )
        assert len(result) == 2
        assert result[0].question == "What is Python?"
        assert result[1].question == "How to bake bread?"


class TestSplitIntoSections:
    """Tests for QAMatcher.split_into_sections()."""

    def _make_document(self, sections):
        return Document(sections=sections, pages=[])

    def test_flat_sections_returned_as_is(self):
        sections = [
            _make_section("A", "Content A"),
            _make_section("B", "Content B"),
        ]
        doc = self._make_document(sections)
        result = QAMatcher.split_into_sections(doc)
        assert len(result) == 2
        assert result[0].title == "A"
        assert result[1].title == "B"

    def test_nested_sections_flattened_to_leaves(self):
        child1 = _make_section("Child 1", "Child content 1")
        child2 = _make_section("Child 2", "Child content 2")
        parent = _make_section("Parent", "Parent content", subsections=[child1, child2])
        doc = self._make_document([parent])
        result = QAMatcher.split_into_sections(doc)
        assert len(result) == 2
        assert result[0].title == "Child 1"
        assert result[1].title == "Child 2"

    def test_empty_document_returns_empty(self):
        doc = self._make_document([])
        result = QAMatcher.split_into_sections(doc)
        assert result == []

    def test_deeply_nested_sections(self):
        leaf = _make_section("Leaf", "Leaf content")
        mid = _make_section("Mid", "Mid content", subsections=[leaf])
        top = _make_section("Top", "Top content", subsections=[mid])
        doc = self._make_document([top])
        result = QAMatcher.split_into_sections(doc)
        assert len(result) == 1
        assert result[0].title == "Leaf"

# Feature: pdf-to-llm-converter, Property 11: Similarity scores are bounded
# Validates: Requirements 7.3
class TestProperty11SimilarityScoreBounds:
    """Property 11: For any set of Q questions and S answer sections,
    the QA_Matcher should produce exactly Q × S similarity scores,
    each in the range [0.0, 1.0]."""

    @given(
        questions=st.lists(
            st.text(min_size=1, max_size=80, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))),
            min_size=1,
            max_size=3,
        ),
        num_sections=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_all_similarity_scores_bounded(self, matcher, questions, num_sections):
        """**Validates: Requirements 7.3**"""
        sections = [
            DocumentSection(
                title=f"Section {i}",
                level=1,
                content=f"Content for section number {i} with some text.",
                page_start=i,
                page_end=i,
                subsections=[],
            )
            for i in range(num_sections)
        ]

        results = matcher.match(
            questions=questions,
            answer_sections=sections,
            top_n=num_sections,  # equal to section count to get all matches
            min_similarity=-1.0,  # allow all scores through (cosine sim range is [-1, 1])
        )

        # Should get one QAMatch per question
        assert len(results) == len(questions)

        # Collect all similarity scores
        all_scores = []
        for qa_match in results:
            for match_result in qa_match.matches:
                all_scores.append(match_result.similarity_score)

        # Total scores should be Q × S (since min_similarity=-1.0 and top_n >= S)
        assert len(all_scores) == len(questions) * num_sections

        # Every score must be in [0.0, 1.0]
        for score in all_scores:
            assert 0.0 <= score <= 1.0, f"Score {score} out of bounds [0.0, 1.0]"


# Feature: pdf-to-llm-converter, Property 12: QA match results are ranked, bounded, and complete
# Validates: Requirements 7.4, 7.5
class TestProperty12MatchRankingAndCompleteness:
    """Property 12: For any QA match result with configured top_n = N,
    each question's matches should be sorted by descending similarity score,
    contain at most N entries, and each match should include a non-empty
    section_title, a valid page_range tuple, a similarity_score in [0, 1],
    and a non-empty text_excerpt."""

    @given(
        questions=st.lists(
            st.text(
                min_size=1,
                max_size=80,
                alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            ),
            min_size=1,
            max_size=3,
        ),
        num_sections=st.integers(min_value=1, max_value=4),
        top_n=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_matches_ranked_bounded_and_complete(self, matcher, questions, num_sections, top_n):
        """**Validates: Requirements 7.4, 7.5**"""
        sections = [
            DocumentSection(
                title=f"Section {i}",
                level=1,
                content=f"Content for section number {i} with some descriptive text.",
                page_start=i + 1,
                page_end=i + 3,
                subsections=[],
            )
            for i in range(num_sections)
        ]

        results = matcher.match(
            questions=questions,
            answer_sections=sections,
            top_n=top_n,
            min_similarity=0.0,
        )

        assert len(results) == len(questions)

        for qa_match in results:
            # Bounded: at most top_n matches
            assert len(qa_match.matches) <= top_n

            # Ranked: sorted by descending similarity score
            scores = [m.similarity_score for m in qa_match.matches]
            assert scores == sorted(scores, reverse=True), (
                f"Matches not sorted by descending score: {scores}"
            )

            for match_result in qa_match.matches:
                # Non-empty section_title
                assert len(match_result.section_title) > 0

                # Valid page_range tuple
                assert isinstance(match_result.page_range, tuple)
                assert len(match_result.page_range) == 2
                assert match_result.page_range[0] <= match_result.page_range[1]

                # Similarity score in [0, 1]
                assert 0.0 <= match_result.similarity_score <= 1.0

                # Non-empty text_excerpt
                assert len(match_result.text_excerpt) > 0


# Feature: pdf-to-llm-converter, Property 13: Unmatched questions are correctly flagged
# Validates: Requirements 7.6
class TestProperty13UnmatchedFlagging:
    """Property 13: For any question where all answer section similarity scores
    fall below the configured min_similarity threshold, the QAMatch result should
    have is_unmatched == True and an empty matches list."""

    @given(
        questions=st.lists(
            st.text(
                min_size=1,
                max_size=80,
                alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            ),
            min_size=1,
            max_size=3,
        ),
        num_sections=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_high_threshold_flags_all_unmatched(self, matcher, questions, num_sections):
        """With min_similarity=1.0, all questions should be flagged as unmatched
        since cosine similarity between arbitrary text rarely reaches exactly 1.0.

        **Validates: Requirements 7.6**"""
        sections = [
            DocumentSection(
                title=f"Section {i}",
                level=1,
                content=f"Content for section number {i} with some text.",
                page_start=i + 1,
                page_end=i + 1,
                subsections=[],
            )
            for i in range(num_sections)
        ]

        results = matcher.match(
            questions=questions,
            answer_sections=sections,
            top_n=num_sections,
            min_similarity=1.0,
        )

        assert len(results) == len(questions)

        for qa_match in results:
            assert qa_match.is_unmatched is True, (
                f"Question '{qa_match.question}' should be unmatched with min_similarity=1.0"
            )
            assert qa_match.matches == [], (
                f"Question '{qa_match.question}' should have empty matches with min_similarity=1.0"
            )

    @given(
        questions=st.lists(
            st.text(
                min_size=1,
                max_size=80,
                alphabet=st.characters(whitelist_categories=("L", "N", "Z")),
            ),
            min_size=1,
            max_size=3,
        ),
        num_sections=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_zero_threshold_flags_none_unmatched(self, matcher, questions, num_sections):
        """With min_similarity=0.0, no questions should be flagged as unmatched
        since all non-negative similarity scores pass the threshold.

        **Validates: Requirements 7.6**"""
        sections = [
            DocumentSection(
                title=f"Section {i}",
                level=1,
                content=f"Content for section number {i} with some text.",
                page_start=i + 1,
                page_end=i + 1,
                subsections=[],
            )
            for i in range(num_sections)
        ]

        results = matcher.match(
            questions=questions,
            answer_sections=sections,
            top_n=num_sections,
            min_similarity=0.0,
        )

        assert len(results) == len(questions)

        for qa_match in results:
            assert qa_match.is_unmatched is False, (
                f"Question '{qa_match.question}' should NOT be unmatched with min_similarity=0.0"
            )
            assert len(qa_match.matches) > 0, (
                f"Question '{qa_match.question}' should have matches with min_similarity=0.0"
            )

