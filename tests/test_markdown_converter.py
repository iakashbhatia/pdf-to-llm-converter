"""Tests for MarkdownConverter.to_markdown()."""

from pdf_to_llm_converter.markdown_converter import MarkdownConverter
from pdf_to_llm_converter.models import (
    Document,
    DocumentSection,
    ExtractedContent,
    PageClassification,
    PageContent,
    Table,
    TextBlock,
)


def _empty_content() -> ExtractedContent:
    return ExtractedContent(
        body_text="",
        headers=[],
        footers=[],
        tables=[],
        reading_order_blocks=[],
    )


def _make_page(page_number: int, content: ExtractedContent | None = None) -> PageContent:
    return PageContent(
        page_number=page_number,
        classification=PageClassification.NATIVE_TEXT,
        content=content or _empty_content(),
        ocr_confidence=None,
    )


class TestTOCGeneration:
    """Requirement 5.7: Table of contents at document start."""

    def test_toc_lists_all_sections(self):
        sections = [
            DocumentSection("Introduction", 1, "", 1, 3),
            DocumentSection("Methods", 1, "", 4, 8),
        ]
        doc = Document(sections=sections, pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "<!-- toc -->" in md
        assert "<!-- /toc -->" in md
        assert "- [Introduction](#introduction) (p. 1-3)" in md
        assert "- [Methods](#methods) (p. 4-8)" in md

    def test_toc_includes_subsections_indented(self):
        sections = [
            DocumentSection(
                "Chapter 1", 1, "", 1, 10,
                subsections=[
                    DocumentSection("Section 1.1", 2, "", 1, 5),
                    DocumentSection("Section 1.2", 2, "", 6, 10),
                ],
            ),
        ]
        doc = Document(sections=sections, pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "- [Chapter 1](#chapter-1) (p. 1-10)" in md
        assert "  - [Section 1.1](#section-11) (p. 1-5)" in md
        assert "  - [Section 1.2](#section-12) (p. 6-10)" in md

    def test_empty_sections_no_toc(self):
        doc = Document(sections=[], pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "<!-- toc -->" not in md


class TestPageComments:
    """Requirement 5.5: Page number metadata comments."""

    def test_page_comments_present(self):
        doc = Document(
            sections=[],
            pages=[_make_page(1), _make_page(2), _make_page(3)],
        )
        md = MarkdownConverter().to_markdown(doc)
        assert "<!-- page: 1 -->" in md
        assert "<!-- page: 2 -->" in md
        assert "<!-- page: 3 -->" in md

    def test_page_comments_sequential(self):
        doc = Document(
            sections=[],
            pages=[_make_page(1), _make_page(2)],
        )
        md = MarkdownConverter().to_markdown(doc)
        idx1 = md.index("<!-- page: 1 -->")
        idx2 = md.index("<!-- page: 2 -->")
        assert idx1 < idx2


class TestSectionComments:
    """Requirement 5.6: Section reference metadata comments."""

    def test_section_comment_and_heading(self):
        sections = [DocumentSection("Overview", 1, "", 1, 1)]
        doc = Document(sections=sections, pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "<!-- section: Overview -->" in md
        assert "# Overview" in md

    def test_section_heading_level(self):
        sections = [DocumentSection("Sub Topic", 3, "", 1, 1)]
        doc = Document(sections=sections, pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "### Sub Topic" in md

    def test_section_with_content(self):
        sections = [DocumentSection("Intro", 1, "Some body text.", 1, 1)]
        doc = Document(sections=sections, pages=[_make_page(1)])
        md = MarkdownConverter().to_markdown(doc)
        assert "Some body text." in md


class TestHeadingRendering:
    """Requirement 5.2: Headings mapped to correct markdown levels."""

    def test_h1_through_h6(self):
        for level in range(1, 7):
            sections = [DocumentSection(f"Level {level}", level, "", 1, 1)]
            doc = Document(sections=sections, pages=[_make_page(1)])
            md = MarkdownConverter().to_markdown(doc)
            expected = "#" * level + f" Level {level}"
            assert expected in md


class TestTableRendering:
    """Requirement 5.3: Tables rendered in markdown table syntax."""

    def test_simple_table(self):
        table = Table(rows=[["Col A", "Col B"], ["val1", "val2"]])
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[table],
            reading_order_blocks=[],
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        assert "| Col A | Col B |" in md
        assert "| --- | --- |" in md
        assert "| val1 | val2 |" in md

    def test_table_preserves_row_count(self):
        table = Table(rows=[["H1", "H2"], ["r1c1", "r1c2"], ["r2c1", "r2c2"]])
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[table],
            reading_order_blocks=[],
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        # Header + separator + 2 data rows = 4 lines in the table
        table_lines = [l for l in md.split("\n") if l.startswith("|")]
        assert len(table_lines) == 4

    def test_empty_table(self):
        table = Table(rows=[])
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[table],
            reading_order_blocks=[],
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        # Empty table should not produce table syntax
        assert "|" not in md


class TestListRendering:
    """Requirement 5.4: Lists rendered with nesting."""

    def test_flat_list(self):
        blocks = [
            TextBlock("Item one", (10, 100, 200, 120), "list_item"),
            TextBlock("Item two", (10, 130, 200, 150), "list_item"),
        ]
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=blocks,
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        assert "- Item one" in md
        assert "- Item two" in md

    def test_nested_list(self):
        blocks = [
            TextBlock("Parent", (10, 100, 200, 120), "list_item"),
            TextBlock("Child", (50, 130, 200, 150), "list_item"),
        ]
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=blocks,
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        assert "- Parent" in md
        assert "  - Child" in md


class TestBodyText:
    """Requirement 5.1: Valid markdown output with body text."""

    def test_body_text_rendered(self):
        content = ExtractedContent(
            body_text="This is a paragraph.",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=[],
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        assert "This is a paragraph." in md

    def test_reading_order_blocks_preferred_over_body_text(self):
        blocks = [TextBlock("Block text", (0, 0, 100, 20), "paragraph")]
        content = ExtractedContent(
            body_text="Body text fallback",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=blocks,
        )
        doc = Document(sections=[], pages=[_make_page(1, content)])
        md = MarkdownConverter().to_markdown(doc)
        assert "Block text" in md
        # body_text is not used when reading_order_blocks are present
        assert "Body text fallback" not in md


class TestEmptyDocument:
    """Edge case: empty document."""

    def test_empty_document(self):
        doc = Document(sections=[], pages=[])
        md = MarkdownConverter().to_markdown(doc)
        assert md == ""


# --- Tests for from_markdown() ---


class TestFromMarkdownEmpty:
    """Edge case: empty/blank markdown input."""

    def test_empty_string(self):
        doc = MarkdownConverter().from_markdown("")
        assert doc.sections == []
        assert doc.pages == []

    def test_whitespace_only(self):
        doc = MarkdownConverter().from_markdown("   \n\n  ")
        assert doc.sections == []
        assert doc.pages == []


class TestFromMarkdownPages:
    """Requirement 6.2: Parse page comments to reconstruct pages."""

    def test_single_page(self):
        md = "<!-- page: 1 -->\n\nSome text.\n"
        doc = MarkdownConverter().from_markdown(md)
        assert len(doc.pages) == 1
        assert doc.pages[0].page_number == 1

    def test_multiple_pages(self):
        md = (
            "<!-- page: 1 -->\n\nPage one text.\n\n"
            "<!-- page: 2 -->\n\nPage two text.\n\n"
            "<!-- page: 3 -->\n\nPage three text.\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        assert len(doc.pages) == 3
        assert [p.page_number for p in doc.pages] == [1, 2, 3]

    def test_page_default_classification(self):
        md = "<!-- page: 1 -->\n\nText.\n"
        doc = MarkdownConverter().from_markdown(md)
        assert doc.pages[0].classification == PageClassification.NATIVE_TEXT

    def test_page_default_ocr_confidence(self):
        md = "<!-- page: 1 -->\n\nText.\n"
        doc = MarkdownConverter().from_markdown(md)
        assert doc.pages[0].ocr_confidence is None


class TestFromMarkdownSections:
    """Requirement 6.2: Parse section comments and headings."""

    def test_single_section(self):
        md = (
            "<!-- page: 1 -->\n"
            "<!-- section: Introduction -->\n"
            "# Introduction\n\n"
            "Body text here.\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        assert len(doc.sections) == 1
        assert doc.sections[0].title == "Introduction"
        assert doc.sections[0].level == 1
        assert doc.sections[0].page_start == 1

    def test_section_heading_levels(self):
        md = (
            "<!-- page: 1 -->\n"
            "<!-- section: Top -->\n"
            "# Top\n\n"
            "<!-- section: Sub -->\n"
            "## Sub\n\n"
            "Sub content.\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        # Sub should be nested under Top
        assert len(doc.sections) == 1
        assert doc.sections[0].title == "Top"
        assert len(doc.sections[0].subsections) == 1
        assert doc.sections[0].subsections[0].title == "Sub"
        assert doc.sections[0].subsections[0].level == 2

    def test_section_content_preserved(self):
        md = (
            "<!-- page: 1 -->\n"
            "<!-- section: Intro -->\n"
            "# Intro\n\n"
            "Some body text.\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        assert "Some body text." in doc.sections[0].content

    def test_multiple_top_level_sections(self):
        md = (
            "<!-- page: 1 -->\n"
            "<!-- section: A -->\n"
            "# A\n\n"
            "<!-- page: 2 -->\n"
            "<!-- section: B -->\n"
            "# B\n\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        assert len(doc.sections) == 2
        assert doc.sections[0].title == "A"
        assert doc.sections[1].title == "B"


class TestFromMarkdownTables:
    """Requirement 6.2: Parse markdown tables back to Table objects."""

    def test_simple_table(self):
        md = (
            "<!-- page: 1 -->\n\n"
            "| Col A | Col B |\n"
            "| --- | --- |\n"
            "| val1 | val2 |\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        tables = doc.pages[0].content.tables
        assert len(tables) == 1
        assert tables[0].rows[0] == ["Col A", "Col B"]
        assert tables[0].rows[1] == ["val1", "val2"]

    def test_table_separator_stripped(self):
        md = (
            "<!-- page: 1 -->\n\n"
            "| H1 | H2 |\n"
            "| --- | --- |\n"
            "| r1 | r2 |\n"
            "| r3 | r4 |\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        table = doc.pages[0].content.tables[0]
        # Should have header + 2 data rows (separator stripped)
        assert len(table.rows) == 3


class TestFromMarkdownLists:
    """Requirement 6.2: Parse list items back to TextBlock objects."""

    def test_flat_list(self):
        md = (
            "<!-- page: 1 -->\n\n"
            "- Item one\n"
            "- Item two\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        blocks = doc.pages[0].content.reading_order_blocks
        list_blocks = [b for b in blocks if b.block_type == "list_item"]
        assert len(list_blocks) == 2
        assert list_blocks[0].text == "Item one"
        assert list_blocks[1].text == "Item two"

    def test_nested_list(self):
        md = (
            "<!-- page: 1 -->\n\n"
            "- Parent\n"
            "  - Child\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        blocks = doc.pages[0].content.reading_order_blocks
        list_blocks = [b for b in blocks if b.block_type == "list_item"]
        assert len(list_blocks) == 2
        # Child should have a larger x-position than parent
        assert list_blocks[1].bbox[0] > list_blocks[0].bbox[0]


class TestFromMarkdownParagraphs:
    """Requirement 6.2: Parse regular paragraphs."""

    def test_paragraph_block(self):
        md = "<!-- page: 1 -->\n\nThis is a paragraph.\n"
        doc = MarkdownConverter().from_markdown(md)
        blocks = doc.pages[0].content.reading_order_blocks
        para_blocks = [b for b in blocks if b.block_type == "paragraph"]
        assert len(para_blocks) == 1
        assert para_blocks[0].text == "This is a paragraph."

    def test_body_text_from_paragraphs(self):
        md = "<!-- page: 1 -->\n\nFirst paragraph.\n\nSecond paragraph.\n"
        doc = MarkdownConverter().from_markdown(md)
        assert "First paragraph." in doc.pages[0].content.body_text
        assert "Second paragraph." in doc.pages[0].content.body_text


class TestFromMarkdownTocStripped:
    """Requirement 6.2: TOC block is stripped during parsing."""

    def test_toc_stripped(self):
        md = (
            "<!-- toc -->\n"
            "- [Intro](#intro) (p. 1-1)\n"
            "<!-- /toc -->\n\n"
            "<!-- page: 1 -->\n"
            "<!-- section: Intro -->\n"
            "# Intro\n\n"
            "Body.\n"
        )
        doc = MarkdownConverter().from_markdown(md)
        assert len(doc.pages) == 1
        assert len(doc.sections) == 1
        assert doc.sections[0].title == "Intro"


class TestFromMarkdownRoundTrip:
    """Requirement 6.3: Serialization round-trip produces equivalent model."""

    def test_basic_round_trip(self):
        sections = [
            DocumentSection("Introduction", 1, "Intro text.", 1, 1),
        ]
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[Table(rows=[["A", "B"], ["1", "2"]])],
            reading_order_blocks=[
                TextBlock("A paragraph.", (0, 0, 0, 0), "paragraph"),
            ],
        )
        original = Document(sections=sections, pages=[_make_page(1, content)])

        converter = MarkdownConverter()
        md = converter.to_markdown(original)
        restored = converter.from_markdown(md)

        # Sections preserved
        assert len(restored.sections) == 1
        assert restored.sections[0].title == "Introduction"
        assert restored.sections[0].level == 1

        # Pages preserved
        assert len(restored.pages) == 1
        assert restored.pages[0].page_number == 1

        # Table preserved
        assert len(restored.pages[0].content.tables) == 1
        assert restored.pages[0].content.tables[0].rows[0] == ["A", "B"]
        assert restored.pages[0].content.tables[0].rows[1] == ["1", "2"]


# ---------------------------------------------------------------------------
# Feature: pdf-to-llm-converter, Property 7: Markdown renders all content types correctly
# Validates: Requirements 5.1, 5.2, 5.3, 5.4
# ---------------------------------------------------------------------------

import re

from hypothesis import given, settings
from hypothesis import strategies as st


# -- Hypothesis strategies for generating Document models --------------------

_heading_level_st = st.integers(min_value=1, max_value=6)

# Printable text without pipe characters (which break table cells) and without
# leading '#' (which could be confused with headings).  Also avoid newlines.
_cell_text_st = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Zs"),
        blacklist_characters="|#\n\r",
    ),
    min_size=1,
    max_size=20,
).map(str.strip).filter(lambda s: len(s) > 0)

_section_title_st = _cell_text_st

_table_st = st.integers(min_value=1, max_value=6).flatmap(
    lambda cols: st.integers(min_value=1, max_value=8).flatmap(
        lambda rows: st.lists(
            st.lists(_cell_text_st, min_size=cols, max_size=cols),
            min_size=rows,
            max_size=rows,
        ).map(Table)
    )
)

# List items: generate a flat list of items at nesting level 0, or nested
# items at levels 0-3.  Nesting is encoded via bbox x-position.
_INDENT_UNIT = 30.0  # must match the 30-unit assumption in _render_list_items

_list_item_st = st.tuples(
    _cell_text_st,
    st.integers(min_value=0, max_value=3),  # nesting level
).map(
    lambda t: TextBlock(
        text=t[0],
        bbox=(t[1] * _INDENT_UNIT, 0.0, 100.0, 10.0),
        block_type="list_item",
    )
)


@st.composite
def _document_with_content(draw):
    """Generate a Document with headings, at least one table, and list items."""
    # Generate 1-3 sections (headings)
    num_sections = draw(st.integers(min_value=1, max_value=3))
    sections = []
    for _ in range(num_sections):
        level = draw(_heading_level_st)
        title = draw(_section_title_st)
        sections.append(
            DocumentSection(
                title=title, level=level, content="", page_start=1, page_end=1
            )
        )

    # Generate 1-3 tables
    num_tables = draw(st.integers(min_value=1, max_value=3))
    tables = [draw(_table_st) for _ in range(num_tables)]

    # Generate 1-5 list items
    num_items = draw(st.integers(min_value=1, max_value=5))
    list_items = [draw(_list_item_st) for _ in range(num_items)]

    content = ExtractedContent(
        body_text="",
        headers=[],
        footers=[],
        tables=tables,
        reading_order_blocks=list_items,
    )

    page = PageContent(
        page_number=1,
        classification=PageClassification.NATIVE_TEXT,
        content=content,
        ocr_confidence=None,
    )

    return Document(sections=sections, pages=[page]), sections, tables, list_items


class TestProperty7MarkdownRendersAllContentTypes:
    """Property 7: Markdown renders all content types correctly.

    **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

    For any Document containing headings, tables, and lists, the markdown
    output should:
    - map each heading of level L to a line starting with exactly L '#' chars
    - render each table preserving the original row count and column count
    - render each list preserving nesting depth and item count
    """

    @given(data=_document_with_content())
    @settings(max_examples=100)
    def test_headings_rendered_with_correct_level(self, data):
        """Each section heading of level L produces a line with exactly L '#' chars.

        **Validates: Requirements 5.1, 5.2**
        """
        document, sections, _tables, _items = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        md_lines = md.split("\n")

        for section in sections:
            expected_line = "#" * section.level + " " + section.title
            # There must be at least one line matching exactly this heading
            matching = [l for l in md_lines if l == expected_line]
            assert len(matching) >= 1, (
                f"Expected heading '{expected_line}' not found in markdown output"
            )
            # Verify the heading line starts with exactly L '#' chars (not more)
            for line in matching:
                hashes = len(line) - len(line.lstrip("#"))
                assert hashes == section.level, (
                    f"Heading '{section.title}' has {hashes} '#' chars, expected {section.level}"
                )

    @given(data=_document_with_content())
    @settings(max_examples=100)
    def test_tables_preserve_row_and_column_count(self, data):
        """Each table preserves the original row count and column count.

        **Validates: Requirements 5.1, 5.3**
        """
        document, _sections, tables, _items = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        for table in tables:
            if not table.rows:
                continue

            expected_cols = len(table.rows[0])
            # Total rendered rows = header + separator + data rows = len(rows) + 1
            expected_data_rows = len(table.rows)

            # Find all markdown table rows (lines starting with '|')
            # Each table in the output has: header | sep | data rows
            # We verify each cell from the original table appears in the output
            # and that the column count is preserved.

            # Check header cells are present
            header = table.rows[0]
            header_line = "| " + " | ".join(header) + " |"
            assert header_line in md, (
                f"Table header '{header_line}' not found in markdown"
            )

            # Check data rows are present
            for row in table.rows[1:]:
                padded = row + [""] * (expected_cols - len(row))
                row_line = "| " + " | ".join(padded[:expected_cols]) + " |"
                assert row_line in md, (
                    f"Table row '{row_line}' not found in markdown"
                )

            # Verify column count via separator line
            separator = "| " + " | ".join("---" for _ in range(expected_cols)) + " |"
            assert separator in md, (
                f"Table separator '{separator}' not found in markdown"
            )

    @given(data=_document_with_content())
    @settings(max_examples=100)
    def test_lists_preserve_item_count_and_nesting(self, data):
        """Each list preserves nesting depth and item count.

        **Validates: Requirements 5.1, 5.4**
        """
        document, _sections, _tables, list_items = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        # Strip the TOC block before counting list items, since TOC also uses '- '
        toc_pattern = re.compile(r"<!-- toc -->.*?<!-- /toc -->", re.DOTALL)
        md_no_toc = toc_pattern.sub("", md)

        # Count list item lines in the output (lines matching '- ' prefix)
        md_lines = md_no_toc.split("\n")
        list_lines = [line for line in md_lines if re.match(r"^\s*- ", line)]

        # Item count must match
        assert len(list_lines) == len(list_items), (
            f"Expected {len(list_items)} list items, found {len(list_lines)}"
        )

        # Verify each item's text appears and nesting is correct
        base_x = min(item.bbox[0] for item in list_items)
        for item in list_items:
            indent_offset = item.bbox[0] - base_x
            expected_nesting = int(indent_offset / 30) if indent_offset > 15 else 0
            expected_prefix = "  " * expected_nesting + "- "
            expected_line = expected_prefix + item.text
            assert expected_line in md_no_toc, (
                f"Expected list line '{expected_line}' not found in markdown"
            )


# ---------------------------------------------------------------------------
# Feature: pdf-to-llm-converter, Property 8: Markdown includes correct page and section metadata
# Validates: Requirements 5.5, 5.6
# ---------------------------------------------------------------------------

# Strategy: simple alphanumeric section titles (no characters that break comment syntax)
_alpha_title_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=15,
).filter(lambda s: len(s.strip()) > 0)


@st.composite
def _document_with_pages_and_sections(draw):
    """Generate a Document with P pages and S sections for metadata testing.

    Each section's page_start is set to a valid page number so that
    _find_sections_on_page will place it on the correct page.
    """
    num_pages = draw(st.integers(min_value=1, max_value=5))

    pages = []
    for i in range(1, num_pages + 1):
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=[],
        )
        pages.append(
            PageContent(
                page_number=i,
                classification=PageClassification.NATIVE_TEXT,
                content=content,
                ocr_confidence=None,
            )
        )

    # Generate 0-4 sections, each assigned to a valid page
    num_sections = draw(st.integers(min_value=0, max_value=4))
    sections = []
    for _ in range(num_sections):
        title = draw(_alpha_title_st)
        level = draw(st.integers(min_value=1, max_value=6))
        page_start = draw(st.integers(min_value=1, max_value=num_pages))
        page_end = draw(st.integers(min_value=page_start, max_value=num_pages))
        sections.append(
            DocumentSection(
                title=title,
                level=level,
                content="",
                page_start=page_start,
                page_end=page_end,
                subsections=[],
            )
        )

    document = Document(sections=sections, pages=pages)
    return document, num_pages, sections


class TestProperty8MarkdownMetadataComments:
    """Property 8: Markdown includes correct page and section metadata.

    **Validates: Requirements 5.5, 5.6**

    For any Document with P pages and S sections, the markdown output should
    contain exactly P `<!-- page: N -->` comments with correct sequential page
    numbers, and exactly S `<!-- section: TITLE -->` comments matching the
    section titles.
    """

    @given(data=_document_with_pages_and_sections())
    @settings(max_examples=100)
    def test_page_comments_count_and_sequence(self, data):
        """Exactly P page comments exist with correct sequential page numbers.

        **Validates: Requirements 5.5**
        """
        document, num_pages, _sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        page_comments = re.findall(r"<!-- page: (\d+) -->", md)
        page_numbers = [int(n) for n in page_comments]

        # Exactly P page comments
        assert len(page_numbers) == num_pages, (
            f"Expected {num_pages} page comments, found {len(page_numbers)}"
        )

        # Sequential page numbers 1..P
        assert page_numbers == list(range(1, num_pages + 1)), (
            f"Page numbers {page_numbers} are not sequential 1..{num_pages}"
        )

    @given(data=_document_with_pages_and_sections())
    @settings(max_examples=100)
    def test_section_comments_match_titles(self, data):
        """Exactly S section comments exist matching the section titles.

        **Validates: Requirements 5.6**
        """
        document, _num_pages, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        section_comments = re.findall(r"<!-- section: (.+?) -->", md)

        # Exactly S section comments
        assert len(section_comments) == len(sections), (
            f"Expected {len(sections)} section comments, found {len(section_comments)}"
        )

        # Sections are rendered in page order (by page_start), so compare
        # against the titles sorted by the page they start on.  Within the
        # same page, _find_sections_on_page preserves the original list order.
        expected_titles = [s.title for s in sorted(sections, key=lambda s: s.page_start)]
        assert section_comments == expected_titles, (
            f"Section comments {section_comments} do not match expected {expected_titles}"
        )


# ---------------------------------------------------------------------------
# Feature: pdf-to-llm-converter, Property 9: Table of contents lists all sections
# Validates: Requirements 5.7
# ---------------------------------------------------------------------------


@st.composite
def _document_with_sections_for_toc(draw):
    """Generate a Document with 1+ sections (possibly with subsections) for TOC testing.

    Uses simple alphanumeric titles to avoid regex issues.
    """
    num_pages = draw(st.integers(min_value=1, max_value=5))

    pages = []
    for i in range(1, num_pages + 1):
        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=[],
            reading_order_blocks=[],
        )
        pages.append(
            PageContent(
                page_number=i,
                classification=PageClassification.NATIVE_TEXT,
                content=content,
                ocr_confidence=None,
            )
        )

    # Generate 1-4 top-level sections
    num_sections = draw(st.integers(min_value=1, max_value=4))
    sections = []
    for _ in range(num_sections):
        title = draw(_alpha_title_st)
        page_start = draw(st.integers(min_value=1, max_value=num_pages))
        page_end = draw(st.integers(min_value=page_start, max_value=num_pages))

        # Optionally add 0-2 subsections
        num_subsections = draw(st.integers(min_value=0, max_value=2))
        subsections = []
        for _ in range(num_subsections):
            sub_title = draw(_alpha_title_st)
            sub_start = draw(st.integers(min_value=page_start, max_value=page_end))
            sub_end = draw(st.integers(min_value=sub_start, max_value=page_end))
            subsections.append(
                DocumentSection(
                    title=sub_title,
                    level=2,
                    content="",
                    page_start=sub_start,
                    page_end=sub_end,
                    subsections=[],
                )
            )

        sections.append(
            DocumentSection(
                title=title,
                level=1,
                content="",
                page_start=page_start,
                page_end=page_end,
                subsections=subsections,
            )
        )

    document = Document(sections=sections, pages=pages)
    return document, sections


def _flatten_sections(sections: list[DocumentSection]) -> list[DocumentSection]:
    """Recursively flatten sections in document order (pre-order traversal)."""
    result: list[DocumentSection] = []
    for section in sections:
        result.append(section)
        result.extend(_flatten_sections(section.subsections))
    return result


class TestProperty9TOCCompleteness:
    """Property 9: Table of contents lists all sections.

    **Validates: Requirements 5.7**

    For any Document with sections, the generated table of contents should
    contain one entry per section, each entry including the section title
    and page reference, in document order.
    """

    @given(data=_document_with_sections_for_toc())
    @settings(max_examples=100)
    def test_toc_block_exists(self, data):
        """TOC block markers are present when sections exist.

        **Validates: Requirements 5.7**
        """
        document, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        assert "<!-- toc -->" in md, "TOC opening marker not found"
        assert "<!-- /toc -->" in md, "TOC closing marker not found"

        # TOC opening must come before closing
        toc_start = md.index("<!-- toc -->")
        toc_end = md.index("<!-- /toc -->")
        assert toc_start < toc_end, "TOC markers are in wrong order"

    @given(data=_document_with_sections_for_toc())
    @settings(max_examples=100)
    def test_toc_contains_all_section_titles(self, data):
        """Each section title (including subsections) appears in the TOC.

        **Validates: Requirements 5.7**
        """
        document, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        # Extract the TOC block
        toc_start = md.index("<!-- toc -->")
        toc_end = md.index("<!-- /toc -->")
        toc_block = md[toc_start:toc_end]

        all_sections = _flatten_sections(sections)
        for section in all_sections:
            assert f"[{section.title}]" in toc_block, (
                f"Section title '{section.title}' not found in TOC block"
            )

    @given(data=_document_with_sections_for_toc())
    @settings(max_examples=100)
    def test_toc_contains_page_references(self, data):
        """Each section's page reference appears in the TOC.

        **Validates: Requirements 5.7**
        """
        document, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        toc_start = md.index("<!-- toc -->")
        toc_end = md.index("<!-- /toc -->")
        toc_block = md[toc_start:toc_end]

        all_sections = _flatten_sections(sections)
        for section in all_sections:
            page_ref = f"(p. {section.page_start}-{section.page_end})"
            assert page_ref in toc_block, (
                f"Page reference '{page_ref}' for section '{section.title}' not found in TOC"
            )

    @given(data=_document_with_sections_for_toc())
    @settings(max_examples=100)
    def test_toc_entries_in_document_order(self, data):
        """TOC entries appear in document order (pre-order traversal of sections).

        **Validates: Requirements 5.7**
        """
        document, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        toc_start = md.index("<!-- toc -->")
        toc_end = md.index("<!-- /toc -->")
        toc_block = md[toc_start:toc_end]

        # Extract titles from TOC entries using the link pattern [Title](#anchor)
        toc_titles = re.findall(r"\[([^\]]+)\]\(#[^)]+\)", toc_block)

        # Expected order: pre-order traversal of sections tree
        all_sections = _flatten_sections(sections)
        expected_titles = [s.title for s in all_sections]

        assert toc_titles == expected_titles, (
            f"TOC order {toc_titles} does not match expected document order {expected_titles}"
        )

    @given(data=_document_with_sections_for_toc())
    @settings(max_examples=100)
    def test_toc_entry_count_matches_section_count(self, data):
        """TOC has exactly one entry per section (including subsections).

        **Validates: Requirements 5.7**
        """
        document, sections = data
        converter = MarkdownConverter()
        md = converter.to_markdown(document)

        toc_start = md.index("<!-- toc -->")
        toc_end = md.index("<!-- /toc -->")
        toc_block = md[toc_start:toc_end]

        # Count TOC entries by matching the link pattern
        toc_entries = re.findall(r"\[([^\]]+)\]\(#[^)]+\)", toc_block)

        all_sections = _flatten_sections(sections)
        assert len(toc_entries) == len(all_sections), (
            f"Expected {len(all_sections)} TOC entries, found {len(toc_entries)}"
        )


# ---------------------------------------------------------------------------
# Feature: pdf-to-llm-converter, Property 10: Document model serialization round-trip
# Validates: Requirements 6.1, 6.2, 6.3
# ---------------------------------------------------------------------------


@st.composite
def _roundtrip_list_item_st(draw):
    """Generate a list item with x-position that survives round-trip.

    from_markdown maps indent to x_pos = 10.0 + nesting * 30.0, so we
    generate items at those exact positions to ensure round-trip fidelity.
    """
    text = draw(_cell_text_st)
    nesting = draw(st.integers(min_value=0, max_value=3))
    x_pos = 10.0 + nesting * 30.0
    return TextBlock(text=text, bbox=(x_pos, 0.0, 0.0, 0.0), block_type="list_item")


@st.composite
def _roundtrip_paragraph_st(draw):
    """Generate a paragraph TextBlock that survives round-trip."""
    text = draw(_cell_text_st)
    return TextBlock(text=text, bbox=(0.0, 0.0, 0.0, 0.0), block_type="paragraph")


@st.composite
def _roundtrip_document(draw):
    """Generate a Document that can cleanly round-trip through to_markdown/from_markdown.

    Constraints for clean round-trip:
    - Section titles are simple alphanumeric (no special chars)
    - Table cells have no pipe chars or newlines
    - List items use x-positions matching from_markdown's reconstruction
    - No headers/footers (not preserved in markdown)
    - Sections are assigned to valid pages
    - Each page has at most one section to avoid ordering ambiguity
    - Content blocks don't include headings (sections handle those)
    """
    num_pages = draw(st.integers(min_value=1, max_value=4))

    # Generate sections: 0 to num_pages sections, each on a distinct page
    available_pages = list(range(1, num_pages + 1))
    num_sections = draw(st.integers(min_value=0, max_value=min(num_pages, 3)))
    section_pages = sorted(draw(
        st.lists(
            st.sampled_from(available_pages),
            min_size=num_sections,
            max_size=num_sections,
            unique=True,
        )
    ))

    sections = []
    for page_num in section_pages:
        title = draw(_alpha_title_st)
        # Use level 1 for all top-level sections to avoid hierarchy rebuild issues
        sections.append(
            DocumentSection(
                title=title,
                level=1,
                content="",
                page_start=page_num,
                page_end=page_num,
                subsections=[],
            )
        )

    # Generate pages with content
    pages = []
    for i in range(1, num_pages + 1):
        # Decide what content this page has
        blocks: list[TextBlock] = []
        tables: list[Table] = []

        # Optionally add paragraphs (0-2)
        num_paras = draw(st.integers(min_value=0, max_value=2))
        for _ in range(num_paras):
            blocks.append(draw(_roundtrip_paragraph_st()))

        # Optionally add list items (0-3).
        # Always start with a level-0 item so that strip() in
        # _parse_extracted_content doesn't eat leading indentation.
        num_items = draw(st.integers(min_value=0, max_value=3))
        if num_items > 0:
            first_text = draw(_cell_text_st)
            blocks.append(
                TextBlock(
                    text=first_text,
                    bbox=(10.0, 0.0, 0.0, 0.0),
                    block_type="list_item",
                )
            )
            for _ in range(num_items - 1):
                blocks.append(draw(_roundtrip_list_item_st()))

        # Optionally add tables (0-2)
        num_tables = draw(st.integers(min_value=0, max_value=2))
        for _ in range(num_tables):
            tables.append(draw(_table_st))

        content = ExtractedContent(
            body_text="",
            headers=[],
            footers=[],
            tables=tables,
            reading_order_blocks=blocks,
        )

        pages.append(
            PageContent(
                page_number=i,
                classification=PageClassification.NATIVE_TEXT,
                content=content,
                ocr_confidence=None,
            )
        )

    document = Document(sections=sections, pages=pages)
    return document


class TestProperty10RoundTripSerialization:
    """Property 10: Document model serialization round-trip.

    # Feature: pdf-to-llm-converter, Property 10: Document model serialization round-trip
    # Validates: Requirements 6.1, 6.2, 6.3

    For any valid Document model object, serializing to markdown via
    to_markdown then parsing back via from_markdown should produce an
    equivalent Document model object.
    """

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_page_count(self, document):
        """Round-trip preserves the number of pages.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        assert len(restored.pages) == len(document.pages)

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_page_numbers(self, document):
        """Round-trip preserves page numbers in order.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        original_nums = [p.page_number for p in document.pages]
        restored_nums = [p.page_number for p in restored.pages]
        assert restored_nums == original_nums

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_section_count(self, document):
        """Round-trip preserves the number of top-level sections.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        assert len(restored.sections) == len(document.sections)

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_section_titles_and_levels(self, document):
        """Round-trip preserves section titles and heading levels.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        original_titles = [(s.title, s.level) for s in document.sections]
        restored_titles = [(s.title, s.level) for s in restored.sections]
        assert restored_titles == original_titles

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_table_structure(self, document):
        """Round-trip preserves table row and column structure per page.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        for orig_page, rest_page in zip(document.pages, restored.pages):
            orig_tables = [t for t in orig_page.content.tables if t.rows]
            rest_tables = rest_page.content.tables

            assert len(rest_tables) == len(orig_tables), (
                f"Page {orig_page.page_number}: expected {len(orig_tables)} "
                f"tables, got {len(rest_tables)}"
            )

            for orig_t, rest_t in zip(orig_tables, rest_tables):
                assert len(rest_t.rows) == len(orig_t.rows), (
                    f"Page {orig_page.page_number}: table row count mismatch"
                )
                for orig_row, rest_row in zip(orig_t.rows, rest_t.rows):
                    assert rest_row == orig_row, (
                        f"Page {orig_page.page_number}: table row mismatch "
                        f"{rest_row} != {orig_row}"
                    )

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_list_items(self, document):
        """Round-trip preserves list item text and relative nesting.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        for orig_page, rest_page in zip(document.pages, restored.pages):
            orig_items = [
                b for b in orig_page.content.reading_order_blocks
                if b.block_type == "list_item"
            ]
            rest_items = [
                b for b in rest_page.content.reading_order_blocks
                if b.block_type == "list_item"
            ]

            assert len(rest_items) == len(orig_items), (
                f"Page {orig_page.page_number}: expected {len(orig_items)} "
                f"list items, got {len(rest_items)}"
            )

            for orig_item, rest_item in zip(orig_items, rest_items):
                assert rest_item.text == orig_item.text, (
                    f"Page {orig_page.page_number}: list item text mismatch"
                )

            # Compare relative nesting levels rather than absolute x-positions,
            # since _render_list_items normalises to base_x = min(x) and
            # from_markdown reconstructs with a fixed base of 10.0.
            if orig_items:
                orig_base = min(it.bbox[0] for it in orig_items)
                rest_base = min(it.bbox[0] for it in rest_items)
                for orig_item, rest_item in zip(orig_items, rest_items):
                    orig_offset = orig_item.bbox[0] - orig_base
                    rest_offset = rest_item.bbox[0] - rest_base
                    assert rest_offset == orig_offset, (
                        f"Page {orig_page.page_number}: list item nesting "
                        f"offset mismatch {rest_offset} != {orig_offset}"
                    )

    @given(document=_roundtrip_document())
    @settings(max_examples=100)
    def test_round_trip_preserves_paragraphs(self, document):
        """Round-trip preserves paragraph text blocks.

        **Validates: Requirements 6.1, 6.2, 6.3**
        """
        converter = MarkdownConverter()
        md = converter.to_markdown(document)
        restored = converter.from_markdown(md)

        for orig_page, rest_page in zip(document.pages, restored.pages):
            orig_paras = [
                b for b in orig_page.content.reading_order_blocks
                if b.block_type == "paragraph"
            ]
            rest_paras = [
                b for b in rest_page.content.reading_order_blocks
                if b.block_type == "paragraph"
            ]

            assert len(rest_paras) == len(orig_paras), (
                f"Page {orig_page.page_number}: expected {len(orig_paras)} "
                f"paragraphs, got {len(rest_paras)}"
            )

            for orig_p, rest_p in zip(orig_paras, rest_paras):
                assert rest_p.text == orig_p.text, (
                    f"Page {orig_page.page_number}: paragraph text mismatch"
                )
