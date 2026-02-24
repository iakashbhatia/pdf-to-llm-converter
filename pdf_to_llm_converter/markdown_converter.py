"""Markdown converter for transforming extracted content to structured markdown."""

from __future__ import annotations

import re

from pdf_to_llm_converter.models import (
    Document,
    DocumentSection,
    ExtractedContent,
    PageClassification,
    PageContent,
    Table,
    TextBlock,
)


class MarkdownConverter:
    """Converts Document models to structured markdown and back."""

    def to_markdown(self, document: Document) -> str:
        """Convert Document model to structured markdown string."""
        parts: list[str] = []

        # Generate table of contents
        toc = self._generate_toc(document.sections)
        if toc:
            parts.append(toc)

        # Render pages with their content
        for page in document.pages:
            parts.append(f"<!-- page: {page.page_number} -->")

            # Find sections that start on this page
            sections_on_page = self._find_sections_on_page(
                document.sections, page.page_number
            )
            for section in sections_on_page:
                parts.append(f"<!-- section: {section.title} -->")
                parts.append(f"{'#' * section.level} {section.title}")
                if section.content:
                    parts.append(section.content)

            # Render page content from ExtractedContent
            content = page.content
            rendered_blocks = self._render_content(content)
            if rendered_blocks:
                parts.append(rendered_blocks)

        return "\n\n".join(parts) + "\n" if parts else ""

    def from_markdown(self, markdown_str: str) -> Document:
        """Parse structured markdown back into a Document model."""
        if not markdown_str.strip():
            return Document(sections=[], pages=[])

        # Strip TOC block
        content = self._strip_toc(markdown_str)

        # Split into page chunks by <!-- page: N --> comments
        page_chunks = self._split_by_pages(content)

        pages: list[PageContent] = []
        all_sections: list[DocumentSection] = []

        for page_number, chunk_text in page_chunks:
            sections_on_page, remaining_text = self._parse_sections_from_chunk(
                chunk_text, page_number
            )
            all_sections.extend(sections_on_page)

            # Parse ALL page text (including section body) into ExtractedContent
            # Strip section comments and headings, keep everything else
            full_page_text = self._strip_section_markers(chunk_text)
            extracted = self._parse_extracted_content(full_page_text)

            pages.append(
                PageContent(
                    page_number=page_number,
                    classification=PageClassification.NATIVE_TEXT,
                    content=extracted,
                    ocr_confidence=None,
                )
            )

        # Build section hierarchy and compute page ranges
        root_sections = self._build_section_hierarchy(all_sections)

        return Document(sections=root_sections, pages=pages)

    def _strip_toc(self, text: str) -> str:
        """Remove the <!-- toc -->...<!-- /toc --> block."""
        return re.sub(
            r"<!-- toc -->.*?<!-- /toc -->\s*",
            "",
            text,
            flags=re.DOTALL,
        )
    def _strip_section_markers(self, text: str) -> str:
        """Remove section comment lines from text, keeping everything else."""
        lines = text.split("\n")
        result: list[str] = []
        for line in lines:
            if re.match(r"^\s*<!-- section: .+? -->\s*$", line):
                continue
            result.append(line)
        return "\n".join(result)

    def _split_by_pages(self, text: str) -> list[tuple[int, str]]:
        """Split text into (page_number, chunk_text) pairs by page comments."""
        pattern = r"<!-- page: (\d+) -->"
        parts = re.split(pattern, text)
        # parts: [before_first_page, page_num_1, chunk_1, page_num_2, chunk_2, ...]
        result: list[tuple[int, str]] = []
        i = 1  # skip content before first page marker
        while i < len(parts) - 1:
            page_number = int(parts[i])
            chunk_text = parts[i + 1]
            result.append((page_number, chunk_text))
            i += 2
        return result

    def _parse_sections_from_chunk(
        self, chunk_text: str, page_number: int
    ) -> tuple[list[DocumentSection], str]:
        """Extract sections from a page chunk, return sections and remaining text."""
        sections: list[DocumentSection] = []
        remaining_lines: list[str] = []
        lines = chunk_text.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check for section comment
            section_match = re.match(r"^<!-- section: (.+?) -->$", line.strip())
            if section_match:
                section_title = section_match.group(1)
                i += 1
                # Next non-empty line should be the heading
                while i < len(lines) and not lines[i].strip():
                    i += 1

                level = 1
                section_content = ""
                if i < len(lines):
                    heading_match = re.match(r"^(#{1,6})\s+(.+)$", lines[i].strip())
                    if heading_match:
                        level = len(heading_match.group(1))
                        i += 1
                        # Collect section content until next section/page comment
                        content_lines: list[str] = []
                        while i < len(lines):
                            next_line = lines[i]
                            if re.match(
                                r"^<!-- (section:|page:)", next_line.strip()
                            ):
                                break
                            content_lines.append(next_line)
                            i += 1
                        section_content = "\n".join(content_lines).strip()

                sections.append(
                    DocumentSection(
                        title=section_title,
                        level=level,
                        content=section_content,
                        page_start=page_number,
                        page_end=page_number,
                        subsections=[],
                    )
                )
            else:
                remaining_lines.append(line)
                i += 1

        return sections, "\n".join(remaining_lines)

    def _parse_extracted_content(self, text: str) -> ExtractedContent:
        """Parse markdown text into ExtractedContent with blocks and tables."""
        text = text.strip()
        if not text:
            return ExtractedContent(
                body_text="",
                headers=[],
                footers=[],
                tables=[],
                reading_order_blocks=[],
            )

        blocks: list[TextBlock] = []
        tables: list[Table] = []
        default_bbox = (0.0, 0.0, 0.0, 0.0)

        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip empty lines
            if not line.strip():
                i += 1
                continue

            # Check for table (starts with |)
            if line.strip().startswith("|"):
                table_lines: list[str] = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1
                table = self._parse_table(table_lines)
                if table:
                    tables.append(table)
                continue

            # Check for list item
            list_match = re.match(r"^(\s*)- (.+)$", line)
            if list_match:
                indent = len(list_match.group(1))
                item_text = list_match.group(2)
                # Map indent to x-position: base_x=10, 30 units per level
                nesting = indent // 2
                x_pos = 10.0 + nesting * 30.0
                blocks.append(
                    TextBlock(
                        text=item_text,
                        bbox=(x_pos, 0.0, 0.0, 0.0),
                        block_type="list_item",
                    )
                )
                i += 1
                continue

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
            if heading_match:
                blocks.append(
                    TextBlock(
                        text=line.strip(),
                        bbox=default_bbox,
                        block_type="heading",
                    )
                )
                i += 1
                continue

            # Regular paragraph - collect consecutive non-empty, non-special lines
            para_lines: list[str] = []
            while i < len(lines):
                l = lines[i]
                if not l.strip():
                    break
                if l.strip().startswith("|"):
                    break
                if re.match(r"^(\s*)- ", l):
                    break
                if re.match(r"^#{1,6}\s+", l.strip()):
                    break
                para_lines.append(l.strip())
                i += 1

            if para_lines:
                blocks.append(
                    TextBlock(
                        text="\n".join(para_lines),
                        bbox=default_bbox,
                        block_type="paragraph",
                    )
                )

        body_text = "\n\n".join(
            b.text for b in blocks if b.block_type == "paragraph"
        )

        return ExtractedContent(
            body_text=body_text,
            headers=[],
            footers=[],
            tables=tables,
            reading_order_blocks=blocks,
        )

    def _parse_table(self, lines: list[str]) -> Table | None:
        """Parse markdown table lines into a Table object."""
        if len(lines) < 2:
            return None

        rows: list[list[str]] = []
        for i, line in enumerate(lines):
            # Skip separator line (| --- | --- |)
            cells = [c.strip() for c in line.strip("|").split("|")]
            if i == 1 and all(re.match(r"^-+$", c.strip()) for c in cells if c.strip()):
                continue
            rows.append(cells)

        return Table(rows=rows) if rows else None

    def _build_section_hierarchy(
        self, flat_sections: list[DocumentSection]
    ) -> list[DocumentSection]:
        """Build a hierarchical section tree from a flat list based on levels."""
        if not flat_sections:
            return []

        root: list[DocumentSection] = []
        stack: list[DocumentSection] = []

        for section in flat_sections:
            # Pop stack until we find a parent with a lower level
            while stack and stack[-1].level >= section.level:
                stack.pop()

            if stack:
                # This section is a subsection of the top of stack
                parent = stack[-1]
                parent.subsections.append(section)
                # Update parent's page_end
                if section.page_end > parent.page_end:
                    parent.page_end = section.page_end
            else:
                root.append(section)

            stack.append(section)

        return root


    def _generate_toc(self, sections: list[DocumentSection]) -> str:
        """Generate a table of contents block from sections."""
        entries = self._collect_toc_entries(sections)
        if not entries:
            return ""
        lines = ["<!-- toc -->"]
        for entry in entries:
            indent, title, page_start, page_end = entry
            anchor = self._slugify(title)
            prefix = "  " * indent
            lines.append(f"{prefix}- [{title}](#{anchor}) (p. {page_start}-{page_end})")
        lines.append("<!-- /toc -->")
        return "\n".join(lines)

    def _collect_toc_entries(
        self, sections: list[DocumentSection], depth: int = 0
    ) -> list[tuple[int, str, int, int]]:
        """Recursively collect TOC entries as (indent, title, page_start, page_end)."""
        entries: list[tuple[int, str, int, int]] = []
        for section in sections:
            entries.append((depth, section.title, section.page_start, section.page_end))
            entries.extend(self._collect_toc_entries(section.subsections, depth + 1))
        return entries

    def _find_sections_on_page(
        self, sections: list[DocumentSection], page_number: int
    ) -> list[DocumentSection]:
        """Find all sections (including subsections) that start on a given page."""
        result: list[DocumentSection] = []
        for section in sections:
            if section.page_start == page_number:
                result.append(section)
            result.extend(
                self._find_sections_on_page(section.subsections, page_number)
            )
        return result

    def _render_content(self, content: ExtractedContent) -> str:
        """Render ExtractedContent to markdown string."""
        parts: list[str] = []

        # Render reading_order_blocks if available (preserves document order)
        if content.reading_order_blocks:
            parts.append(self._render_blocks(content.reading_order_blocks))
        elif content.body_text:
            parts.append(content.body_text)

        # Render tables
        for table in content.tables:
            parts.append(self._render_table(table))

        return "\n\n".join(p for p in parts if p)

    def _render_blocks(self, blocks: list[TextBlock]) -> str:
        """Render a list of TextBlocks to markdown, handling different block types."""
        parts: list[str] = []
        list_items: list[TextBlock] = []

        for block in blocks:
            if block.block_type == "list_item":
                list_items.append(block)
            else:
                # Flush any accumulated list items first
                if list_items:
                    parts.append(self._render_list_items(list_items))
                    list_items = []

                if block.block_type == "heading":
                    # Headings from blocks - use level detection from text
                    parts.append(block.text)
                elif block.block_type == "paragraph":
                    parts.append(block.text)
                elif block.block_type == "table_cell":
                    # Table cells are handled via tables in ExtractedContent
                    parts.append(block.text)
                else:
                    parts.append(block.text)

        # Flush remaining list items
        if list_items:
            parts.append(self._render_list_items(list_items))

        return "\n\n".join(p for p in parts if p)

    def _render_list_items(self, items: list[TextBlock]) -> str:
        """Render list items with nesting based on indentation (bbox x-position)."""
        if not items:
            return ""

        lines: list[str] = []
        # Use the leftmost x-position as the base indent level
        base_x = min(item.bbox[0] for item in items)

        for item in items:
            # Estimate nesting level from horizontal offset
            indent_offset = item.bbox[0] - base_x
            # Assume ~30 units per indent level (typical PDF units)
            nesting_level = int(indent_offset / 30) if indent_offset > 15 else 0
            prefix = "  " * nesting_level + "- "
            lines.append(f"{prefix}{item.text}")

        return "\n".join(lines)

    def _render_table(self, table: Table) -> str:
        """Render a Table as markdown table syntax."""
        if not table.rows:
            return ""

        # First row is the header
        header = table.rows[0]
        col_count = len(header)

        # Build header row
        header_line = "| " + " | ".join(header) + " |"
        # Build separator
        separator = "| " + " | ".join("---" for _ in range(col_count)) + " |"

        lines = [header_line, separator]

        # Build data rows
        for row in table.rows[1:]:
            # Pad row to match column count if needed
            padded = row + [""] * (col_count - len(row))
            lines.append("| " + " | ".join(padded[:col_count]) + " |")

        return "\n".join(lines)

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a URL-friendly anchor slug."""
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")
