#!/usr/bin/env python3
"""
Markdown to DITA Converter for Heretto Import

This script converts Jekyll-based Markdown documentation to DITA XML format,
preserving the content reuse structure using DITA conref (content references).

Key features:
- Converts Jekyll includes to DITA warehouse topics
- Uses conref for content reuse (similar to Jekyll includes)
- Creates appropriate DITA topic types (concept, task, reference)
- Generates a DITA map for navigation
- Handles code blocks, tables, lists, and other Markdown elements
- Optional inline mode: embeds include content directly (no external references)

Usage:
    python convert_to_dita.py [--input-dir PATH] [--output-dir PATH]
    python convert_to_dita.py --inline-includes   # Inline mode (no warehouse topics)
    python convert_to_dita.py --inline-includes --use-existing-images  # Keep existing images
"""

import os
import re
import sys
import argparse
import uuid
import base64
import zlib
import urllib.request
import urllib.error
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import html

# ============================================================================
# Configuration
# ============================================================================

@dataclass
class ConversionConfig:
    """Configuration for the DITA conversion process."""
    input_dir: Path = field(default_factory=lambda: Path("."))
    output_dir: Path = field(default_factory=lambda: Path("dita_output"))
    warehouse_dir: str = "warehouse"  # Directory for reusable content
    topics_dir: str = "topics"        # Directory for main topics
    maps_dir: str = "maps"            # Directory for DITA maps
    images_dir: str = "images"        # Directory for downloaded images
    inline_includes: bool = False     # If True, inline include content instead of conref
    skip_diagrams: bool = False       # If True, skip downloading Mermaid diagrams (faster for testing)
    use_existing_images: bool = False  # If True, keep existing images and only download missing ones

    # Filtering options for selective conversion
    distribution: str = ""            # Filter by distribution (e.g., "rhel", "debian")
    protocol: str = ""                # Filter by protocol (e.g., "iscsi", "nvme-tcp", "nfs")
    generate_section_maps: bool = False  # Generate per-distribution/protocol maps
    organize_by_section: bool = False    # Organize topics into subdirectories

    # DITA DOCTYPE declarations
    concept_doctype: str = '<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">'
    task_doctype: str = '<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">'
    reference_doctype: str = '<!DOCTYPE reference PUBLIC "-//OASIS//DTD DITA Reference//EN" "reference.dtd">'
    topic_doctype: str = '<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">'
    map_doctype: str = '<!DOCTYPE map PUBLIC "-//OASIS//DTD DITA Map//EN" "map.dtd">'


# ============================================================================
# Utility Functions
# ============================================================================

def sanitize_id(text: str) -> str:
    """Convert text to a valid DITA ID (XML NCName)."""
    # Remove or replace invalid characters
    result = re.sub(r'[^a-zA-Z0-9_-]', '_', text.lower())
    # Ensure it starts with a letter or underscore
    if result and not result[0].isalpha() and result[0] != '_':
        result = '_' + result
    # Remove consecutive underscores
    result = re.sub(r'_+', '_', result)
    return result.strip('_') or 'topic'


def escape_xml(text: str) -> str:
    """Escape text for XML content."""
    return html.escape(text, quote=False)


def escape_xml_attr(text: str) -> str:
    """Escape text for XML attributes."""
    return html.escape(text, quote=True)


def remove_non_ascii(text: str) -> str:
    """Remove non-ASCII characters, keeping common replacements."""
    # Replace common unicode characters with ASCII equivalents
    replacements = {
        '–': '-',  # en-dash
        '—': '-',  # em-dash
        ''': "'",  # smart single quote
        ''': "'",  # smart single quote
        '"': '"',  # smart double quote
        '"': '"',  # smart double quote
        '…': '...',  # ellipsis
        '•': '*',  # bullet
        '→': '->',  # arrow
        '←': '<-',  # arrow
        '⚠️': '[WARNING]',  # warning emoji
        '📖': '[INFO]',  # book emoji
        '✅': '[OK]',  # checkmark
        '❌': '[X]',  # X mark
        '📋': '[NOTE]',  # clipboard
        '📁': '[FOLDER]',  # folder
        '🔧': '[CONFIG]',  # wrench
        '💡': '[TIP]',  # lightbulb
        '🚀': '[START]',  # rocket
        '⏱️': '[TIME]',  # timer
        '🔒': '[SECURE]',  # lock
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    # Remove any remaining non-ASCII characters
    return text.encode('ascii', 'ignore').decode('ascii')


def remove_step_prefix(text: str) -> str:
    """Remove 'Step X:' prefix from text since DITA uses numbered lists."""
    # Match patterns like "Step 1:", "Step 2:", "Step 10:" etc.
    return re.sub(r'^Step\s+\d+[:\s]*', '', text, flags=re.IGNORECASE)


def generate_uuid() -> str:
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:8]


def collapse_consecutive_notes(lines: List[str]) -> List[str]:
    """Collapse consecutive <note> elements of the same type into one note."""
    if not lines:
        return lines

    result = []
    i = 0
    note_pattern = re.compile(r'^(\s*)<note type="(\w+)"><p>(.*?)</p></note>$')

    while i < len(lines):
        line = lines[i]
        match = note_pattern.match(line)

        if match:
            indent = match.group(1)
            note_type = match.group(2)
            contents = [match.group(3)]

            # Look ahead for consecutive notes of the same type
            j = i + 1
            while j < len(lines):
                next_match = note_pattern.match(lines[j])
                if next_match and next_match.group(2) == note_type:
                    contents.append(next_match.group(3))
                    j += 1
                else:
                    break

            if len(contents) > 1:
                # Collapse into one note with multiple paragraphs
                p_elements = '</p><p>'.join(contents)
                result.append(f'{indent}<note type="{note_type}"><p>{p_elements}</p></note>')
            else:
                result.append(line)

            i = j
        else:
            result.append(line)
            i += 1

    return result


def get_kroki_url(mermaid_code: str) -> str:
    """
    Generate a Kroki URL for Mermaid code.

    Kroki is a diagram rendering service that supports Mermaid.
    A white background init directive is prepended so PNGs are never transparent.
    """
    # Prepend Mermaid init to force a white background on every diagram
    bg_init = "%%{init: {'theme': 'default', 'themeVariables': {'background': '#ffffff', 'mainBkg': '#ffffff'}}}%%"
    code = bg_init + "\n" + mermaid_code.strip()

    # Kroki uses deflate compression + base64
    compressed = zlib.compress(code.encode('utf-8'), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode('ascii')

    return f"https://kroki.io/mermaid/png/{encoded}"


def download_mermaid_image(mermaid_code: str, images_dir: Path, source_context: str, diagram_num: int) -> str:
    """
    Download a Mermaid diagram as PNG from Kroki and save locally.

    Args:
        mermaid_code: The Mermaid diagram code
        images_dir: Directory to save images
        source_context: Human-readable source context (e.g., "rhel-nvme-tcp-quickstart")
        diagram_num: Diagram number within the source file

    Returns the relative path to the saved image file.
    Filename format: {source_context}-diagram-{num}.png
    Filename is stable even if diagram content changes.
    """
    code = mermaid_code.strip()

    # Filename based only on source file and diagram number (stable across content edits)
    filename = f"{source_context}-diagram-{diagram_num:02d}.png"
    filepath = images_dir / filename

    # Check if already downloaded (cache)
    if filepath.exists():
        return filename

    # Generate Kroki URL
    url = get_kroki_url(code)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'DITA-Converter/1.0'})
            with urllib.request.urlopen(req, timeout=60) as response:
                png_content = response.read()

            filepath.write_bytes(png_content)
            print(f"    Downloaded: {filename}")
            return filename

        except urllib.error.URLError as e:
            if attempt < max_retries:
                print(f"    Retry {attempt}/{max_retries - 1}: {e}")
            else:
                print(f"    Warning: Failed to download diagram after {max_retries} attempts: {e}")
                return f"{source_context}-diagram-{diagram_num:02d}-error.png"
        except Exception as e:
            if attempt < max_retries:
                print(f"    Retry {attempt}/{max_retries - 1}: {e}")
            else:
                print(f"    Warning: Error processing diagram after {max_retries} attempts: {e}")
                return f"{source_context}-diagram-{diagram_num:02d}-error.png"

    return f"{source_context}-diagram-{diagram_num:02d}-error.png"


# ============================================================================
# Markdown Parser
# ============================================================================

@dataclass
class MarkdownElement:
    """Represents a parsed Markdown element."""
    type: str  # heading, paragraph, code_block, list, table, include, etc.
    content: str
    level: int = 0  # For headings
    language: str = ""  # For code blocks
    items: List[str] = field(default_factory=list)  # For lists
    children: List['MarkdownElement'] = field(default_factory=list)


class MarkdownParser:
    """Parses Markdown content into structured elements."""

    def __init__(self):
        self.include_pattern = re.compile(r'\{%\s*include\s+([^\s%}]+)\s*%\}')
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.code_block_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        self.inline_code_pattern = re.compile(r'`([^`]+)`')
        self.bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
        self.link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
        self.list_item_pattern = re.compile(r'^(\s*)[-*]\s+(.+)$', re.MULTILINE)
        self.ordered_list_pattern = re.compile(r'^(\s*)\d+\.\s+(.+)$', re.MULTILINE)
        self.blockquote_pattern = re.compile(r'^>\s*(.+)$', re.MULTILINE)
        self.hr_pattern = re.compile(r'^---+\s*$', re.MULTILINE)
        self.table_pattern = re.compile(r'^\|(.+)\|$', re.MULTILINE)

    def parse(self, content: str) -> List[MarkdownElement]:
        """Parse Markdown content into elements."""
        elements = []

        # Remove YAML front matter
        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)

        # Process content line by line and block by block
        lines = content.split('\n')
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for Jekyll include
            include_match = self.include_pattern.search(line)
            if include_match:
                elements.append(MarkdownElement(
                    type='include',
                    content=include_match.group(1).strip()
                ))
                i += 1
                continue

            # Check for heading
            heading_match = self.heading_pattern.match(line)
            if heading_match:
                level = len(heading_match.group(1))
                elements.append(MarkdownElement(
                    type='heading',
                    content=heading_match.group(2).strip(),
                    level=level
                ))
                i += 1
                continue

            # Check for code block start
            if line.startswith('```'):
                lang = line[3:].strip()
                code_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith('```'):
                    code_lines.append(lines[i])
                    i += 1
                elements.append(MarkdownElement(
                    type='code_block',
                    content='\n'.join(code_lines),
                    language=lang
                ))
                i += 1  # Skip closing ```
                continue

            # Check for horizontal rule
            if self.hr_pattern.match(line):
                i += 1
                continue  # Skip HR in DITA

            # Check for blockquote
            if line.startswith('>'):
                quote_lines = []
                while i < len(lines) and lines[i].startswith('>'):
                    quote_lines.append(lines[i][1:].strip())
                    i += 1
                elements.append(MarkdownElement(
                    type='note',
                    content='\n'.join(quote_lines)
                ))
                continue

            # Check for unordered list
            list_match = self.list_item_pattern.match(line)
            if list_match:
                items = []
                while i < len(lines) and self.list_item_pattern.match(lines[i]):
                    match = self.list_item_pattern.match(lines[i])
                    items.append(match.group(2).strip())
                    i += 1
                elements.append(MarkdownElement(
                    type='unordered_list',
                    content='',
                    items=items
                ))
                continue

            # Check for ordered list (with nested unordered sublists support)
            ol_match = self.ordered_list_pattern.match(line)
            if ol_match:
                # Parse ordered list with potential nested bullet items
                ol_items = []  # List of tuples: (item_text, [nested_bullet_items])

                while i < len(lines):
                    current_line = lines[i]

                    # Check if this is an ordered list item (at root level, no indent)
                    ol_item_match = self.ordered_list_pattern.match(current_line)
                    if ol_item_match and ol_item_match.group(1) == '':  # No leading whitespace
                        item_text = ol_item_match.group(2).strip()
                        nested_items = []
                        i += 1

                        # Collect any nested unordered list items (indented bullets)
                        while i < len(lines):
                            nested_line = lines[i]
                            # Check for indented bullet (starts with spaces then - or *)
                            nested_match = re.match(r'^(\s+)[-*]\s+(.+)$', nested_line)
                            if nested_match and len(nested_match.group(1)) >= 2:
                                nested_items.append(nested_match.group(2).strip())
                                i += 1
                            elif nested_line.strip() == '':
                                # Empty line - check if next line continues the list
                                i += 1
                            else:
                                # Not a nested item, break out
                                break

                        ol_items.append((item_text, nested_items))
                    else:
                        # Not an ordered list item at root level, stop collecting
                        break

                if ol_items:
                    elements.append(MarkdownElement(
                        type='ordered_list_nested',
                        content='',
                        items=[item[0] for item in ol_items],  # Main item texts
                        children=[MarkdownElement(type='nested_ul', content='', items=item[1])
                                  for item in ol_items]  # Nested bullet lists
                    ))
                continue

            # Check for table
            if line.startswith('|'):
                table_lines = []
                while i < len(lines) and lines[i].startswith('|'):
                    # Skip separator lines (|---|---|)
                    if not re.match(r'^\|[-:\s|]+\|$', lines[i]):
                        table_lines.append(lines[i])
                    i += 1
                if table_lines:
                    elements.append(MarkdownElement(
                        type='table',
                        content='\n'.join(table_lines)
                    ))
                continue

            # Regular paragraph
            if line.strip():
                para_lines = [line]
                i += 1
                while i < len(lines) and lines[i].strip() and \
                      not lines[i].startswith('#') and \
                      not lines[i].startswith('```') and \
                      not lines[i].startswith('>') and \
                      not lines[i].startswith('|') and \
                      not self.list_item_pattern.match(lines[i]) and \
                      not self.include_pattern.search(lines[i]):
                    para_lines.append(lines[i])
                    i += 1
                elements.append(MarkdownElement(
                    type='paragraph',
                    content=' '.join(para_lines)
                ))
                continue

            i += 1

        return elements

    def convert_inline(self, text: str) -> str:
        """Convert inline Markdown formatting to DITA."""
        # Bold
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        # Italic
        text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
        # Inline code
        text = re.sub(r'`([^`]+)`', r'<codeph>\1</codeph>', text)
        # Links - handle internal .md links vs external links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', self._convert_link, text)
        return text

    def _convert_link(self, match) -> str:
        """Convert a Markdown link to DITA xref, fixing .md to .dita references."""
        link_text = match.group(1)
        link_href = match.group(2)

        # Check if it's an internal link (to .md or .html files in the project)
        if link_href.endswith('.md') or ('.md#' in link_href):
            # Internal markdown link - convert to .dita
            # Handle anchors
            if '#' in link_href:
                base_path, anchor = link_href.rsplit('#', 1)
                base_path = base_path.replace('.md', '.dita')
                new_href = f'{base_path}#{anchor}'
            else:
                new_href = link_href.replace('.md', '.dita')
            # Convert path structure for DITA output
            # Strip {{ site.baseurl }} and similar Jekyll templating
            new_href = re.sub(r'\{\{[^}]+\}\}', '', new_href)
            new_href = new_href.strip('/')
            # If it's a common/ path, point to topics directory
            if 'common/' in new_href or 'distributions/' in new_href:
                new_href = re.sub(r'^.*(common|distributions)/', r'../topics/', new_href)
            return f'<xref href="{escape_xml_attr(new_href)}" format="dita" scope="local">{link_text}</xref>'
        elif link_href.endswith('.html') or ('.html#' in link_href):
            # HTML link within the site - may need conversion
            # Strip Jekyll templating
            clean_href = re.sub(r'\{\{[^}]+\}\}', '', link_href).strip('/')
            # If it looks like an internal reference, try to convert to DITA
            if 'common/' in clean_href or 'glossary' in clean_href.lower():
                # Try to convert to DITA reference
                new_href = clean_href.replace('.html', '.dita')
                new_href = re.sub(r'^.*(common)/', r'../topics/', new_href)
                return f'<xref href="{escape_xml_attr(new_href)}" format="dita" scope="local">{link_text}</xref>'
            else:
                return f'<xref href="{escape_xml_attr(link_href)}" format="html" scope="external">{link_text}</xref>'
        else:
            # External link
            return f'<xref href="{escape_xml_attr(link_href)}" format="html" scope="external">{link_text}</xref>'


# ============================================================================
# DITA Generator
# ============================================================================

class DITAGenerator:
    """Generates DITA XML from parsed Markdown elements."""

    def __init__(self, config: ConversionConfig):
        self.config = config
        self.parser = MarkdownParser()
        self.warehouse_ids = {}  # Maps include paths to warehouse IDs
        self.images_dir = config.output_dir / config.images_dir
        self.diagram_counter = 0  # Counter for diagrams within current source file
        self._include_cache = {}  # Cache for resolved include content
        self._current_source_context = "unknown"  # Human-readable source context

    def set_source_context(self, rel_path: str):
        """Set the current source file context for human-readable diagram names.

        Converts path like 'distributions/rhel/nvme-tcp/QUICKSTART.md' to 'rhel-nvme-tcp-quickstart'.
        """
        # Reset per-file diagram counter
        self.diagram_counter = 0

        # Convert path to human-readable context
        # e.g., "distributions/rhel/nvme-tcp/QUICKSTART.md" -> "rhel-nvme-tcp-quickstart"
        parts = rel_path.replace('\\', '/').lower().split('/')
        # Remove 'distributions' prefix if present
        if parts and parts[0] == 'distributions':
            parts = parts[1:]
        # Remove .md extension from last part
        if parts:
            parts[-1] = parts[-1].replace('.md', '')
        # Join with hyphens
        self._current_source_context = '-'.join(parts)

    def _resolve_include(self, include_path: str) -> str:
        """Resolve and return the content of an include file."""
        if include_path in self._include_cache:
            return self._include_cache[include_path]

        includes_dir = self.config.input_dir / '_includes'
        include_file = includes_dir / include_path

        if include_file.exists():
            content = include_file.read_text(encoding='utf-8')
            self._include_cache[include_path] = content
            return content
        else:
            print(f"    Warning: Include file not found: {include_path}")
            return ""

    def _inline_include_to_dita(self, include_path: str, indent: str = '        ') -> str:
        """Convert an include file's content to inline DITA elements."""
        content = self._resolve_include(include_path)
        if not content:
            return f'{indent}<!-- Include not found: {include_path} -->'

        elements = self.parser.parse(content)
        output = []

        for elem in elements:
            if elem.type == 'heading':
                # Headings in included content become bold paragraphs (they're sections in context)
                output.append(f'{indent}<p><b>{escape_xml(elem.content)}</b></p>')
            elif elem.type == 'paragraph':
                output.append(f'{indent}<p>{self.parser.convert_inline(escape_xml(elem.content))}</p>')
            elif elem.type == 'code_block':
                if elem.language == 'mermaid':
                    image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=False)
                    output.append(f'{indent}{image_elem}')
                else:
                    output.append(f'{indent}<codeblock>{escape_xml(elem.content)}</codeblock>')
            elif elem.type == 'note':
                note_type = self._detect_note_type(elem.content)
                cleaned_content = self._strip_note_prefix(elem.content, note_type)
                output.append(f'{indent}<note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
            elif elem.type == 'unordered_list':
                output.append(self._generate_ul(elem.items, indent=indent))
            elif elem.type == 'ordered_list':
                output.append(self._generate_ol(elem.items, indent=indent))
            elif elem.type == 'ordered_list_nested':
                nested_items = [child.items for child in elem.children]
                output.append(self._generate_ol(elem.items, indent=indent, nested_items=nested_items))
            elif elem.type == 'table':
                output.append(self._generate_table(elem.content))
            elif elem.type == 'include':
                # Recursively inline nested includes
                output.append(self._inline_include_to_dita(elem.content, indent))

        return '\n'.join(output)

    def _handle_mermaid_diagram(self, mermaid_code: str, from_warehouse: bool = False) -> str:
        """
        Download a Mermaid diagram and return the DITA image element.

        Args:
            mermaid_code: The Mermaid diagram code
            from_warehouse: If True, use path for warehouse topics (../images/)
                           If False, use path for main topics (../images/)
        """
        self.diagram_counter += 1

        if self.config.skip_diagrams:
            # Return a placeholder comment for testing runs
            return f'<!-- Mermaid diagram {self.diagram_counter} (skipped) -->'

        filename = download_mermaid_image(
            mermaid_code,
            self.images_dir,
            self._current_source_context,
            self.diagram_counter
        )

        # Both warehouse and topics are one level deep, so path is the same
        image_path = f"../images/{filename}"

        # Include scope attribute for proper Heretto CCMS linking
        return f'<fig><image href="{escape_xml_attr(image_path)}" scope="local"><alt>Diagram</alt></image></fig>'

    def generate_warehouse_topic(self, include_path: str, content: str) -> str:
        """Generate a DITA warehouse topic from an include file.

        Uses <div> instead of <section> to allow conref in task topics,
        since <section> is not allowed in <taskbody>.
        """
        elements = self.parser.parse(content)
        topic_id = 'warehouse_' + sanitize_id(include_path.replace('/', '_').replace('.md', ''))
        div_id = sanitize_id(include_path.replace('/', '_').replace('.md', '')) + '_content'
        self.warehouse_ids[include_path] = topic_id

        body_content = self._elements_to_dita_warehouse(elements, topic_id)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.topic_doctype}
<topic id="{topic_id}" xml:lang="en-US">
    <title>{escape_xml(include_path.replace('.md', '').replace('/', ' - ').title())}</title>
    <body>
        <div id="{div_id}">
{body_content}
        </div>
    </body>
</topic>
'''

    def _elements_to_dita_warehouse(self, elements: List[MarkdownElement], topic_id: str) -> str:
        """Convert parsed elements to DITA body content for warehouse topics (no sections)."""
        output = []

        for elem in elements:
            if elem.type == 'heading':
                # Headings in warehouse topics become bold paragraphs
                output.append(f'            <p><b>{escape_xml(elem.content)}</b></p>')
            elif elem.type == 'paragraph':
                output.append(f'            <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>')
            elif elem.type == 'code_block':
                # Handle Mermaid diagrams as local images
                if elem.language == 'mermaid':
                    image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=True)
                    output.append(f'            {image_elem}')
                else:
                    output.append(f'            <codeblock>{escape_xml(elem.content)}</codeblock>')
            elif elem.type == 'note':
                note_type = self._detect_note_type(elem.content)
                cleaned_content = self._strip_note_prefix(elem.content, note_type)
                output.append(f'            <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
            elif elem.type == 'unordered_list':
                output.append(self._generate_ul(elem.items, indent='            '))
            elif elem.type == 'ordered_list':
                output.append(self._generate_ol(elem.items, indent='            '))
            elif elem.type == 'ordered_list_nested':
                nested_items = [child.items for child in elem.children]
                output.append(self._generate_ol(elem.items, indent='            ', nested_items=nested_items))
            elif elem.type == 'table':
                output.append(self._generate_table(elem.content).replace('        ', '            '))

        return '\n'.join(output)

    def _generate_prolog(self, topic_id: str, doc_type: str) -> str:
        """Generate DITA prolog with empty metadata block."""
        return '''    <prolog>
        <metadata/>
    </prolog>'''

    def generate_task_topic(self, title: str, content: str, topic_id: str) -> str:
        """Generate a DITA task topic (for QUICKSTART guides)."""
        elements = self.parser.parse(content)
        body_content = self._elements_to_task_body(elements, topic_id)
        prolog = self._generate_prolog(topic_id, 'task')

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.task_doctype}
<task id="{topic_id}" xml:lang="en-US">
    <title>{escape_xml(title)}</title>
{prolog}
    <taskbody>
{body_content}
    </taskbody>
</task>
'''

    def generate_concept_topic(self, title: str, content: str, topic_id: str) -> str:
        """Generate a DITA concept topic (for BEST-PRACTICES guides)."""
        elements = self.parser.parse(content)
        body_content = self._elements_to_dita(elements, topic_id)
        prolog = self._generate_prolog(topic_id, 'concept')

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.concept_doctype}
<concept id="{topic_id}" xml:lang="en-US">
    <title>{escape_xml(title)}</title>
{prolog}
    <conbody>
{body_content}
    </conbody>
</concept>
'''

    def _elements_to_dita(self, elements: List[MarkdownElement], topic_id: str) -> str:
        """Convert parsed elements to DITA body content."""
        output = []
        current_section = None
        section_content = []

        for elem in elements:
            if elem.type == 'heading' and elem.level == 2:
                # Close previous section
                if current_section:
                    output.append(self._wrap_section(current_section, section_content))
                current_section = elem.content
                section_content = []
            elif elem.type == 'heading' and elem.level >= 3:
                # H3+ headings become bold paragraphs
                section_content.append(f'        <p><b>{escape_xml(elem.content)}</b></p>')
            elif elem.type == 'include':
                section_content.append(self._generate_conref(elem.content, topic_id))
            elif elem.type == 'paragraph':
                section_content.append(f'        <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>')
            elif elem.type == 'code_block':
                # Handle Mermaid diagrams as local images
                if elem.language == 'mermaid':
                    image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=False)
                    section_content.append(f'        {image_elem}')
                else:
                    section_content.append(f'        <codeblock>{escape_xml(elem.content)}</codeblock>')
            elif elem.type == 'note':
                note_type = self._detect_note_type(elem.content)
                cleaned_content = self._strip_note_prefix(elem.content, note_type)
                section_content.append(f'        <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
            elif elem.type == 'unordered_list':
                section_content.append(self._generate_ul(elem.items))
            elif elem.type == 'ordered_list':
                section_content.append(self._generate_ol(elem.items))
            elif elem.type == 'ordered_list_nested':
                nested_items = [child.items for child in elem.children]
                section_content.append(self._generate_ol(elem.items, nested_items=nested_items))
            elif elem.type == 'table':
                section_content.append(self._generate_table(elem.content))

        # Close final section
        if current_section:
            # Collapse consecutive notes before wrapping
            section_content = collapse_consecutive_notes(section_content)
            output.append(self._wrap_section(current_section, section_content))
        elif section_content:
            # Collapse consecutive notes
            section_content = collapse_consecutive_notes(section_content)
            output.extend(section_content)

        return '\n'.join(output)

    def _elements_to_task_body(self, elements: List[MarkdownElement], topic_id: str) -> str:
        """Convert parsed elements to DITA task body with steps."""
        output = []
        prereq_list_items = []  # List items for the <ul>
        prereq_conrefs = []     # Conrefs go after the list
        prereq_notes = []       # Vendor doc priority and other prereq notes
        postreq_content = []    # Content for Next Steps / postreq
        steps = []
        current_step = None
        in_prereq = False
        in_disclaimer_section = False
        in_postreq = False

        for elem in elements:
            if elem.type == 'heading' and elem.level == 2:
                if 'prerequisite' in elem.content.lower():
                    in_prereq = True
                    in_disclaimer_section = False
                    in_postreq = False
                    current_step = None
                elif 'disclaimer' in elem.content.lower() or 'important' in elem.content.lower():
                    # Disclaimer section - vendor doc priority goes to prereq
                    in_disclaimer_section = True
                    in_prereq = False
                    in_postreq = False
                    current_step = None
                elif 'next step' in elem.content.lower():
                    # Next Steps section goes to postreq
                    in_postreq = True
                    in_prereq = False
                    in_disclaimer_section = False
                    if current_step:
                        steps.append(current_step)
                    current_step = None
                elif 'step' in elem.content.lower() or re.match(r'step\s*\d+', elem.content.lower()):
                    in_prereq = False
                    in_disclaimer_section = False
                    in_postreq = False
                    if current_step:
                        steps.append(current_step)
                    current_step = {'title': elem.content, 'content': []}
                else:
                    in_prereq = False
                    in_disclaimer_section = False
                    in_postreq = False
                    if current_step:
                        steps.append(current_step)
                    current_step = {'title': elem.content, 'content': []}
            elif in_postreq:
                # All content in Next Steps section goes to postreq
                if elem.type == 'paragraph':
                    postreq_content.append(f'            <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>')
                elif elem.type == 'unordered_list':
                    for item in elem.items:
                        postreq_content.append(f'            <p>- {self.parser.convert_inline(escape_xml(item))}</p>')
                elif elem.type == 'note':
                    note_type = self._detect_note_type(elem.content)
                    cleaned_content = self._strip_note_prefix(elem.content, note_type)
                    postreq_content.append(f'            <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
                elif elem.type == 'include':
                    postreq_content.append(self._generate_conref(elem.content, topic_id))
            elif elem.type == 'note':
                # Check if this is the vendor doc priority note
                content_lower = elem.content.lower()
                if 'vendor documentation priority' in content_lower or in_disclaimer_section:
                    # Move to prereq as a note
                    note_type = self._detect_note_type(elem.content)
                    cleaned_content = self._strip_note_prefix(elem.content, note_type)
                    prereq_notes.append(f'        <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
                elif in_prereq:
                    note_type = self._detect_note_type(elem.content)
                    cleaned_content = self._strip_note_prefix(elem.content, note_type)
                    prereq_conrefs.append(f'        <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>')
                elif current_step:
                    current_step['content'].append(self._element_to_dita(elem))
                else:
                    output.append(self._element_to_dita(elem))
            elif elem.type == 'include':
                if in_prereq or in_disclaimer_section:
                    # Conrefs in prereq go after the list, not inside it
                    prereq_conrefs.append(self._generate_conref(elem.content, topic_id))
                elif current_step:
                    current_step['content'].append(self._generate_conref(elem.content, topic_id))
                else:
                    output.append(self._generate_conref(elem.content, topic_id))
            elif in_prereq and elem.type == 'unordered_list':
                for item in elem.items:
                    prereq_list_items.append(f'            <li><p>{self.parser.convert_inline(escape_xml(item))}</p></li>')
            elif current_step:
                current_step['content'].append(self._element_to_dita(elem))

        if current_step:
            steps.append(current_step)

        # Build prerequisites - vendor doc priority note first, then list items, then conrefs
        if prereq_notes or prereq_list_items or prereq_conrefs:
            output.append('        <prereq>')
            # Vendor doc priority note first
            for note in prereq_notes:
                output.append(note)
            if prereq_list_items:
                output.append('            <ul>')
                output.extend(prereq_list_items)
                output.append('            </ul>')
            # Add conrefs after the list (still inside prereq, but not in ul)
            for conref in prereq_conrefs:
                output.append(conref)
            output.append('        </prereq>')

        # Build steps
        if steps:
            output.append('        <steps>')
            for step in steps:
                step_content = '\n'.join(step['content']) if step['content'] else ''
                # Remove "Step X:" prefix from title since DITA uses numbered list
                step_title = remove_step_prefix(step['title'])
                output.append(f'''            <step>
                <cmd>{escape_xml(step_title)}</cmd>
                <info>
{step_content}
                </info>
            </step>''')
            output.append('        </steps>')

        # Build postreq (Next Steps)
        if postreq_content:
            output.append('        <postreq>')
            output.extend(postreq_content)
            output.append('        </postreq>')

        return '\n'.join(output)


    def _element_to_dita(self, elem: MarkdownElement) -> str:
        """Convert a single element to DITA."""
        if elem.type == 'paragraph':
            return f'                    <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>'
        elif elem.type == 'heading' and elem.level >= 3:
            # H3+ headings become bold paragraphs
            return f'                    <p><b>{escape_xml(elem.content)}</b></p>'
        elif elem.type == 'code_block':
            # Handle Mermaid diagrams as local images
            if elem.language == 'mermaid':
                image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=False)
                return f'                    {image_elem}'
            else:
                return f'                    <codeblock>{escape_xml(elem.content)}</codeblock>'
        elif elem.type == 'unordered_list':
            return self._generate_ul(elem.items, indent='                    ')
        elif elem.type == 'ordered_list':
            return self._generate_ol(elem.items, indent='                    ')
        elif elem.type == 'ordered_list_nested':
            nested_items = [child.items for child in elem.children]
            return self._generate_ol(elem.items, indent='                    ', nested_items=nested_items)
        elif elem.type == 'note':
            note_type = self._detect_note_type(elem.content)
            cleaned_content = self._strip_note_prefix(elem.content, note_type)
            return f'                    <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(cleaned_content))}</p></note>'
        return ''

    def _generate_conref(self, include_path: str, topic_id: str) -> str:
        """Generate a conref element or inline content for an include.

        If inline_includes is True, resolves and inlines the content directly.
        Otherwise, uses <div> conref for deferred resolution.
        """
        if self.config.inline_includes:
            # Inline the content directly
            return self._inline_include_to_dita(include_path)
        else:
            # Use conref for deferred resolution
            warehouse_id = 'warehouse_' + sanitize_id(include_path.replace('/', '_').replace('.md', ''))
            div_id = sanitize_id(include_path.replace('/', '_').replace('.md', '')) + '_content'
            warehouse_file = warehouse_id + '.dita'
            return f'        <div conref="../warehouse/{warehouse_file}#{warehouse_id}/{div_id}"/>'

    def _wrap_section(self, title: str, content: List[str]) -> str:
        """Wrap content in a DITA section."""
        section_id = sanitize_id(title)
        content_str = '\n'.join(content) if content else ''

        # Quick Reference sections are wrapped in a note
        if 'quick reference' in title.lower():
            return f'''        <note type="tip">
            <p><b>{escape_xml(title)}</b></p>
{content_str}
        </note>'''
        else:
            return f'''        <section id="{section_id}">
            <title>{escape_xml(title)}</title>
{content_str}
        </section>'''

    def _detect_note_type(self, content: str) -> str:
        """Detect the appropriate DITA note type from content."""
        content_lower = content.lower()
        if 'warning' in content_lower or '⚠️' in content:
            return 'warning'
        elif 'important' in content_lower:
            return 'important'
        elif 'caution' in content_lower:
            return 'caution'
        elif 'tip' in content_lower:
            return 'tip'
        return 'note'

    def _strip_note_prefix(self, content: str, note_type: str) -> str:
        """Strip the note type prefix from content since DITA will add it."""
        import re
        # First, strip emoji prefixes (these appear before the text label)
        # e.g., "⚠️ Disclaimer:" or "⚠️ Note:"
        emoji_patterns = [
            r'\*\*⚠️\s*[^*:]+:\*\*\s*',    # **⚠️ Disclaimer:** or **⚠️ Note:**
            r'\*\*⚠️\*\*:?\s*',             # **⚠️**:
            r'⚠️\s*',                       # ⚠️ alone
            r'\*\*📖\s*[^*:]+:\*\*\s*',    # **📖 Info:**
            r'📖\s*',                       # 📖 alone
        ]
        result = content
        for pattern in emoji_patterns:
            result = re.sub(pattern, '', result)

        # Then strip text-based prefixes
        # Patterns to remove various prefix formats:
        # - **[WARNING] Something:** or **[IMPORTANT]:**
        # - [WARNING] Something: or [IMPORTANT]:
        # - **Warning:** or **Important:**
        # - Warning: or Important:
        patterns = [
            rf'\*\*\[{note_type}\][^*]*:\*\*\s*',   # **[WARNING] Something:**
            rf'\*\*\[{note_type}\]\*\*:?\s*',       # **[WARNING]**:
            rf'\*\*{note_type}[^*]*:\*\*\s*',       # **Warning Something:** (any text between)
            rf'\*\*{note_type}:?\*\*:?\s*',         # **Warning:** or **Warning**:
            rf'\[{note_type}\][^:\]]*:\s*',         # [WARNING] Something:
            rf'\[{note_type}\]:?\s*',               # [WARNING]:
            rf'{note_type}:\s*',                     # Warning:
        ]
        for pattern in patterns:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        return result.strip()

    def _generate_ul(self, items: List[str], indent: str = '        ') -> str:
        """Generate a DITA unordered list with proper <p> wrapping."""
        li_items = '\n'.join([f'{indent}    <li><p>{self.parser.convert_inline(escape_xml(item))}</p></li>' for item in items])
        return f'{indent}<ul>\n{li_items}\n{indent}</ul>'

    def _generate_ol(self, items: List[str], indent: str = '        ', nested_items: List[List[str]] = None) -> str:
        """Generate a DITA ordered list with proper <p> wrapping and nested <ul> support.

        Args:
            items: List of main ordered list item texts
            indent: Indentation string
            nested_items: List of lists, where each inner list contains the nested bullet items
                         for the corresponding main item. Can be None or empty lists for items
                         without nested bullets.
        """
        if nested_items is None:
            nested_items = [[] for _ in items]

        li_elements = []
        for idx, item in enumerate(items):
            nested = nested_items[idx] if idx < len(nested_items) else []

            if nested:
                # Item with nested ul
                li_content = f'{indent}    <li><p>{self.parser.convert_inline(escape_xml(item))}</p>\n'
                # Generate nested ul
                nested_ul_items = '\n'.join([
                    f'{indent}            <li><p>{self.parser.convert_inline(escape_xml(n))}</p></li>'
                    for n in nested
                ])
                li_content += f'{indent}        <ul>\n{nested_ul_items}\n{indent}        </ul>\n'
                li_content += f'{indent}    </li>'
            else:
                # Simple item without nested list
                li_content = f'{indent}    <li><p>{self.parser.convert_inline(escape_xml(item))}</p></li>'

            li_elements.append(li_content)

        return f'{indent}<ol>\n' + '\n'.join(li_elements) + f'\n{indent}</ol>'

    def _generate_table(self, content: str) -> str:
        """Generate a DITA table from Markdown table content."""
        lines = content.strip().split('\n')
        if not lines:
            return ''

        # Parse header
        header_cells = [cell.strip() for cell in lines[0].split('|')[1:-1]]
        num_cols = len(header_cells)

        # Parse body rows
        body_rows = []
        for line in lines[1:]:
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if len(cells) == num_cols:
                body_rows.append(cells)

        # Build DITA table
        table = ['        <table>']
        table.append(f'            <tgroup cols="{num_cols}">')

        # Header
        table.append('                <thead>')
        table.append('                    <row>')
        for cell in header_cells:
            table.append(f'                        <entry>{self.parser.convert_inline(escape_xml(cell))}</entry>')
        table.append('                    </row>')
        table.append('                </thead>')

        # Body
        table.append('                <tbody>')
        for row in body_rows:
            table.append('                    <row>')
            for cell in row:
                table.append(f'                        <entry>{self.parser.convert_inline(escape_xml(cell))}</entry>')
            table.append('                    </row>')
        table.append('                </tbody>')

        table.append('            </tgroup>')
        table.append('        </table>')

        return '\n'.join(table)


# ============================================================================
# DITA Map Generator
# ============================================================================

class DITAMapGenerator:
    """Generates DITA maps for navigation."""

    def __init__(self, config: ConversionConfig):
        self.config = config

    def _get_topic_href(self, topic: Dict[str, str]) -> str:
        """Get the href path for a topic, accounting for organized subdirectories."""
        subdir = topic.get('subdir', '')
        if subdir and self.config.organize_by_section:
            return f"topics/{subdir}/{topic['id']}.dita"
        return f"topics/{topic['id']}.dita"

    def generate_main_map(self, topics: List[Dict[str, str]], title: str = "Linux Storage Configuration Guides") -> str:
        """Generate the main DITA map."""
        topicrefs = []

        # Group topics by distribution
        distributions = {}
        common_topics = []

        for topic in topics:
            path = topic.get('relative_path', '')
            if path.startswith('distributions/'):
                parts = path.split('/')
                if len(parts) >= 2:
                    dist = parts[1]  # rhel, debian, suse, oracle
                    if dist not in distributions:
                        distributions[dist] = []
                    distributions[dist].append(topic)
            elif path.startswith('Proxmox/'):
                if 'Proxmox' not in distributions:
                    distributions['Proxmox'] = []
                distributions['Proxmox'].append(topic)
            else:
                common_topics.append(topic)

        # Build map structure
        for dist, dist_topics in sorted(distributions.items()):
            dist_title = dist.upper() if dist in ['rhel', 'suse'] else dist.title()
            topicrefs.append(f'    <topichead navtitle="{dist_title}">')

            # Group by protocol
            protocols = {}
            for topic in dist_topics:
                path = topic.get('relative_path', '')
                if 'nvme-tcp' in path.lower():
                    proto = 'NVMe-TCP'
                elif 'iscsi' in path.lower():
                    proto = 'iSCSI'
                elif 'nfs' in path.lower():
                    proto = 'NFS'
                else:
                    proto = 'Other'
                if proto not in protocols:
                    protocols[proto] = []
                protocols[proto].append(topic)

            for proto, proto_topics in sorted(protocols.items()):
                topicrefs.append(f'        <topichead navtitle="{proto}">')
                for topic in proto_topics:
                    # Check if this is a parent topic with children (BEST-PRACTICES split by H2)
                    if topic.get('type') == 'concept-parent' and 'children' in topic:
                        # Create a topichead for the parent with nested children
                        parent_title = 'Best Practices' if 'best-practices' in topic['id'].lower() else topic['title']
                        topicrefs.append(f'            <topichead navtitle="{escape_xml(parent_title)}">')
                        for child in topic['children']:
                            child_href = self._get_topic_href(child)
                            topicrefs.append(f'                <topicref href="{child_href}" navtitle="{escape_xml(child["title"])}"/>')
                        topicrefs.append('            </topichead>')
                    else:
                        href = self._get_topic_href(topic)
                        topicrefs.append(f'            <topicref href="{href}"/>')
                topicrefs.append('        </topichead>')

            topicrefs.append('    </topichead>')

        # Add common topics
        if common_topics:
            topicrefs.append('    <topichead navtitle="Common Resources">')
            for topic in common_topics:
                href = self._get_topic_href(topic)
                topicrefs.append(f'        <topicref href="{href}"/>')
            topicrefs.append('    </topichead>')

        topicrefs_str = '\n'.join(topicrefs)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.map_doctype}
<map xml:lang="en-US">
    <title>{escape_xml(title)}</title>
{topicrefs_str}
</map>
'''

    def generate_section_map(self, topics: List[Dict[str, str]], dist: str, proto: str) -> str:
        """Generate a DITA map for a specific distribution/protocol combination."""
        dist_title = dist.upper() if dist in ['rhel', 'suse'] else dist.title()
        proto_map = {'nfs': 'NFS', 'iscsi': 'iSCSI', 'nvme-tcp': 'NVMe-TCP'}
        proto_title = proto_map.get(proto.lower(), proto.title())
        map_title = f"{dist_title} {proto_title} Storage Guide"

        topicrefs = []

        for topic in topics:
            if topic.get('type') == 'concept-parent' and 'children' in topic:
                parent_title = 'Best Practices' if 'best-practices' in topic['id'].lower() else topic['title']
                topicrefs.append(f'    <topichead navtitle="{escape_xml(parent_title)}">')
                for child in topic['children']:
                    child_href = self._get_topic_href(child)
                    topicrefs.append(f'        <topicref href="{child_href}" navtitle="{escape_xml(child["title"])}"/>')
                topicrefs.append('    </topichead>')
            else:
                href = self._get_topic_href(topic)
                topic_title = topic.get('title', topic['id'])
                topicrefs.append(f'    <topicref href="{href}" navtitle="{escape_xml(topic_title)}"/>')

        topicrefs_str = '\n'.join(topicrefs)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.map_doctype}
<map xml:lang="en-US">
    <title>{escape_xml(map_title)}</title>
{topicrefs_str}
</map>
'''

    def generate_best_practices_map(self, children: List[Dict[str, str]], dist: str, proto: str, main_title: str) -> str:
        """Generate a DITA map for a single best practices document.

        The Architecture section is the top-level node, with other topics nested below.
        """
        dist_title = dist.upper() if dist in ['rhel', 'suse'] else dist.title()
        proto_map = {'nfs': 'NFS', 'iscsi': 'iSCSI', 'nvme-tcp': 'NVMe-TCP'}
        proto_title = proto_map.get(proto.lower(), proto.title())
        map_title = f"{dist_title} {proto_title} Best Practices"

        # Find the architecture topic to be the top-level
        architecture_topic = None
        other_topics = []

        for child in children:
            title_lower = child.get('title', '').lower()
            if 'architecture' in title_lower and 'overview' in title_lower:
                architecture_topic = child
            elif 'architecture' in title_lower:
                # Also match just "architecture" as a fallback
                if architecture_topic is None:
                    architecture_topic = child
                else:
                    other_topics.append(child)
            else:
                other_topics.append(child)

        topicrefs = []

        if architecture_topic:
            # Architecture is the top-level, others are nested under it
            arch_href = self._get_topic_href(architecture_topic)
            topicrefs.append(f'    <topicref href="{arch_href}" navtitle="{escape_xml(architecture_topic["title"])}">')
            for child in other_topics:
                child_href = self._get_topic_href(child)
                topicrefs.append(f'        <topicref href="{child_href}" navtitle="{escape_xml(child["title"])}"/>')
            topicrefs.append('    </topicref>')
        else:
            # No architecture topic found, just list all topics
            for child in children:
                child_href = self._get_topic_href(child)
                topicrefs.append(f'    <topicref href="{child_href}" navtitle="{escape_xml(child["title"])}"/>')

        topicrefs_str = '\n'.join(topicrefs)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.map_doctype}
<map xml:lang="en-US">
    <title>{escape_xml(map_title)}</title>
{topicrefs_str}
</map>
'''


# ============================================================================
# Main Converter
# ============================================================================

class MarkdownToDITAConverter:
    """Main converter that orchestrates the conversion process."""

    def __init__(self, config: ConversionConfig):
        self.config = config
        self.dita_gen = DITAGenerator(config)
        self.map_gen = DITAMapGenerator(config)
        self.converted_topics = []

    def convert(self):
        """Run the full conversion process."""
        print(f"Starting conversion from {self.config.input_dir}")

        # Create output directories
        self._create_output_dirs()

        # Step 1: Convert include files to warehouse topics
        print("\n=== Converting include files to warehouse topics ===")
        self._convert_includes()

        # Step 2: Convert main documentation files
        print("\n=== Converting main documentation files ===")
        self._convert_main_docs()

        # Step 3: Generate DITA map
        print("\n=== Generating DITA map ===")
        self._generate_map()

        print(f"\n✅ Conversion complete! Output written to: {self.config.output_dir}")

    def _create_output_dirs(self):
        """Create output directory structure, cleaning existing files first."""
        import shutil

        if self.config.use_existing_images:
            # Preserve the images directory, clean everything else
            if self.config.output_dir.exists():
                images_path = self.config.output_dir / self.config.images_dir
                for subdir in [self.config.warehouse_dir, self.config.topics_dir, self.config.maps_dir]:
                    subdir_path = self.config.output_dir / subdir
                    if subdir_path.exists():
                        shutil.rmtree(subdir_path)
                print(f"  Cleaned output directory (preserved images): {self.config.output_dir}")
        else:
            # Clean entire output directory including images
            if self.config.output_dir.exists():
                print(f"  Cleaning existing output directory: {self.config.output_dir}")
                shutil.rmtree(self.config.output_dir)

        dirs = [
            self.config.output_dir / self.config.warehouse_dir,
            self.config.output_dir / self.config.topics_dir,
            self.config.output_dir / self.config.maps_dir,
            self.config.output_dir / self.config.images_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {d}")

    def _convert_includes(self):
        """Convert Jekyll include files to DITA warehouse topics.

        When inline_includes mode is enabled, this step is skipped since
        include content is embedded directly in the main topics.
        """
        if self.config.inline_includes:
            print("  Skipped: Inline mode enabled - includes will be embedded in topics")
            return

        includes_dir = self.config.input_dir / '_includes'
        if not includes_dir.exists():
            print(f"  Warning: _includes directory not found at {includes_dir}")
            return

        for md_file in includes_dir.rglob('*.md'):
            relative_path = md_file.relative_to(includes_dir)
            include_path = str(relative_path).replace('\\', '/')

            print(f"  Converting: {include_path}")

            # Set source context so diagrams get meaningful filenames instead of "unknown-diagram-XX.png"
            self.dita_gen.set_source_context(f"_includes/{include_path}")

            content = md_file.read_text(encoding='utf-8')
            dita_content = self.dita_gen.generate_warehouse_topic(include_path, content)

            # Generate output filename
            warehouse_id = 'warehouse_' + sanitize_id(include_path.replace('/', '_').replace('.md', ''))
            output_file = self.config.output_dir / self.config.warehouse_dir / f"{warehouse_id}.dita"

            output_file.write_text(dita_content, encoding='utf-8')

    def _should_convert_file(self, rel_path: Path) -> bool:
        """Check if a file should be converted based on distribution/protocol filters."""
        path_str = str(rel_path).replace('\\', '/').lower()

        # Check distribution filter
        if self.config.distribution:
            dist_filter = self.config.distribution.lower()
            # Handle aws-outposts special case
            if dist_filter == 'aws-outposts' or dist_filter == 'aws':
                if 'aws-outposts' not in path_str:
                    return False
            elif f'/{dist_filter}/' not in path_str and not path_str.startswith(f'{dist_filter}/'):
                return False

        # Check protocol filter
        if self.config.protocol:
            proto_filter = self.config.protocol.lower()
            if f'/{proto_filter}/' not in path_str:
                return False

        return True

    def _get_topic_subdir(self, rel_path_str: str) -> str:
        """Get the subdirectory path for organized topic output."""
        if not self.config.organize_by_section:
            return ""

        # Parse path like "distributions/rhel/iscsi/QUICKSTART.md"
        parts = rel_path_str.replace('\\', '/').lower().split('/')
        if parts and parts[0] == 'distributions':
            parts = parts[1:]  # Remove "distributions" prefix

        # Filter out the filename (ends with .md) from parts
        dir_parts = [p for p in parts if not p.endswith('.md')]

        # Return directory parts as subdir (e.g., "rhel/iscsi" or just "aws-outposts")
        if len(dir_parts) >= 2:
            return f"{dir_parts[0]}/{dir_parts[1]}"
        elif len(dir_parts) >= 1:
            return dir_parts[0]
        return ""

    def _convert_main_docs(self):
        """Convert main documentation files to DITA topics."""
        # Find all QUICKSTART, GUI-QUICKSTART, and BEST-PRACTICES files
        for pattern in ['**/QUICKSTART.md', '**/GUI-QUICKSTART.md', '**/BEST-PRACTICES.md']:
            for md_file in self.config.input_dir.glob(pattern):
                # Skip files in _includes, common, etc.
                rel_path = md_file.relative_to(self.config.input_dir)
                if str(rel_path).startswith(('_', 'common', 'scripts')):
                    continue

                # Apply distribution/protocol filters
                if not self._should_convert_file(rel_path):
                    continue

                self._convert_doc_file(md_file)

        # Also convert standalone reference files from _includes that are linked from topics
        self._convert_reference_files()

    def _convert_doc_file(self, md_file: Path):
        """Convert a single documentation file to DITA."""
        rel_path = md_file.relative_to(self.config.input_dir)
        rel_path_str = str(rel_path).replace('\\', '/')

        print(f"  Converting: {rel_path_str}")

        # Set source context for human-readable diagram filenames
        self.dita_gen.set_source_context(rel_path_str)

        content = md_file.read_text(encoding='utf-8')

        # Extract title from YAML front matter or first heading
        title = self._extract_title(content, md_file.stem)

        # Generate base topic ID (without prefix)
        base_id = sanitize_id(rel_path_str.replace('/', '_').replace('.md', ''))
        # Replace 'distributions_' prefix with short prefix based on topic type
        base_id_short = re.sub(r'^distributions_', '', base_id)

        # Determine output subdirectory for organized output
        topic_subdir = self._get_topic_subdir(rel_path_str)
        if topic_subdir:
            output_dir = self.config.output_dir / self.config.topics_dir / topic_subdir
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = self.config.output_dir / self.config.topics_dir

        # Determine topic type and generate DITA
        if 'QUICKSTART' in md_file.name:
            # Task topics use 't_' prefix
            topic_id = f"t_{base_id_short}"
            dita_content = self.dita_gen.generate_task_topic(title, content, topic_id)

            # Clean non-ASCII characters from output
            dita_content = remove_non_ascii(dita_content)

            # Write output file
            output_file = output_dir / f"{topic_id}.dita"
            output_file.write_text(dita_content, encoding='utf-8')

            # Track for map generation
            self.converted_topics.append({
                'id': topic_id,
                'title': title,
                'relative_path': rel_path_str,
                'type': 'task',
                'subdir': topic_subdir
            })
        else:
            # BEST-PRACTICES: Split by H2 sections into separate topics (concept with 'c_' prefix)
            self._convert_best_practices_sections(md_file, content, title, base_id_short, rel_path_str, topic_subdir)

    def _split_by_h2(self, content: str) -> List[Tuple[str, str]]:
        """Split content by H2 headings. Returns list of (section_title, section_content)."""
        # Remove YAML front matter
        content = re.sub(r'^---\n.*?---\n', '', content, flags=re.DOTALL)

        # Remove the main H1 title
        content = re.sub(r'^#\s+[^\n]+\n', '', content)

        sections = []
        # Split by H2 headings
        h2_pattern = r'^##\s+(.+)$'

        # Find all H2 positions
        h2_matches = list(re.finditer(h2_pattern, content, re.MULTILINE))

        if not h2_matches:
            return [('Overview', content.strip())]

        for i, match in enumerate(h2_matches):
            section_title = match.group(1).strip()
            start = match.end()

            # Find end (next H2 or end of content)
            if i + 1 < len(h2_matches):
                end = h2_matches[i + 1].start()
            else:
                end = len(content)

            section_content = content[start:end].strip()

            # Skip empty sections and Table of Contents
            if section_content and 'table of contents' not in section_title.lower():
                sections.append((section_title, section_content))

        return sections

    def _convert_best_practices_sections(self, md_file: Path, content: str, main_title: str, base_topic_id: str, rel_path_str: str, topic_subdir: str = ""):
        """Convert BEST-PRACTICES file into multiple section topics."""
        sections = self._split_by_h2(content)

        # Determine output directory
        if topic_subdir:
            output_dir = self.config.output_dir / self.config.topics_dir / topic_subdir
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = self.config.output_dir / self.config.topics_dir

        section_topics = []
        is_first_topic = True

        for section_title, section_content in sections:
            # Skip troubleshooting sections
            if 'troubleshoot' in section_title.lower():
                continue

            # Generate section topic ID with 'c_' prefix for concept
            section_id = f"c_{base_topic_id}_{sanitize_id(section_title)}"

            # For the first topic (Architecture Overview), use just the main title
            # For other topics, use "Main Title - Section Title"
            if is_first_topic and 'architecture' in section_title.lower():
                topic_title = main_title
                is_first_topic = False
            else:
                topic_title = f"{main_title} - {section_title}"

            # Generate concept topic for this section
            dita_content = self.dita_gen.generate_concept_topic(
                topic_title,
                section_content,
                section_id
            )

            # Clean non-ASCII characters from output
            dita_content = remove_non_ascii(dita_content)

            # Write output file
            output_file = output_dir / f"{section_id}.dita"
            output_file.write_text(dita_content, encoding='utf-8')

            section_topics.append({
                'id': section_id,
                'title': section_title,
                'relative_path': rel_path_str,
                'type': 'concept',
                'subdir': topic_subdir
            })

        # Track as a parent topic with children for map generation
        # Parent ID also uses 'c_' prefix
        parent_id = f"c_{base_topic_id}"
        self.converted_topics.append({
            'id': parent_id,
            'title': main_title,
            'relative_path': rel_path_str,
            'type': 'concept-parent',
            'children': section_topics,
            'subdir': topic_subdir
        })

    def _convert_reference_files(self):
        """Convert standalone reference files (glossary, network-concepts, etc.) to DITA topics.

        These files are linked from the main topics and need to be converted as well.
        """
        # List of reference files to convert from _includes
        reference_files = [
            ('_includes/glossary.md', 'Storage Terminology Glossary'),
            ('_includes/network-concepts.md', 'Network Configuration Concepts'),
            ('_includes/multipath-concepts.md', 'Multipath Configuration Concepts'),
        ]

        # Create common output directory
        common_dir = self.config.output_dir / self.config.topics_dir / 'common'
        common_dir.mkdir(parents=True, exist_ok=True)

        for rel_path, default_title in reference_files:
            md_file = self.config.input_dir / rel_path
            if not md_file.exists():
                print(f"  Skipping (not found): {rel_path}")
                continue

            print(f"  Converting reference: {rel_path}")

            # Set source context for diagrams
            self.dita_gen.set_source_context(rel_path)

            content = md_file.read_text(encoding='utf-8')
            title = self._extract_title(content, default_title)

            # Generate topic ID with 'c_' prefix (these are concept/reference topics)
            filename = Path(rel_path).stem
            topic_id = f"c_{sanitize_id(filename)}"

            # Generate concept topic
            dita_content = self.dita_gen.generate_concept_topic(title, content, topic_id)

            # Clean non-ASCII characters from output
            dita_content = remove_non_ascii(dita_content)

            # Write output file
            output_file = common_dir / f"{topic_id}.dita"
            output_file.write_text(dita_content, encoding='utf-8')

            # Track for map generation
            self.converted_topics.append({
                'id': topic_id,
                'title': title,
                'relative_path': f'common/{filename}',
                'type': 'concept',
                'subdir': 'common'
            })

    def _extract_title(self, content: str, default: str) -> str:
        """Extract title from content."""
        # Try YAML front matter
        yaml_match = re.search(r'^---\n.*?title:\s*["\']?([^"\'\n]+)["\']?\n.*?---', content, re.DOTALL)
        if yaml_match:
            return yaml_match.group(1).strip()

        # Try first heading
        heading_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

        return default.replace('-', ' ').title()

    def _generate_map(self):
        """Generate the main DITA map and optional section maps."""
        if not self.converted_topics:
            print("  No topics to include in map")
            return

        # Generate main map with appropriate title
        if self.config.distribution or self.config.protocol:
            # Generate a filtered main map with specific title
            dist_label = self.config.distribution.upper() if self.config.distribution in ['rhel', 'suse'] else self.config.distribution.title()
            proto_map = {'nfs': 'NFS', 'iscsi': 'iSCSI', 'nvme-tcp': 'NVMe-TCP'}
            proto_label = proto_map.get(self.config.protocol.lower(), self.config.protocol.title()) if self.config.protocol else ''
            parts = [p for p in [dist_label, proto_label, "Storage Guide"] if p]
            title = " ".join(parts)
        else:
            title = "Linux Storage Configuration Guides"

        map_content = self.map_gen.generate_main_map(self.converted_topics, title)
        map_file = self.config.output_dir / self.config.maps_dir / "linux-storage-guides.ditamap"
        map_file.write_text(map_content, encoding='utf-8')
        print(f"  Generated: {map_file}")

        # Generate per-section maps if requested
        if self.config.generate_section_maps:
            self._generate_section_maps()

    def _generate_section_maps(self):
        """Generate individual DITA maps for each distribution/protocol combination."""
        # Group topics by distribution and protocol
        sections = {}  # key = (dist, proto), value = list of topics

        for topic in self.converted_topics:
            path = topic.get('relative_path', '')
            parts = path.lower().replace('\\', '/').split('/')

            # Extract distribution
            if parts and parts[0] == 'distributions' and len(parts) >= 2:
                dist = parts[1]
            elif path.lower().startswith('proxmox/'):
                dist = 'proxmox'
            else:
                continue  # Skip common/other topics for section maps

            # Extract protocol
            if 'nvme-tcp' in path.lower():
                proto = 'nvme-tcp'
            elif 'iscsi' in path.lower():
                proto = 'iscsi'
            elif 'nfs' in path.lower():
                proto = 'nfs'
            else:
                proto = 'other'

            key = (dist, proto)
            if key not in sections:
                sections[key] = []
            sections[key].append(topic)

        # Generate a map for each section
        for (dist, proto), topics in sorted(sections.items()):
            map_content = self.map_gen.generate_section_map(topics, dist, proto)
            map_filename = f"{dist}-{proto}.ditamap"
            map_file = self.config.output_dir / self.config.maps_dir / map_filename
            map_file.write_text(map_content, encoding='utf-8')
            print(f"  Generated section map: {map_file}")

            # Also generate individual best practices maps for each concept-parent
            for topic in topics:
                if topic.get('type') == 'concept-parent' and 'children' in topic:
                    # This is a best practices document - create its own map
                    bp_map_content = self.map_gen.generate_best_practices_map(
                        topic['children'],
                        dist,
                        proto,
                        topic.get('title', 'Best Practices')
                    )
                    bp_map_filename = f"{dist}-{proto}-best-practices.ditamap"
                    bp_map_file = self.config.output_dir / self.config.maps_dir / bp_map_filename
                    bp_map_file.write_text(bp_map_content, encoding='utf-8')
                    print(f"  Generated best practices map: {bp_map_file}")


# ============================================================================
# Command Line Interface
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Convert Jekyll Markdown documentation to DITA XML for Heretto import.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Convert all documentation
    python convert_to_dita.py --inline-includes

    # Convert only RHEL documentation
    python convert_to_dita.py --inline-includes -d rhel

    # Convert only iSCSI documentation across all distributions
    python convert_to_dita.py --inline-includes -p iscsi

    # Convert RHEL iSCSI only with separate maps
    python convert_to_dita.py --inline-includes -d rhel -p iscsi --section-maps

    # Organize output into subdirectories for easier selective import
    python convert_to_dita.py --inline-includes --section-maps --organize-sections

    # Re-convert with existing images (skip re-downloading unchanged diagrams)
    python convert_to_dita.py --inline-includes --use-existing-images

Available distributions: rhel, debian, suse, oracle, proxmox, xcpng, aws-outposts
Available protocols: iscsi, nvme-tcp, nfs
        '''
    )

    parser.add_argument(
        '-i', '--input-dir',
        type=Path,
        default=Path('.'),
        help='Input directory containing Jekyll Markdown files (default: current directory)'
    )

    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=Path('dita_output'),
        help='Output directory for DITA files (default: dita_output)'
    )

    parser.add_argument(
        '--inline-includes',
        action='store_true',
        help='Inline include content directly instead of using conref (no warehouse topics created)'
    )

    parser.add_argument(
        '--skip-diagrams',
        action='store_true',
        help='Skip downloading Mermaid diagrams (faster for testing runs)'
    )

    parser.add_argument(
        '--use-existing-images',
        action='store_true',
        help='Keep existing images and only download missing ones (skips clearing images directory)'
    )

    parser.add_argument(
        '-d', '--distribution',
        type=str,
        default='',
        help='Filter by distribution (e.g., rhel, debian, suse, oracle, proxmox, xcpng, aws-outposts)'
    )

    parser.add_argument(
        '-p', '--protocol',
        type=str,
        default='',
        help='Filter by protocol (e.g., iscsi, nvme-tcp, nfs)'
    )

    parser.add_argument(
        '--section-maps',
        action='store_true',
        help='Generate separate DITA maps for each distribution/protocol combination'
    )

    parser.add_argument(
        '--organize-sections',
        action='store_true',
        help='Organize topics into subdirectories (topics/rhel/iscsi/) instead of flat structure'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    # Validate input directory
    if not args.input_dir.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    # Create configuration
    config = ConversionConfig(
        input_dir=args.input_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        inline_includes=args.inline_includes,
        skip_diagrams=args.skip_diagrams,
        use_existing_images=args.use_existing_images,
        distribution=args.distribution.lower(),
        protocol=args.protocol.lower(),
        generate_section_maps=args.section_maps,
        organize_by_section=args.organize_sections
    )

    # Run conversion
    converter = MarkdownToDITAConverter(config)
    converter.convert()

    # Print summary
    print(f"\n📁 Output Structure:")
    print(f"   {config.output_dir}/")
    print(f"   ├── {config.warehouse_dir}/    # Reusable content (warehouse topics)")
    print(f"   ├── {config.topics_dir}/       # Main documentation topics")
    print(f"   ├── {config.images_dir}/       # Downloaded diagram images (PNG)")
    print(f"   └── {config.maps_dir}/         # DITA navigation maps")

    print(f"\n📋 Import Instructions for Heretto:")
    print(f"   1. Create a new content collection in Heretto")
    print(f"   2. Import the entire '{config.output_dir}' folder")
    print(f"   3. Or import the '{config.maps_dir}/linux-storage-guides.ditamap' file")
    print(f"   4. Ensure images folder is included for diagram rendering")
    print(f"   5. Review and publish your content")


if __name__ == '__main__':
    main()