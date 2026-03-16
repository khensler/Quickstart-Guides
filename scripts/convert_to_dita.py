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

Usage:
    python convert_to_dita.py [--input-dir PATH] [--output-dir PATH]
"""

import os
import re
import sys
import argparse
import uuid
import base64
import zlib
import hashlib
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


def generate_uuid() -> str:
    """Generate a short unique identifier."""
    return uuid.uuid4().hex[:8]


def get_kroki_url(mermaid_code: str) -> str:
    """
    Generate a Kroki URL for Mermaid code.

    Kroki is a diagram rendering service that supports Mermaid.
    """
    code = mermaid_code.strip()

    # Kroki uses deflate compression + base64
    compressed = zlib.compress(code.encode('utf-8'), 9)
    encoded = base64.urlsafe_b64encode(compressed).decode('ascii')

    return f"https://kroki.io/mermaid/svg/{encoded}"


def download_mermaid_image(mermaid_code: str, images_dir: Path, diagram_counter: int) -> str:
    """
    Download a Mermaid diagram as SVG from Kroki and save locally.

    Returns the relative path to the saved image file.
    """
    code = mermaid_code.strip()

    # Generate a unique filename based on content hash
    content_hash = hashlib.md5(code.encode('utf-8')).hexdigest()[:12]
    filename = f"diagram_{diagram_counter:03d}_{content_hash}.svg"
    filepath = images_dir / filename

    # Check if already downloaded (cache)
    if filepath.exists():
        return filename

    # Generate Kroki URL
    url = get_kroki_url(code)

    try:
        # Download the SVG
        req = urllib.request.Request(url, headers={'User-Agent': 'DITA-Converter/1.0'})
        with urllib.request.urlopen(req, timeout=30) as response:
            svg_content = response.read()

        # Save to file
        filepath.write_bytes(svg_content)
        print(f"    Downloaded: {filename}")
        return filename

    except urllib.error.URLError as e:
        print(f"    Warning: Failed to download diagram: {e}")
        # Return a placeholder filename
        return f"diagram_{diagram_counter:03d}_error.svg"
    except Exception as e:
        print(f"    Warning: Error processing diagram: {e}")
        return f"diagram_{diagram_counter:03d}_error.svg"


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

            # Check for ordered list
            ol_match = self.ordered_list_pattern.match(line)
            if ol_match:
                items = []
                while i < len(lines) and self.ordered_list_pattern.match(lines[i]):
                    match = self.ordered_list_pattern.match(lines[i])
                    items.append(match.group(2).strip())
                    i += 1
                elements.append(MarkdownElement(
                    type='ordered_list',
                    content='',
                    items=items
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
        # Links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<xref href="\2" format="html" scope="external">\1</xref>', text)
        return text


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
        self.diagram_counter = 0  # Counter for unique diagram filenames

    def _handle_mermaid_diagram(self, mermaid_code: str, from_warehouse: bool = False) -> str:
        """
        Download a Mermaid diagram and return the DITA image element.

        Args:
            mermaid_code: The Mermaid diagram code
            from_warehouse: If True, use path for warehouse topics (../images/)
                           If False, use path for main topics (../images/)
        """
        self.diagram_counter += 1
        filename = download_mermaid_image(mermaid_code, self.images_dir, self.diagram_counter)

        # Both warehouse and topics are one level deep, so path is the same
        image_path = f"../images/{filename}"

        return f'<fig><image href="{escape_xml_attr(image_path)}"><alt>Diagram</alt></image></fig>'

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
<topic id="{topic_id}">
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
                output.append(f'            <p><b>{escape_xml(elem.content)}</b></p>')
            elif elem.type == 'paragraph':
                output.append(f'            <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>')
            elif elem.type == 'code_block':
                # Handle Mermaid diagrams as local images
                if elem.language == 'mermaid':
                    image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=True)
                    output.append(f'            {image_elem}')
                else:
                    lang_attr = f' outputclass="{elem.language}"' if elem.language else ''
                    output.append(f'            <codeblock{lang_attr}>{escape_xml(elem.content)}</codeblock>')
            elif elem.type == 'note':
                note_type = self._detect_note_type(elem.content)
                output.append(f'            <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(elem.content))}</p></note>')
            elif elem.type == 'unordered_list':
                output.append(self._generate_ul(elem.items, indent='            '))
            elif elem.type == 'ordered_list':
                output.append(self._generate_ol(elem.items, indent='            '))
            elif elem.type == 'table':
                output.append(self._generate_table(elem.content).replace('        ', '            '))

        return '\n'.join(output)

    def generate_task_topic(self, title: str, content: str, topic_id: str) -> str:
        """Generate a DITA task topic (for QUICKSTART guides)."""
        elements = self.parser.parse(content)
        body_content = self._elements_to_task_body(elements, topic_id)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.task_doctype}
<task id="{topic_id}">
    <title>{escape_xml(title)}</title>
    <taskbody>
{body_content}
    </taskbody>
</task>
'''

    def generate_concept_topic(self, title: str, content: str, topic_id: str) -> str:
        """Generate a DITA concept topic (for BEST-PRACTICES guides)."""
        elements = self.parser.parse(content)
        body_content = self._elements_to_dita(elements, topic_id)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.concept_doctype}
<concept id="{topic_id}">
    <title>{escape_xml(title)}</title>
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
                    lang_attr = f' outputclass="{elem.language}"' if elem.language else ''
                    section_content.append(f'        <codeblock{lang_attr}>{escape_xml(elem.content)}</codeblock>')
            elif elem.type == 'note':
                note_type = self._detect_note_type(elem.content)
                section_content.append(f'        <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(elem.content))}</p></note>')
            elif elem.type == 'unordered_list':
                section_content.append(self._generate_ul(elem.items))
            elif elem.type == 'ordered_list':
                section_content.append(self._generate_ol(elem.items))
            elif elem.type == 'table':
                section_content.append(self._generate_table(elem.content))

        # Close final section
        if current_section:
            output.append(self._wrap_section(current_section, section_content))
        elif section_content:
            output.extend(section_content)

        return '\n'.join(output)

    def _elements_to_task_body(self, elements: List[MarkdownElement], topic_id: str) -> str:
        """Convert parsed elements to DITA task body with steps."""
        output = []
        prereq_list_items = []  # List items for the <ul>
        prereq_conrefs = []     # Conrefs go after the list
        steps = []
        current_step = None
        in_prereq = False

        for elem in elements:
            if elem.type == 'heading' and elem.level == 2:
                if 'prerequisite' in elem.content.lower():
                    in_prereq = True
                    current_step = None
                elif 'step' in elem.content.lower() or re.match(r'step\s*\d+', elem.content.lower()):
                    in_prereq = False
                    if current_step:
                        steps.append(current_step)
                    current_step = {'title': elem.content, 'content': []}
                else:
                    in_prereq = False
                    if current_step:
                        steps.append(current_step)
                    current_step = {'title': elem.content, 'content': []}
            elif elem.type == 'include':
                if in_prereq:
                    # Conrefs in prereq go after the list, not inside it
                    prereq_conrefs.append(self._generate_conref(elem.content, topic_id))
                elif current_step:
                    current_step['content'].append(self._generate_conref(elem.content, topic_id))
                else:
                    output.append(self._generate_conref(elem.content, topic_id))
            elif in_prereq and elem.type == 'unordered_list':
                for item in elem.items:
                    prereq_list_items.append(f'            <li>{self.parser.convert_inline(escape_xml(item))}</li>')
            elif current_step:
                current_step['content'].append(self._element_to_dita(elem))

        if current_step:
            steps.append(current_step)

        # Build prerequisites - list items first, then conrefs
        if prereq_list_items or prereq_conrefs:
            output.append('        <prereq>')
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
                output.append(f'''            <step>
                <cmd>{escape_xml(step['title'])}</cmd>
                <info>
{step_content}
                </info>
            </step>''')
            output.append('        </steps>')

        return '\n'.join(output)


    def _element_to_dita(self, elem: MarkdownElement) -> str:
        """Convert a single element to DITA."""
        if elem.type == 'paragraph':
            return f'                    <p>{self.parser.convert_inline(escape_xml(elem.content))}</p>'
        elif elem.type == 'code_block':
            # Handle Mermaid diagrams as local images
            if elem.language == 'mermaid':
                image_elem = self._handle_mermaid_diagram(elem.content, from_warehouse=False)
                return f'                    {image_elem}'
            else:
                lang_attr = f' outputclass="{elem.language}"' if elem.language else ''
                return f'                    <codeblock{lang_attr}>{escape_xml(elem.content)}</codeblock>'
        elif elem.type == 'unordered_list':
            return self._generate_ul(elem.items, indent='                    ')
        elif elem.type == 'ordered_list':
            return self._generate_ol(elem.items, indent='                    ')
        elif elem.type == 'note':
            note_type = self._detect_note_type(elem.content)
            return f'                    <note type="{note_type}"><p>{self.parser.convert_inline(escape_xml(elem.content))}</p></note>'
        return ''

    def _generate_conref(self, include_path: str, topic_id: str) -> str:
        """Generate a conref element for an include.

        Uses <div> instead of <section> to allow conref in task topics,
        since <section> is not allowed in <taskbody>.
        """
        warehouse_id = 'warehouse_' + sanitize_id(include_path.replace('/', '_').replace('.md', ''))
        div_id = sanitize_id(include_path.replace('/', '_').replace('.md', '')) + '_content'
        warehouse_file = warehouse_id + '.dita'
        return f'        <div conref="../warehouse/{warehouse_file}#{warehouse_id}/{div_id}"/>'

    def _wrap_section(self, title: str, content: List[str]) -> str:
        """Wrap content in a DITA section."""
        section_id = sanitize_id(title)
        content_str = '\n'.join(content) if content else ''
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

    def _generate_ul(self, items: List[str], indent: str = '        ') -> str:
        """Generate a DITA unordered list."""
        li_items = '\n'.join([f'{indent}    <li>{self.parser.convert_inline(escape_xml(item))}</li>' for item in items])
        return f'{indent}<ul>\n{li_items}\n{indent}</ul>'

    def _generate_ol(self, items: List[str], indent: str = '        ') -> str:
        """Generate a DITA ordered list."""
        li_items = '\n'.join([f'{indent}    <li>{self.parser.convert_inline(escape_xml(item))}</li>' for item in items])
        return f'{indent}<ol>\n{li_items}\n{indent}</ol>'

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

    def generate_main_map(self, topics: List[Dict[str, str]]) -> str:
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
                            child_href = f"topics/{child['id']}.dita"
                            topicrefs.append(f'                <topicref href="{child_href}" navtitle="{escape_xml(child["title"])}"/>')
                        topicrefs.append('            </topichead>')
                    else:
                        href = f"topics/{topic['id']}.dita"
                        topicrefs.append(f'            <topicref href="{href}"/>')
                topicrefs.append('        </topichead>')

            topicrefs.append('    </topichead>')

        # Add common topics
        if common_topics:
            topicrefs.append('    <topichead navtitle="Common Resources">')
            for topic in common_topics:
                href = f"topics/{topic['id']}.dita"
                topicrefs.append(f'        <topicref href="{href}"/>')
            topicrefs.append('    </topichead>')

        topicrefs_str = '\n'.join(topicrefs)

        return f'''<?xml version="1.0" encoding="UTF-8"?>
{self.config.map_doctype}
<map>
    <title>Linux Storage Configuration Guides</title>
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

        # Clean existing output directory to remove stale files
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
        """Convert Jekyll include files to DITA warehouse topics."""
        includes_dir = self.config.input_dir / '_includes'
        if not includes_dir.exists():
            print(f"  Warning: _includes directory not found at {includes_dir}")
            return

        for md_file in includes_dir.rglob('*.md'):
            relative_path = md_file.relative_to(includes_dir)
            include_path = str(relative_path).replace('\\', '/')

            print(f"  Converting: {include_path}")

            content = md_file.read_text(encoding='utf-8')
            dita_content = self.dita_gen.generate_warehouse_topic(include_path, content)

            # Generate output filename
            warehouse_id = 'warehouse_' + sanitize_id(include_path.replace('/', '_').replace('.md', ''))
            output_file = self.config.output_dir / self.config.warehouse_dir / f"{warehouse_id}.dita"

            output_file.write_text(dita_content, encoding='utf-8')

    def _convert_main_docs(self):
        """Convert main documentation files to DITA topics."""
        # Find all QUICKSTART, GUI-QUICKSTART, and BEST-PRACTICES files
        for pattern in ['**/QUICKSTART.md', '**/GUI-QUICKSTART.md', '**/BEST-PRACTICES.md']:
            for md_file in self.config.input_dir.glob(pattern):
                # Skip files in _includes, common, etc.
                rel_path = md_file.relative_to(self.config.input_dir)
                if str(rel_path).startswith(('_', 'common', 'scripts')):
                    continue

                self._convert_doc_file(md_file)

    def _convert_doc_file(self, md_file: Path):
        """Convert a single documentation file to DITA."""
        rel_path = md_file.relative_to(self.config.input_dir)
        rel_path_str = str(rel_path).replace('\\', '/')

        print(f"  Converting: {rel_path_str}")

        content = md_file.read_text(encoding='utf-8')

        # Extract title from YAML front matter or first heading
        title = self._extract_title(content, md_file.stem)

        # Generate topic ID
        topic_id = sanitize_id(rel_path_str.replace('/', '_').replace('.md', ''))

        # Determine topic type and generate DITA
        if 'QUICKSTART' in md_file.name:
            dita_content = self.dita_gen.generate_task_topic(title, content, topic_id)

            # Write output file
            output_file = self.config.output_dir / self.config.topics_dir / f"{topic_id}.dita"
            output_file.write_text(dita_content, encoding='utf-8')

            # Track for map generation
            self.converted_topics.append({
                'id': topic_id,
                'title': title,
                'relative_path': rel_path_str,
                'type': 'task'
            })
        else:
            # BEST-PRACTICES: Split by H2 sections into separate topics
            self._convert_best_practices_sections(md_file, content, title, topic_id, rel_path_str)

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

    def _convert_best_practices_sections(self, md_file: Path, content: str, main_title: str, base_topic_id: str, rel_path_str: str):
        """Convert BEST-PRACTICES file into multiple section topics."""
        sections = self._split_by_h2(content)

        section_topics = []

        for section_title, section_content in sections:
            # Generate section topic ID
            section_id = f"{base_topic_id}_{sanitize_id(section_title)}"

            # Generate concept topic for this section
            dita_content = self.dita_gen.generate_concept_topic(
                f"{main_title} - {section_title}",
                section_content,
                section_id
            )

            # Write output file
            output_file = self.config.output_dir / self.config.topics_dir / f"{section_id}.dita"
            output_file.write_text(dita_content, encoding='utf-8')

            section_topics.append({
                'id': section_id,
                'title': section_title,
                'relative_path': rel_path_str,
                'type': 'concept'
            })

        # Track as a parent topic with children for map generation
        self.converted_topics.append({
            'id': base_topic_id,
            'title': main_title,
            'relative_path': rel_path_str,
            'type': 'concept-parent',
            'children': section_topics
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
        """Generate the main DITA map."""
        if not self.converted_topics:
            print("  No topics to include in map")
            return

        map_content = self.map_gen.generate_main_map(self.converted_topics)
        map_file = self.config.output_dir / self.config.maps_dir / "linux-storage-guides.ditamap"
        map_file.write_text(map_content, encoding='utf-8')
        print(f"  Generated: {map_file}")


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
    python convert_to_dita.py
    python convert_to_dita.py --input-dir . --output-dir dita_output
    python convert_to_dita.py -i /path/to/docs -o /path/to/output
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
        output_dir=args.output_dir.resolve()
    )

    # Run conversion
    converter = MarkdownToDITAConverter(config)
    converter.convert()

    # Print summary
    print(f"\n📁 Output Structure:")
    print(f"   {config.output_dir}/")
    print(f"   ├── {config.warehouse_dir}/    # Reusable content (warehouse topics)")
    print(f"   ├── {config.topics_dir}/       # Main documentation topics")
    print(f"   ├── {config.images_dir}/       # Downloaded diagram images (SVG)")
    print(f"   └── {config.maps_dir}/         # DITA navigation maps")

    print(f"\n📋 Import Instructions for Heretto:")
    print(f"   1. Create a new content collection in Heretto")
    print(f"   2. Import the entire '{config.output_dir}' folder")
    print(f"   3. Or import the '{config.maps_dir}/linux-storage-guides.ditamap' file")
    print(f"   4. Ensure images folder is included for diagram rendering")
    print(f"   5. Review and publish your content")


if __name__ == '__main__':
    main()