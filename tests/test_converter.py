#!/usr/bin/env python3
"""Validation suite for scripts/convert_to_dita.py.

Runs the real converter CLI over the self-contained fixture tree in
tests/fixtures/ and asserts on the DITA it produces. Every Markdown construct
used by the guides in this repo appears in a fixture, so a converter change that
silently alters (or drops) any of them fails here.

Usage:
    python tests/test_converter.py           # all tests
    python tests/test_converter.py -v        # verbose
    python tests/test_converter.py TestTaskTopic

No third-party packages required (stdlib unittest). --skip-diagrams is always
passed, so no network access and no Kroki server are needed.

If a converter behaviour is wrong-but-deliberately-kept, name the test
`..._known_limitation` / `..._known_gap` and say why in a comment, so a later fix
is noticed rather than silently breaking a downstream expectation. There are
currently none: every limitation this suite originally documented has been fixed.
"""

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
import base64
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / 'tests' / 'fixtures'
STANDALONE = FIXTURES / 'standalone' / 'STANDALONE.md'
SCRIPT = REPO / 'scripts' / 'convert_to_dita.py'

# The canonical flag set from STYLEGUIDE.md / CLAUDE.md.
CANONICAL = ('--inline-includes', '--section-maps', '--organize-sections')

ISCSI_DIR = 'topics/testdist/iscsi'
QS = f'{ISCSI_DIR}/t_testdist_iscsi_quickstart.dita'
BP = f'{ISCSI_DIR}/c_testdist_iscsi_best-practices_'


# --------------------------------------------------------------------------
# Import the converter module directly for unit-level tests
# --------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location('convert_to_dita', SCRIPT)
conv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(conv)


# --------------------------------------------------------------------------
# Converter runs (cached per flag combination, torn down at exit)
# --------------------------------------------------------------------------

_RUNS = {}
_TMPDIRS = []


def run_converter(*flags, source=None):
    """Run the converter CLI and return its output directory (cached)."""
    key = (tuple(flags), str(source or ''))
    if key not in _RUNS:
        out = Path(tempfile.mkdtemp(prefix='dita_test_'))
        _TMPDIRS.append(out)
        cmd = [sys.executable, str(SCRIPT), '-o', str(out), '--skip-diagrams']
        cmd += list(flags)
        cmd += ['-f', str(source)] if source else ['-i', str(FIXTURES)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))
        if proc.returncode != 0:
            raise AssertionError(
                f'converter failed ({proc.returncode}) for {flags}\n'
                f'STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}')
        _RUNS[key] = out
    return _RUNS[key]


def tearDownModule():
    for d in _TMPDIRS:
        shutil.rmtree(d, ignore_errors=True)


class ConverterCase(unittest.TestCase):
    """Base class with helpers for reading and querying generated output."""

    FLAGS = CANONICAL
    SOURCE = None

    @classmethod
    def out(cls):
        return run_converter(*cls.FLAGS, source=cls.SOURCE)

    def read(self, rel):
        path = self.out() / rel
        self.assertTrue(path.is_file(), f'expected output file missing: {rel}')
        return path.read_text(encoding='utf-8')

    def tree(self, rel):
        return ET.fromstring(self.read(rel))

    def all_topics(self):
        return sorted((self.out() / 'topics').rglob('*.dita'))

    def all_maps(self):
        return sorted((self.out() / 'maps').rglob('*.ditamap'))

    def assertOrdered(self, haystack, *needles):
        """Assert the needles appear in the given order in haystack."""
        pos = -1
        for needle in needles:
            found = haystack.find(needle, pos + 1)
            self.assertNotEqual(found, -1, f'not found after previous marker: {needle!r}')
            pos = found


# ==========================================================================
# Unit tests: pure helper functions
# ==========================================================================

class TestUtilityFunctions(unittest.TestCase):

    def test_sanitize_id(self):
        self.assertEqual(conv.sanitize_id('Architecture Overview'), 'architecture_overview')
        self.assertEqual(conv.sanitize_id('nconnect Tuning'), 'nconnect_tuning')
        # Hyphens survive (topic filenames such as c_iscsi-multipath-config rely on it)
        self.assertEqual(conv.sanitize_id('iscsi-multipath-config'), 'iscsi-multipath-config')
        self.assertEqual(conv.sanitize_id('Understanding APD (All Paths Down)'),
                         'understanding_apd_all_paths_down')
        self.assertEqual(conv.sanitize_id('!!!'), 'topic')

    def test_sanitize_id_never_starts_with_a_digit(self):
        # XML NCNames may not start with a digit, and the Azure Local guides use
        # '### 1.1 ...' style subheadings.
        self.assertEqual(conv.sanitize_id('123 numeric start'), '_123_numeric_start')
        self.assertEqual(conv.sanitize_id('1.1 HBA Driver and Firmware'),
                         '_1_1_hba_driver_and_firmware')

    def test_github_slug_matches_jekyll_anchors(self):
        self.assertEqual(conv.github_slug('Understanding APD (All Paths Down) Events'),
                         'understanding-apd-all-paths-down-events')
        self.assertEqual(conv.github_slug('nconnect Tuning'), 'nconnect-tuning')
        self.assertEqual(conv.github_slug('`code` and **bold** and *italic*'),
                         'code-and-bold-and-italic')
        self.assertEqual(conv.github_slug('Step 1: Connect'), 'step-1-connect')

    def test_remove_non_ascii_uses_xml_safe_replacements(self):
        # Runs on already-escaped XML, so arrows must become entities, never raw < >
        self.assertEqual(conv.remove_non_ascii('host → array'), 'host -&gt; array')
        self.assertEqual(conv.remove_non_ascii('array ← host'), 'array &lt;- host')
        self.assertEqual(conv.remove_non_ascii('em—dash and en–dash'), 'em-dash and en-dash')
        self.assertEqual(conv.remove_non_ascii('⚠️ careful'), '[WARNING] careful')
        self.assertEqual(conv.remove_non_ascii('✅ ok ❌ no 💡 tip'), '[OK] ok [X] no [TIP] tip')
        # Anything left over is dropped rather than shipped as non-ASCII
        self.assertEqual(conv.remove_non_ascii('naive é test'), 'naive  test')

    def test_remove_step_prefix(self):
        self.assertEqual(conv.remove_step_prefix('Step 1: Verify the initiator'),
                         'Verify the initiator')
        self.assertEqual(conv.remove_step_prefix('Step 10: Ten'), 'Ten')
        self.assertEqual(conv.remove_step_prefix('step 2 Lowercase'), 'Lowercase')
        self.assertEqual(conv.remove_step_prefix('Troubleshooting'), 'Troubleshooting')

    def test_distribution_and_deployment_labels(self):
        self.assertEqual(conv.format_dist_title('rhel'), 'RHEL')
        self.assertEqual(conv.format_dist_title('azure-local'), 'Azure Local')
        self.assertEqual(conv.format_dist_title('testdist'), 'Testdist')
        self.assertEqual(conv.normalize_deployment('disagg'), 'disaggregated')
        self.assertEqual(conv.normalize_deployment('HCI'), 'hyperconverged')
        self.assertEqual(conv.normalize_deployment('s2d'), 'hyperconverged')
        self.assertEqual(conv.deployment_of('distributions/azure-local/disaggregated/fc/QUICKSTART.md'),
                         'disaggregated')
        self.assertEqual(conv.deployment_of('distributions\\azure-local\\hyperconverged\\fc\\x.md'),
                         'hyperconverged')
        self.assertEqual(conv.deployment_of('distributions/rhel/iscsi/QUICKSTART.md'), '')

    def test_collapse_consecutive_notes(self):
        lines = [
            '        <note type="note"><p>A</p></note>',
            '        <note type="note"><p>B</p></note>',
            '        <note type="warning"><p>C</p></note>',
        ]
        got = conv.collapse_consecutive_notes(lines)
        self.assertEqual(got, [
            '        <note type="note"><p>A</p><p>B</p></note>',
            '        <note type="warning"><p>C</p></note>',
        ])

    def test_collapse_consecutive_notes_leaves_separated_notes_alone(self):
        lines = [
            '        <note type="note"><p>A</p></note>',
            '        <p>prose between</p>',
            '        <note type="note"><p>B</p></note>',
        ]
        self.assertEqual(conv.collapse_consecutive_notes(lines), lines)

    def test_kroki_url_round_trips_the_mermaid_source(self):
        code = 'graph LR\n    A[Host] --> B[Array]'
        url = conv.get_kroki_url(code)
        encoded = url.rsplit('/', 1)[1]
        decoded = zlib.decompress(base64.urlsafe_b64decode(encoded)).decode('utf-8')
        self.assertEqual(decoded, code)
        self.assertIn('/mermaid/png/', url)


# ==========================================================================
# Unit tests: inline formatting
# ==========================================================================

class TestInlineFormatting(unittest.TestCase):

    def setUp(self):
        self.p = conv.MarkdownParser()

    def inline(self, text):
        return self.p.convert_inline(conv.escape_xml(text))

    def test_basic_spans(self):
        self.assertEqual(self.inline('**bold**'), '<b>bold</b>')
        self.assertEqual(self.inline('*italic*'), '<i>italic</i>')
        self.assertEqual(self.inline('`code`'), '<codeph>code</codeph>')
        self.assertEqual(self.inline('a **b** and *c* and `d`'),
                         'a <b>b</b> and <i>c</i> and <codeph>d</codeph>')

    def test_xml_escaping_precedes_inline_conversion(self):
        self.assertEqual(self.inline('`<context>`'), '<codeph>&lt;context&gt;</codeph>')
        self.assertEqual(self.inline('a < b & c > d'), 'a &lt; b &amp; c &gt; d')

    def test_code_spans_are_protected_from_emphasis(self):
        # `sd*` ... `dm-*` must not be read as one italic run spanning both spans
        got = self.inline('devices `sd*` and `dm-*` here')
        self.assertEqual(got, 'devices <codeph>sd*</codeph> and <codeph>dm-*</codeph> here')
        self.assertNotIn('<i>', got)

    def test_links(self):
        self.assertEqual(
            self.inline('[docs](https://support.everpuredata.com/bundle/x)'),
            '<xref href="https://support.everpuredata.com/bundle/x" format="html" '
            'scope="external">docs</xref>')

    def test_nested_emphasis_converts_both_levels(self):
        self.assertEqual(self.inline('**bold with *italic* inside**'),
                         '<b>bold with <i>italic</i> inside</b>')
        self.assertEqual(self.inline('*italic with **bold** inside*'),
                         '<i>italic with <b>bold</b> inside</i>')

    def test_adjacent_bold_spans_stay_separate(self):
        # The bold pattern is non-greedy, so two spans must not merge into one
        self.assertEqual(self.inline('**one** and **two**'),
                         '<b>one</b> and <b>two</b>')
        self.assertEqual(self.inline('a **b** c *d* e **f**'),
                         'a <b>b</b> c <i>d</i> e <b>f</b>')

    def test_bold_span_wrapping_across_source_lines(self):
        # Blockquote lines are newline-joined before conversion, and authored bold
        # spans routinely wrap. A bold pattern that cannot cross a newline leaves
        # the markers behind and lets the italic pass chew them into stray '*'.
        self.assertEqual(self.inline('**bold across\ntwo lines** tail'),
                         '<b>bold across\ntwo lines</b> tail')
        self.assertEqual(self.inline('**wrapped with *italic*\ninside** tail'),
                         '<b>wrapped with <i>italic</i>\ninside</b> tail')

    def test_unpaired_bold_marker_is_left_alone(self):
        self.assertEqual(self.inline('**bold** and a stray **'),
                         '<b>bold</b> and a stray **')


# ==========================================================================
# Unit tests: notes
# ==========================================================================

class TestNoteTypes(unittest.TestCase):

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def detect(self, text):
        return self.g._detect_note_type(text)

    def strip(self, text):
        return self.g._strip_note_prefix(text, self.detect(text))

    def test_note_type_detection(self):
        self.assertEqual(self.detect('**Warning:** boom'), 'warning')
        self.assertEqual(self.detect('⚠️ careful'), 'warning')
        self.assertEqual(self.detect('**Important:** read this'), 'important')
        self.assertEqual(self.detect('**Caution:** slow down'), 'caution')
        self.assertEqual(self.detect('**Tip:** try this'), 'tip')
        self.assertEqual(self.detect('just some prose'), 'note')

    def test_disclaimers_are_important_even_when_emoji_decorated(self):
        # STYLEGUIDE.md: the disclaimer lands in <prereq> as an important note
        self.assertEqual(self.detect('**⚠️ Important Disclaimer:** x'), 'important')
        self.assertEqual(self.detect('**Vendor Documentation Priority:** x'), 'important')
        # A plain warning emoji with no disclaimer wording is still a warning
        self.assertEqual(self.detect('⚠️ careful'), 'warning')

    def test_prefix_stripping(self):
        self.assertEqual(self.strip('**Warning:** boom'), 'boom')
        self.assertEqual(self.strip('Warning: boom'), 'boom')
        self.assertEqual(self.strip('[WARNING] boom'), 'boom')
        self.assertEqual(self.strip('**[IMPORTANT]:** read this'), 'read this')
        self.assertEqual(self.strip('**Important Note:** read this'), 'read this')
        self.assertEqual(self.strip('⚠️ careful now'), 'careful now')
        self.assertEqual(self.strip('📖 See also'), 'See also')
        self.assertEqual(self.strip('**Tip:** try this'), 'try this')
        # Nothing to strip: content survives untouched
        self.assertEqual(self.strip('just some prose'), 'just some prose')


# ==========================================================================
# Unit tests: block generators
# ==========================================================================

class TestTableGeneration(unittest.TestCase):

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def test_table_shape_and_inline_markup(self):
        md = '| Setting | Value |\n| `a.b.c` | **60** |'
        got = self.g._generate_table(md)
        self.assertIn('<tgroup cols="2">', got)
        self.assertIn('<thead>', got)
        self.assertIn('<entry>Setting</entry>', got)
        self.assertIn('<entry><codeph>a.b.c</codeph></entry>', got)
        self.assertIn('<entry><b>60</b></entry>', got)
        self.assertOrder(got, '<thead>', '</thead>', '<tbody>', '</tbody>')

    def assertOrder(self, hay, *needles):
        pos = -1
        for n in needles:
            i = hay.find(n, pos + 1)
            self.assertNotEqual(i, -1, n)
            pos = i

    def test_rows_with_wrong_column_count_are_dropped(self):
        md = '| A | B | C |\n| 1 | 2 | 3 |\n| short | row |'
        got = self.g._generate_table(md)
        self.assertIn('<entry>1</entry>', got)
        self.assertNotIn('short', got)


class TestListGeneration(unittest.TestCase):

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def test_unordered_list_wraps_items_in_p(self):
        got = self.g._generate_ul(['one', 'two'])
        self.assertIn('<li><p>one</p></li>', got)
        self.assertTrue(got.strip().startswith('<ul>'))
        self.assertTrue(got.strip().endswith('</ul>'))

    def test_ordered_list_with_bullet_sublist(self):
        nested = [[conv.NestedListItem(depth=3, ordered=False, text='why')], []]
        got = self.g._generate_ol(['main', 'second'], nested_items=nested)
        self.assertIn('<ol>', got)
        self.assertIn('<ul>', got)
        self.assertIn('<li><p>why</p></li>', got)
        self.assertIn('<li><p>second</p></li>', got)

    def test_numbered_sublist_renders_as_ol(self):
        nested = [[conv.NestedListItem(depth=3, ordered=True, text='sub')]]
        got = self.g._generate_ol(['main'], nested_items=nested)
        # The sublist tag follows the marker that was authored
        self.assertRegex(got, r'<li><p>main</p>\s*<ol>')

    def test_three_level_sublist_nesting(self):
        nested = [[
            conv.NestedListItem(depth=3, ordered=False, text='level two'),
            conv.NestedListItem(depth=6, ordered=False, text='level three'),
        ]]
        got = self.g._generate_ol(['level one'], nested_items=nested)
        self.assertEqual(got.count('<ul>'), 2)
        self.assertEqual(got.count('</ul>'), 2)
        self.assertOrder(got, 'level one', 'level two', 'level three')

    def test_plain_strings_are_accepted_as_sublist_items(self):
        got = self.g._generate_ol(['main'], nested_items=[['legacy string']])
        self.assertIn('<li><p>legacy string</p></li>', got)

    def assertOrder(self, hay, *needles):
        pos = -1
        for n in needles:
            i = hay.find(n, pos + 1)
            self.assertNotEqual(i, -1, n)
            pos = i


# ==========================================================================
# Unit tests: parser block detection
# ==========================================================================

class TestParser(unittest.TestCase):

    def setUp(self):
        self.p = conv.MarkdownParser()

    def types(self, md):
        return [e.type for e in self.p.parse(md)]

    def test_front_matter_is_stripped(self):
        els = self.p.parse('---\nlayout: default\ntitle: X\n---\n# Title\n')
        self.assertEqual([e.type for e in els], ['heading'])
        self.assertEqual(els[0].content, 'Title')

    def test_raw_liquid_markers_are_dropped_but_template_text_survives(self):
        md = "{% raw %}\n```bash\necho '{{index .data \"tls.crt\"}}'\n```\n{% endraw %}\n"
        els = self.p.parse(md)
        self.assertEqual([e.type for e in els], ['code_block'])
        self.assertIn('{{index .data "tls.crt"}}', els[0].content)

    def test_horizontal_rules_are_skipped(self):
        self.assertEqual(self.types('---\n\nText\n'), ['paragraph'])

    def test_paragraph_lines_are_joined_and_stripped(self):
        els = self.p.parse('First line\n    second line\n')
        self.assertEqual(els[0].content, 'First line second line')

    def test_wrapped_list_item_is_folded_back(self):
        els = self.p.parse('- item that wraps\n  onto a second line\n- second item\n')
        self.assertEqual(els[0].type, 'unordered_list')
        self.assertEqual(els[0].items, ['item that wraps onto a second line', 'second item'])

    def test_ordered_list_collects_nested_items(self):
        els = self.p.parse('1. one\n   - sub a\n   - sub b\n2. two\n')
        self.assertEqual(els[0].type, 'ordered_list_nested')
        self.assertEqual(els[0].items, ['one', 'two'])
        self.assertEqual([n.text for n in els[0].children[0].items], ['sub a', 'sub b'])
        self.assertEqual(els[0].children[1].items, [])

    def test_code_fence_language_is_captured(self):
        els = self.p.parse('```mermaid\ngraph LR\n```\n')
        self.assertEqual(els[0].type, 'code_block')
        self.assertEqual(els[0].language, 'mermaid')

    def test_table_separator_row_is_dropped(self):
        els = self.p.parse('| A | B |\n|---|---|\n| 1 | 2 |\n')
        self.assertEqual(els[0].type, 'table')
        self.assertNotIn('---', els[0].content)

    def test_blockquote_becomes_note_element(self):
        els = self.p.parse('> **Warning:** boom\n> second line\n')
        self.assertEqual(els[0].type, 'note')
        self.assertEqual(els[0].content, '**Warning:** boom\nsecond line')

    def test_standalone_image_line_becomes_image_element(self):
        els = self.p.parse('![Alt text](img/x.png)\n')
        self.assertEqual(els[0].type, 'image')
        self.assertEqual(els[0].content, 'img/x.png')
        self.assertEqual(els[0].language, 'Alt text')

    def test_indented_code_fence_under_a_list_item_is_a_code_block(self):
        els = self.p.parse('- bullet\n  ```bash\n  echo hi\n  ```\n')
        self.assertEqual([e.type for e in els], ['unordered_list', 'code_block'])
        self.assertEqual(els[1].language, 'bash')
        # The fence's own indentation is removed: <codeblock> is preformatted
        self.assertEqual(els[1].content, 'echo hi')

    def test_indented_fence_keeps_relative_indentation_inside_the_block(self):
        els = self.p.parse('1. step\n   ```yaml\n   a:\n     b: 1\n   ```\n')
        block = [e for e in els if e.type == 'code_block'][0]
        self.assertEqual(block.content, 'a:\n  b: 1')


class TestTaskBodyRouting(unittest.TestCase):
    """H2 routing rules in _elements_to_task_body, exercised on small inputs."""

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def body(self, md):
        return self.g._elements_to_task_body(self.g.parser.parse(md), 't_x')

    def test_h3_steps_under_an_h2_wrapper_collapse_to_one_step(self):
        # CLAUDE.md: nesting steps under "## Step-by-Step Instructions" collapses
        # the whole procedure into a single DITA step. Locked in deliberately.
        got = self.body('## Step-by-Step Instructions\n\n'
                        '### Step 1: First\n\nA\n\n### Step 2: Second\n\nB\n')
        self.assertEqual(got.count('<step>'), 1)
        self.assertIn('<p><b>Step 1: First</b></p>', got)

    def test_h2_steps_produce_one_step_each(self):
        got = self.body('## Step 1: First\n\nA\n\n## Step 2: Second\n\nB\n')
        self.assertEqual(got.count('<step>'), 2)
        self.assertIn('<cmd>First</cmd>', got)
        self.assertIn('<cmd>Second</cmd>', got)

    def test_taskbody_child_order_is_enforced_regardless_of_source_order(self):
        # Next Steps authored before the prerequisites still lands last
        got = self.body('Intro prose\n\n## Next Steps\n\n- later\n\n'
                        '## Prerequisites\n\n- first\n\n## Step 1: Go\n\nA\n')
        self.assertOrder(got, '<prereq>', '<context>', '<steps>', '<postreq>')

    def test_next_steps_bullets_become_dash_paragraphs(self):
        got = self.body('## Next Steps\n\n- one\n- two\n')
        self.assertIn('<p>- one</p>', got)
        self.assertIn('<p>- two</p>', got)

    def assertOrder(self, hay, *needles):
        pos = -1
        for n in needles:
            i = hay.find(n, pos + 1)
            self.assertNotEqual(i, -1, f'{n} missing or out of order')
            pos = i


class TestSplitByH2(unittest.TestCase):

    def setUp(self):
        self.c = conv.MarkdownToDITAConverter(conv.ConversionConfig())

    def test_sections_split_on_h2_and_toc_is_skipped(self):
        md = ('---\ntitle: T\n---\n\n# Doc\n\nintro\n\n'
              '## Table of Contents\n\n- x\n\n## Alpha\n\nA\n\n## Beta\n\nB\n')
        got = self.c._split_by_h2(md)
        self.assertEqual([t for t, _ in got], ['Alpha', 'Beta'])
        # The intro is carried into the first kept section; the TOC section is not
        self.assertEqual(got[0][1], 'intro\n\nA')
        self.assertEqual(got[1][1], 'B')

    def test_content_without_h2_becomes_a_single_overview_section(self):
        got = self.c._split_by_h2('# Doc\n\nBody only.\n')
        self.assertEqual([t for t, _ in got], ['Overview'])

    def test_intro_before_first_h2_is_prepended_to_the_first_section(self):
        got = self.c._split_by_h2('# Doc\n\nMARKER_INTRO\n\n## Alpha\n\nA\n')
        self.assertEqual([t for t, _ in got], ['Alpha'])
        self.assertEqual(got[0][1], 'MARKER_INTRO\n\nA')

    def test_h1_title_is_not_mistaken_for_intro_prose(self):
        # Front matter removal leaves a newline before the H1, so the H1 strip has
        # to tolerate leading whitespace or the title text leaks into the body.
        got = self.c._split_by_h2('---\ntitle: T\n---\n\n# Doc Title\n\n## Alpha\n\nA\n')
        self.assertNotIn('Doc Title', got[0][1])

    def test_a_preamble_of_only_horizontal_rules_is_ignored(self):
        got = self.c._split_by_h2('# Doc\n\n---\n\n## Alpha\n\nA\n')
        self.assertEqual(got[0][1], 'A')


class TestChooseSectionLevel(unittest.TestCase):

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def test_prefers_shallowest_repeating_level(self):
        self.assertEqual(self.g._choose_section_level([3, 4, 4, 6]), 4)
        self.assertEqual(self.g._choose_section_level([3, 3, 4, 4]), 3)

    def test_falls_back_to_shallowest_when_nothing_repeats(self):
        self.assertEqual(self.g._choose_section_level([3, 4, 5]), 3)

    def test_returns_none_without_headings(self):
        self.assertIsNone(self.g._choose_section_level([]))


class TestImagePathDepth(unittest.TestCase):

    def setUp(self):
        self.g = conv.DITAGenerator(conv.ConversionConfig())

    def test_hop_count_tracks_topic_nesting(self):
        self.g.set_topic_subdir('')
        self.assertEqual(self.g._resolve_image_path('img/x.png'), '../images/x.png')
        self.g.set_topic_subdir('testdist/iscsi')
        self.assertEqual(self.g._resolve_image_path('img/x.png'), '../../../images/x.png')
        self.g.set_topic_subdir('testlocal/disaggregated/fc')
        self.assertEqual(self.g._resolve_image_path('img/x.png'), '../../../../images/x.png')

    def test_external_images_are_referenced_in_place(self):
        self.assertEqual(self.g._resolve_image_ref('https://example.com/a.png'),
                         ('https://example.com/a.png', 'external'))
        href, scope = self.g._resolve_image_ref('img/a.png')
        self.assertEqual(scope, 'local')


# ==========================================================================
# Integration: QUICKSTART -> task topic (canonical flags)
# ==========================================================================

class TestTaskTopic(ConverterCase):

    def setUp(self):
        self.qs = self.read(QS)

    def test_task_topic_skeleton(self):
        self.assertIn('<!DOCTYPE task PUBLIC', self.qs)
        self.assertIn('<task id="t_testdist_iscsi_quickstart" xml:lang="en-US">', self.qs)
        self.assertIn('<title>Testdist iSCSI Converter Fixture</title>', self.qs)
        self.assertIn('<prolog>', self.qs)
        self.assertIn('<metadata/>', self.qs)

    def test_title_comes_from_front_matter(self):
        self.assertIn('<title>Testdist iSCSI Converter Fixture</title>', self.qs)

    def test_taskbody_child_order(self):
        self.assertOrdered(self.qs, '<prereq>', '<context>', '<steps>', '<postreq>')

    def test_context_holds_only_pre_h2_content(self):
        context = self.qs.split('<context>')[1].split('</context>')[0]
        self.assertIn('MARKER_CONTEXT_PARAGRAPH', context)
        self.assertIn('MARKER_CONTEXT_BULLET one', context)
        self.assertIn('MARKER_CONTEXT_CODE', context)
        self.assertNotIn('MARKER_OVERVIEW_PARAGRAPH', context)

    def test_paragraph_continuation_joins_source_lines(self):
        self.assertIn('so it must land in <codeph>&lt;context&gt;</codeph> - and this '
                      'second source line must join the same paragraph.', self.qs)

    def test_prereq_contains_flattened_list_and_notes(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertIn('<li><p>MARKER_PREREQ_ONE', prereq)
        # H3 subheading under Prerequisites is dropped, its bullets are flattened up
        self.assertIn('MARKER_PREREQ_H3_ITEM', prereq)
        self.assertNotIn('Additional Requirements', prereq)
        # Wrapped bullet folded into one item
        self.assertIn('MARKER_PREREQ_TWO that wraps across two source lines and '
                      'therefore has to be folded back into a single list item', prereq)
        # Notes come after the <ul>, never inside it
        self.assertOrdered(prereq, '</ul>', 'MARKER_PREREQ_NOTE')

    def test_disclaimer_include_lands_in_prereq(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertIn('MARKER_DISCLAIMER_NOTE', prereq)

    def test_vendor_documentation_priority_note_is_hoisted_to_prereq(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertIn('MARKER_VENDOR_PRIORITY_NOTE', prereq)
        steps = self.qs.split('<steps>')[1].split('</steps>')[0]
        self.assertNotIn('MARKER_VENDOR_PRIORITY_NOTE', steps)

    def test_important_h2_routes_notes_to_prereq(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertIn('MARKER_IMPORTANT_SECTION_NOTE', prereq)

    def test_prose_in_an_important_h2_is_kept_in_prereq(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertIn('MARKER_IMPORTANT_SECTION_PARAGRAPH', prereq)

    def test_prereq_prose_before_the_list_precedes_the_ul(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertOrdered(prereq, 'MARKER_PREREQ_INTRO_PARAGRAPH', '<ul>')

    def test_prereq_code_block_after_the_list_is_kept(self):
        prereq = self.qs.split('<prereq>')[1].split('</prereq>')[0]
        self.assertOrdered(prereq, '</ul>',
                           '<codeblock>echo "MARKER_PREREQ_CODE_AFTER_LIST"</codeblock>')

    def test_every_h2_becomes_a_step_including_overview_and_troubleshooting(self):
        for cmd in ('<cmd>Overview</cmd>', '<cmd>Background</cmd>',
                    '<cmd>Troubleshooting</cmd>', '<cmd>Additional Notes</cmd>',
                    '<cmd>Related Articles</cmd>'):
            self.assertIn(cmd, self.qs)

    def test_step_prefix_is_stripped_from_cmd(self):
        self.assertIn('<cmd>Verify the initiator</cmd>', self.qs)
        self.assertNotIn('<cmd>Step 1:', self.qs)

    def test_h3_inside_a_step_becomes_a_bold_paragraph(self):
        self.assertIn('<p><b>Subheading Inside A Step</b></p>', self.qs)

    def test_inline_formatting_in_a_step(self):
        self.assertIn('MARKER_OVERVIEW_PARAGRAPH with <b>bold</b>, <i>italic</i>, '
                      '<codeph>codeph</codeph>', self.qs)

    def test_code_block_becomes_codeblock_preserving_newlines(self):
        self.assertIn('<codeblock>sudo systemctl start iscsid\n'
                      'iscsiadm -m session -P 3</codeblock>', self.qs)

    def test_table_inside_a_step_is_emitted(self):
        step = self.qs.split('<cmd>Verify the initiator</cmd>')[1].split('</step>')[0]
        self.assertIn('<tgroup cols="3">', step)
        self.assertIn('<entry>MARKER_STEP1_TABLE_CELL</entry>', step)
        self.assertIn('<entry><codeph>node.session.timeo.replacement_timeout</codeph></entry>', step)
        self.assertNotIn('Broken row', step)

    def test_nested_ordered_list_structure(self):
        step = self.qs.split('<cmd>Configure multipath</cmd>')[1].split('</step>')[0]
        self.assertOrdered(
            step,
            '<ol>',
            '<li><p><b>Discover the portal</b>',
            '<ul>', '<li><p><i>Why</i>: MARKER_NESTED_WHY_ONE</p></li>',
            'MARKER_NESTED_SECOND_BULLET', '</ul>',
            '<li><p><b>Log in to all portals</b>',
            '<ol>', 'MARKER_NESTED_ORDERED_SUB',
            '<ul>', 'MARKER_NESTED_DEEP_BULLET', '</ul>', '</ol>',
            '<li><p>Plain third item with no sublist</p></li>',
        )

    def test_note_types_and_prefix_stripping_in_steps(self):
        for note_type, marker in (('warning', 'MARKER_WARNING_ONE'),
                                  ('warning', 'MARKER_WARNING_TWO'),
                                  ('caution', 'MARKER_CAUTION_NOTE'),
                                  ('tip', 'MARKER_TIP_NOTE'),
                                  ('note', 'MARKER_PLAIN_NOTE')):
            self.assertIn(f'<note type="{note_type}"><p>{marker}', self.qs)
        # The redundant authored label is gone, DITA supplies it
        self.assertNotIn('<p>**Warning:**', self.qs)
        self.assertNotIn('Warning:</p>', self.qs)

    def test_consecutive_notes_are_not_collapsed_in_task_steps(self):
        # collapse_consecutive_notes runs on concept bodies only
        step = self.qs.split('<cmd>Configure multipath</cmd>')[1].split('</step>')[0]
        self.assertIn('MARKER_WARNING_ONE', step)
        self.assertIn('MARKER_WARNING_TWO', step)
        self.assertEqual(step.count('<note type="warning">'), 2)

    def test_images_get_depth_correct_local_hrefs(self):
        self.assertIn('<image href="../../../images/test%20screenshot.png" scope="local">'
                      '<alt>Test screenshot</alt></image>', self.qs)
        self.assertIn('<image href="../../../images/diagram.png" scope="local">', self.qs)

    def test_external_image_keeps_its_url_and_external_scope(self):
        self.assertIn('<image href="https://example.com/remote.png" scope="external">', self.qs)

    def test_mermaid_placeholder_with_skip_diagrams(self):
        self.assertIn('<!-- Mermaid diagram 1 (skipped) -->', self.qs)

    def test_raw_liquid_markers_are_stripped_and_template_survives(self):
        self.assertIn("""<codeblock>oc get secret test-secret -o """
                      """go-template='{{index .data "tls.crt"}}'</codeblock>""", self.qs)
        self.assertNotIn('{% raw %}', self.qs)
        self.assertNotIn('{% endraw %}', self.qs)

    def test_include_is_inlined_including_nested_include(self):
        self.assertIn('MARKER_OUTER_INCLUDE paragraph with <b>bold</b>', self.qs)
        self.assertIn('MARKER_OUTER_INCLUDE_CODE', self.qs)
        self.assertIn('<entry>MARKER_INCLUDE_CELL</entry>', self.qs)
        self.assertIn('<note type="tip"><p>MARKER_OUTER_INCLUDE_TIP.</p></note>', self.qs)
        self.assertIn('MARKER_INNER_INCLUDE', self.qs)
        self.assertNotIn('{% include', self.qs)

    def test_include_headings_become_bold_paragraphs_in_a_task(self):
        self.assertIn('<p><b>Outer Include Heading</b></p>', self.qs)
        self.assertIn('<p><b>Inner Include Heading</b></p>', self.qs)

    def test_postreq_holds_next_steps_content(self):
        postreq = self.qs.split('<postreq>')[1].split('</postreq>')[0]
        self.assertIn('<p>MARKER_POSTREQ_PARAGRAPH.</p>', postreq)
        self.assertIn('<p>- MARKER_POSTREQ_BULLET_ONE</p>', postreq)
        self.assertIn('<note type="tip"><p>MARKER_POSTREQ_NOTE.</p></note>', postreq)

    def test_unicode_is_replaced_with_ascii_equivalents(self):
        self.assertIn('host -&gt; array, an em-dash, "smart quotes", and a [WARNING] emoji',
                      self.qs)

    def test_indented_fence_under_a_bullet_becomes_a_codeblock(self):
        self.assertIn('<codeblock>echo "MARKER_FENCE_AFTER_LIST"</codeblock>', self.qs)
        self.assertNotIn('<codeph>bash', self.qs)

    def test_nested_emphasis_survives_end_to_end(self):
        self.assertIn('<b>MARKER_NESTED_EMPHASIS is bold with <i>italic</i> inside</b>',
                      self.qs)
        self.assertIn('<i>italic with <b>bold</b> inside</i>', self.qs)

    def test_bold_wrapping_across_source_lines_closes_in_a_note(self):
        # Blockquote lines are newline-joined, so the newline survives inside <p>
        self.assertIn('<note type="note"><p><b>MARKER_WRAPPED_BOLD spans two source '
                      'lines and contains an <i>italic</i> run, and\nmust still close.'
                      '</b> Trailing prose after the bold span.</p></note>', self.qs)
        # No orphaned emphasis markers anywhere in the topic
        self.assertNotRegex(self.qs, r'(?<![\w*])\*(?![\w*])')


# ==========================================================================
# Integration: cross-reference resolution
# ==========================================================================

class TestCrossReferences(ConverterCase):

    def setUp(self):
        self.qs = self.read(QS)

    def test_sibling_protocol_link(self):
        self.assertIn('<xref href="../nvme-tcp/t_testdist_nvme-tcp_quickstart.dita" '
                      'format="dita" scope="local">sibling protocol guide</xref>', self.qs)

    def test_anchor_into_split_best_practices_selects_the_right_topic(self):
        self.assertIn('<xref href="c_testdist_iscsi_best-practices_performance_tuning.dita" '
                      'format="dita" scope="local">Best Practices anchor</xref>', self.qs)

    def test_h3_anchor_carries_the_sanitized_dita_id(self):
        self.assertIn('href="c_testdist_iscsi_best-practices_performance_tuning.dita'
                      '#nconnect_tuning"', self.qs)

    def test_mixed_case_anchor_is_slugified_before_lookup(self):
        self.assertIn('<xref href="c_testdist_iscsi_best-practices_performance_tuning.dita'
                      '#queue_depth" format="dita" scope="local">'
                      'Best Practices mixed-case anchor</xref>', self.qs)

    def test_anchor_to_a_punctuated_heading_resolves(self):
        self.assertIn('<xref href="c_testdist_iscsi_best-practices_performance_tuning.dita'
                      '#understanding_apd_all_paths_down" format="dita" scope="local">'
                      'Best Practices punctuated anchor</xref>', self.qs)

    def test_link_without_anchor_lands_on_the_first_section_topic(self):
        self.assertIn('<xref href="c_testdist_iscsi_best-practices_architecture_overview.dita" '
                      'format="dita" scope="local">Best Practices, no anchor</xref>', self.qs)

    def test_anchor_into_a_quickstart_drops_the_unusable_id(self):
        # A QUICKSTART is one topic with no per-heading ids, so the anchor is dropped
        self.assertIn('<xref href="../nvme-tcp/t_testdist_nvme-tcp_quickstart.dita" '
                      'format="dita" scope="local">Sibling quickstart anchor</xref>', self.qs)
        self.assertNotIn('#step-1-connect', self.qs)

    def test_jekyll_html_link_resolves_to_the_reference_topic(self):
        self.assertIn('<xref href="../../common/c_glossary.dita" format="dita" '
                      'scope="local">Glossary via Jekyll html</xref>', self.qs)
        self.assertNotIn('site.baseurl', self.qs)

    def test_external_links_are_html_scope_external(self):
        self.assertIn('<xref href="https://support.everpuredata.com/bundle/other" '
                      'format="html" scope="external">External support article</xref>', self.qs)

    def test_unregistered_md_target_falls_back_to_a_dita_rewrite(self):
        self.assertIn('<xref href="../../../README.dita"', self.qs)

    def test_bare_include_relative_link_resolves_by_basename(self):
        # 'iscsi-multipath-config.md' authored inside an include is correct relative
        # to _includes/, and must still resolve after inlining.
        self.assertIn('<xref href="../../common/c_iscsi-multipath-config.dita"', self.qs)

    def test_every_local_dita_xref_resolves_on_disk(self):
        known_dangling = {'../../../README.dita'}  # source is not a converted guide
        unresolved = []
        for topic in self.all_topics():
            text = topic.read_text(encoding='utf-8')
            for href in re.findall(r'<xref href="([^"]+)" format="dita"', text):
                if href in known_dangling:
                    continue
                target = (topic.parent / href.split('#', 1)[0]).resolve()
                if not target.is_file():
                    unresolved.append(f'{topic.name} -> {href}')
        self.assertEqual(unresolved, [])

    def test_anchors_in_local_dita_xrefs_exist_in_the_target_topic(self):
        missing = []
        for topic in self.all_topics():
            text = topic.read_text(encoding='utf-8')
            for href in re.findall(r'<xref href="([^"]+#[^"]+)" format="dita"', text):
                path, anchor = href.split('#', 1)
                target = (topic.parent / path).resolve()
                if not target.is_file():
                    continue
                if f'id="{anchor}"' not in target.read_text(encoding='utf-8'):
                    missing.append(f'{topic.name} -> {href}')
        self.assertEqual(missing, [])


# ==========================================================================
# Integration: BEST-PRACTICES -> concept topics
# ==========================================================================

class TestConceptTopics(ConverterCase):

    def test_one_topic_per_h2_section(self):
        names = {p.name for p in (self.out() / ISCSI_DIR).glob('c_*.dita')}
        self.assertEqual(names, {
            'c_testdist_iscsi_best-practices_architecture_overview.dita',
            'c_testdist_iscsi_best-practices_performance_tuning.dita',
            'c_testdist_iscsi_best-practices_deep_heading_levels.dita',
            'c_testdist_iscsi_best-practices_notes_handling.dita',
            'c_testdist_iscsi_best-practices_quick_reference.dita',
            'c_testdist_iscsi_best-practices_additional_resources.dita',
        })

    def test_concept_skeleton(self):
        text = self.read(BP + 'architecture_overview.dita')
        self.assertIn('<!DOCTYPE concept PUBLIC', text)
        self.assertIn('<concept id="c_testdist_iscsi_best-practices_architecture_overview" '
                      'xml:lang="en-US">', text)
        self.assertIn('<conbody>', text)

    def test_first_architecture_section_uses_the_document_title(self):
        self.assertIn('<title>Testdist iSCSI Best Practices Fixture</title>',
                      self.read(BP + 'architecture_overview.dita'))

    def test_other_sections_are_titled_document_dash_section(self):
        self.assertIn('<title>Testdist iSCSI Best Practices Fixture - Performance Tuning</title>',
                      self.read(BP + 'performance_tuning.dita'))

    def test_troubleshooting_section_is_excluded_entirely(self):
        self.assertFalse((self.out() / (BP + 'troubleshooting.dita')).exists())
        blob = ''.join(p.read_text(encoding='utf-8') for p in self.all_topics())
        self.assertNotIn('MARKER_BP_TROUBLESHOOTING_BODY', blob)

    def test_table_of_contents_section_is_excluded(self):
        blob = ''.join(p.read_text(encoding='utf-8') for p in self.all_topics())
        self.assertNotIn('MARKER_BP_TOC_ITEM', blob)

    def test_intro_before_first_h2_lands_in_the_first_section_topic(self):
        text = self.read(BP + 'architecture_overview.dita')
        self.assertOrdered(text, '<conbody>', 'MARKER_BP_INTRO_BEFORE_FIRST_H2',
                           'MARKER_BP_ARCH_PARAGRAPH')

    def test_numbered_subheading_gets_a_legal_ncname_id(self):
        text = self.read(BP + 'performance_tuning.dita')
        self.assertIn('<section id="_1_1_numbered_subheading">', text)
        self.assertIn('MARKER_BP_NUMBERED_HEADING', text)

    def test_h3_subsections_become_sections_with_ids(self):
        text = self.read(BP + 'architecture_overview.dita')
        self.assertIn('<section id="path_layout">', text)
        self.assertIn('<title>Path Layout</title>', text)
        self.assertIn('<section id="redundancy_model">', text)
        self.assertIn('MARKER_BP_SUBSECTION_A', text)

    def test_content_before_the_first_subsection_stays_in_conbody(self):
        text = self.read(BP + 'architecture_overview.dita')
        self.assertOrdered(text, '<conbody>', 'MARKER_BP_ARCH_PARAGRAPH',
                           '<table>', '<section id="path_layout">')

    def test_mermaid_and_tables_inside_a_concept(self):
        text = self.read(BP + 'architecture_overview.dita')
        self.assertIn('<!-- Mermaid diagram 1 (skipped) -->', text)
        self.assertIn('<entry>MARKER_BP_TABLE_CELL</entry>', text)

    def test_include_headings_are_demoted_by_nesting_depth(self):
        # The include's H3 sits below the host guide's H3 sections, so it renders as
        # a bold lead-in inside the last section rather than opening a new one.
        text = self.read(BP + 'architecture_overview.dita')
        self.assertIn('<p><b>Outer Include Heading</b></p>', text)
        self.assertNotIn('<section id="outer_include_heading">', text)
        self.assertOrdered(text, '<section id="redundancy_model">',
                           '<p><b>Outer Include Heading</b></p>', '</section>')

    def test_lone_wrapper_heading_becomes_bold_and_h4s_become_sections(self):
        text = self.read(BP + 'deep_heading_levels.dita')
        self.assertIn('<p><b>Lone Wrapper Heading</b></p>', text)
        self.assertIn('<section id="wrapped_one">', text)
        self.assertIn('<section id="wrapped_two">', text)
        self.assertOrdered(text, '<p><b>Lone Wrapper Heading</b></p>',
                           '<section id="wrapped_one">')

    def test_consecutive_same_type_notes_collapse_in_a_concept(self):
        text = self.read(BP + 'notes_handling.dita')
        self.assertIn('<note type="note"><p>MARKER_BP_NOTE_A.</p>'
                      '<p>MARKER_BP_NOTE_B.</p></note>', text)
        self.assertEqual(text.count('<note type="note">'), 1)
        self.assertIn('<note type="warning"><p>MARKER_BP_WARNING.</p></note>', text)

    def test_quick_reference_subsection_is_wrapped_in_a_tip_note(self):
        text = self.read(BP + 'performance_tuning.dita')
        self.assertIn('<note type="tip">', text)
        self.assertIn('<p><b>Quick Reference</b></p>', text)
        self.assertIn('MARKER_BP_INLINE_QUICKREF', text)
        self.assertNotIn('<section id="quick_reference">', text)

    def test_reference_topics_are_emitted_into_topics_common(self):
        text = self.read('topics/common/c_glossary.dita')
        self.assertIn('<title>Storage Terminology Glossary</title>', text)
        self.assertIn('MARKER_GLOSSARY_IQN', text)
        self.assertTrue((self.out() / 'topics/common/c_iscsi-multipath-config.dita').is_file())


# ==========================================================================
# Integration: maps
# ==========================================================================

class TestMaps(ConverterCase):

    def test_expected_maps_are_generated(self):
        names = {p.name for p in self.all_maps()}
        self.assertEqual(names, {
            'linux-storage-guides.ditamap',
            'testdist-iscsi.ditamap',
            'testdist-iscsi-best-practices.ditamap',
            'testdist-nvme-tcp.ditamap',
            'testlocal-disaggregated-fc.ditamap',
        })

    def test_map_hrefs_are_collection_root_relative_and_resolve(self):
        # CLAUDE.md: hrefs are relative to the imported collection root, not maps/
        unresolved = []
        for m in self.all_maps():
            for href in re.findall(r'href="([^"]+)"', m.read_text(encoding='utf-8')):
                self.assertTrue(href.startswith('topics/'),
                                f'{m.name}: href not collection-root relative: {href}')
                if not (self.out() / href).is_file():
                    unresolved.append(f'{m.name} -> {href}')
        self.assertEqual(unresolved, [])

    def test_main_map_groups_by_distribution_then_protocol(self):
        text = self.read('maps/linux-storage-guides.ditamap')
        self.assertIn('<map xml:lang="en-US">', text)
        self.assertOrdered(text, '<topichead navtitle="Testdist">',
                           '<topichead navtitle="iSCSI">',
                           'topics/testdist/iscsi/t_testdist_iscsi_quickstart.dita')
        self.assertIn('<topichead navtitle="NVMe-TCP">', text)
        self.assertIn('<topichead navtitle="Common Resources">', text)

    def test_main_map_nests_deployment_between_distribution_and_protocol(self):
        text = self.read('maps/linux-storage-guides.ditamap')
        self.assertOrdered(text, '<topichead navtitle="Testlocal">',
                           '<topichead navtitle="Disaggregated">',
                           '<topichead navtitle="FC">',
                           'topics/testlocal/disaggregated/fc/')

    def test_best_practices_children_are_nested_under_a_topichead(self):
        text = self.read('maps/linux-storage-guides.ditamap')
        self.assertOrdered(text, '<topichead navtitle="Best Practices">',
                           'c_testdist_iscsi_best-practices_architecture_overview.dita',
                           '</topichead>')

    def test_section_map_titles_use_display_labels(self):
        self.assertIn('<title>Testdist iSCSI Storage Guide</title>',
                      self.read('maps/testdist-iscsi.ditamap'))
        self.assertIn('<title>Testdist NVMe-TCP Storage Guide</title>',
                      self.read('maps/testdist-nvme-tcp.ditamap'))
        self.assertIn('<title>Testlocal Disaggregated FC Storage Guide</title>',
                      self.read('maps/testlocal-disaggregated-fc.ditamap'))

    def test_best_practices_map_puts_architecture_at_the_top(self):
        text = self.read('maps/testdist-iscsi-best-practices.ditamap')
        self.assertOrdered(
            text,
            'c_testdist_iscsi_best-practices_architecture_overview.dita" '
            'navtitle="Architecture Overview">',
            'c_testdist_iscsi_best-practices_performance_tuning.dita',
            '</topicref>')

    def test_gui_quickstart_is_converted_as_a_task_and_mapped(self):
        self.assertIn('<task id="t_testdist_iscsi_gui-quickstart"',
                      self.read(f'{ISCSI_DIR}/t_testdist_iscsi_gui-quickstart.dita'))
        self.assertIn('t_testdist_iscsi_gui-quickstart.dita',
                      self.read('maps/testdist-iscsi.ditamap'))


# ==========================================================================
# Integration: images on disk
# ==========================================================================

class TestImages(ConverterCase):

    def test_authored_screenshots_are_copied_into_images(self):
        images = self.out() / 'images'
        self.assertTrue((images / 'test screenshot.png').is_file())
        self.assertTrue((images / 'diagram.png').is_file())

    def test_every_local_image_href_resolves_from_its_topic_directory(self):
        unresolved = []
        for topic in self.all_topics():
            text = topic.read_text(encoding='utf-8')
            for href in re.findall(r'<image href="([^"]+)" scope="local"', text):
                target = (topic.parent / urllib.parse.unquote(href)).resolve()
                if not target.is_file():
                    unresolved.append(f'{topic.name} -> {href}')
        self.assertEqual(unresolved, [])

    def test_deeply_nested_topic_gets_an_extra_hop(self):
        text = self.read('topics/testlocal/disaggregated/fc/'
                         't_testlocal_disaggregated_fc_quickstart.dita')
        self.assertIn('<image href="../../../../images/diagram.png" scope="local">', text)


# ==========================================================================
# Integration: XML validity across the whole output
# ==========================================================================

class TestOutputValidity(ConverterCase):

    TASKBODY_ORDER = ['prereq', 'context', 'steps', 'steps-informal',
                      'steps-unordered', 'result', 'example', 'postreq']

    def test_every_generated_file_parses_as_xml(self):
        for path in self.all_topics() + self.all_maps():
            with self.subTest(file=path.name):
                try:
                    ET.parse(path)
                except ET.ParseError as exc:
                    self.fail(f'{path.name}: {exc}')

    def test_taskbody_child_order_is_legal_dita(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            if root.tag != 'task':
                continue
            body = root.find('taskbody')
            self.assertIsNotNone(body, path.name)
            children = [c.tag for c in body]
            with self.subTest(file=path.name):
                self.assertEqual(len(children), len(set(children)),
                                 f'duplicate taskbody children: {children}')
                indices = [self.TASKBODY_ORDER.index(c) for c in children]
                self.assertEqual(indices, sorted(indices),
                                 f'illegal taskbody order: {children}')

    def test_steps_contain_a_cmd_first(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            for step in root.iter('step'):
                with self.subTest(file=path.name):
                    self.assertEqual([c.tag for c in step][:1], ['cmd'])

    def test_list_items_wrap_content_in_p(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            for li in root.iter('li'):
                with self.subTest(file=path.name):
                    self.assertEqual([c.tag for c in li][:1], ['p'],
                                     'Heretto requires <li><p>')

    def test_sections_are_never_nested_and_carry_unique_ids(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            for section in root.iter('section'):
                self.assertEqual(list(section.iter('section')), [section],
                                 f'{path.name}: nested <section>')
            ids = [s.get('id') for s in root.iter('section')]
            with self.subTest(file=path.name):
                self.assertNotIn(None, ids)
                self.assertEqual(len(ids), len(set(ids)))

    def test_sections_never_appear_inside_a_taskbody(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            if root.tag == 'task':
                self.assertEqual(list(root.iter('section')), [], path.name)

    def test_root_elements_declare_xml_lang(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            with self.subTest(file=path.name):
                self.assertEqual(root.get('{http://www.w3.org/XML/1998/namespace}lang'),
                                 'en-US')

    def test_images_declare_scope_and_alt(self):
        for path in self.all_topics():
            root = ET.parse(path).getroot()
            for image in root.iter('image'):
                with self.subTest(file=path.name):
                    self.assertIn(image.get('scope'), ('local', 'external'))
                    self.assertIsNotNone(image.find('alt'))

    def test_output_is_pure_ascii(self):
        for path in self.all_topics():
            data = path.read_bytes()
            with self.subTest(file=path.name):
                try:
                    data.decode('ascii')
                except UnicodeDecodeError as exc:
                    self.fail(f'{path.name}: non-ASCII byte: {exc}')

    def test_no_liquid_or_markdown_leaks_into_the_output(self):
        for path in self.all_topics():
            text = path.read_text(encoding='utf-8')
            with self.subTest(file=path.name):
                for leak in ('{% include', '{% raw', '{{ site.baseurl', '</p></p>'):
                    self.assertNotIn(leak, text)
                self.assertNotRegex(text, r'\*\*[A-Za-z]')  # unconverted bold

    def test_no_authored_content_is_lost(self):
        """Every MARKER_ token in the fixtures reaches the output.

        The exceptions are constructs the converter drops by design (or by known
        limitation); each is asserted individually in the tests above.
        """
        expected_dropped = {
            'MARKER_BP_TOC_ITEM',                # Table of Contents section
            'MARKER_BP_TROUBLESHOOTING_BODY',    # troubleshooting excluded from BP
        }
        authored = set()
        for md in list((FIXTURES / 'distributions').rglob('*.md')) + \
                list((FIXTURES / '_includes').rglob('*.md')):
            authored.update(re.findall(r'MARKER_[A-Z0-9_]+', md.read_text(encoding='utf-8')))
        blob = ''.join(p.read_text(encoding='utf-8') for p in self.all_topics())
        missing = sorted(m for m in authored - expected_dropped if m not in blob)
        self.assertEqual(missing, [], f'content lost in conversion: {missing}')
        # And the drop list is accurate, not stale
        still_present = sorted(m for m in expected_dropped if m in blob)
        self.assertEqual(still_present, [],
                         f'expected-dropped markers now appear (update the list): {still_present}')


# ==========================================================================
# Integration: alternative flag combinations
# ==========================================================================

class TestFlatOutput(ConverterCase):
    """Without --organize-sections everything lands directly in topics/."""

    FLAGS = ('--inline-includes',)

    def test_topics_are_flat(self):
        self.assertTrue((self.out() / 'topics/t_testdist_iscsi_quickstart.dita').is_file())
        self.assertFalse((self.out() / ISCSI_DIR).exists())

    def test_image_prefix_has_a_single_hop(self):
        text = self.read('topics/t_testdist_iscsi_quickstart.dita')
        self.assertIn('<image href="../images/diagram.png" scope="local">', text)

    def test_cross_references_are_relative_to_the_flat_topics_dir(self):
        text = self.read('topics/t_testdist_iscsi_quickstart.dita')
        self.assertIn('<xref href="t_testdist_nvme-tcp_quickstart.dita"', text)
        self.assertIn('<xref href="common/c_glossary.dita"', text)

    def test_all_hrefs_still_resolve(self):
        for topic in self.all_topics():
            text = topic.read_text(encoding='utf-8')
            for href in re.findall(r'<xref href="([^"]+)" format="dita"', text):
                if href.startswith('../../../README'):
                    continue
                self.assertTrue((topic.parent / href.split('#', 1)[0]).resolve().is_file(),
                                f'{topic.name} -> {href}')
            for href in re.findall(r'<image href="([^"]+)" scope="local"', text):
                self.assertTrue((topic.parent / urllib.parse.unquote(href)).resolve().is_file(),
                                f'{topic.name} -> {href}')


class TestConrefMode(ConverterCase):
    """Without --inline-includes, includes become warehouse topics + conrefs."""

    FLAGS = ()

    def test_warehouse_topics_are_generated_for_every_include(self):
        names = {p.name for p in (self.out() / 'warehouse').glob('*.dita')}
        self.assertIn('warehouse_quickstart_test-disclaimer.dita', names)
        self.assertIn('warehouse_quickstart_test-outer-include.dita', names)
        self.assertIn('warehouse_quickstart_test-inner-include.dita', names)

    def test_warehouse_topic_uses_a_div_not_a_section(self):
        text = self.read('warehouse/warehouse_quickstart_test-outer-include.dita')
        self.assertIn('<topic id="warehouse_quickstart_test-outer-include" xml:lang="en-US">', text)
        self.assertIn('<div id="quickstart_test-outer-include_content">', text)
        self.assertNotIn('<section', text)  # <section> is illegal inside <taskbody>
        self.assertIn('MARKER_OUTER_INCLUDE', text)

    def test_include_becomes_a_conref_and_the_target_resolves(self):
        topic = self.out() / 'topics/t_testdist_iscsi_quickstart.dita'
        text = topic.read_text(encoding='utf-8')
        conrefs = re.findall(r'<div conref="([^"]+)"/>', text)
        self.assertTrue(conrefs)
        for conref in conrefs:
            path, fragment = conref.split('#', 1)
            target = (topic.parent / path).resolve()
            self.assertTrue(target.is_file(), f'conref target missing: {conref}')
            topic_id, div_id = fragment.split('/', 1)
            target_text = target.read_text(encoding='utf-8')
            self.assertIn(f'<topic id="{topic_id}"', target_text)
            self.assertIn(f'<div id="{div_id}">', target_text)

    def test_include_content_is_not_inlined(self):
        text = self.read('topics/t_testdist_iscsi_quickstart.dita')
        self.assertNotIn('MARKER_OUTER_INCLUDE_CODE', text)

    def test_conref_paths_track_topic_nesting_under_organize_sections(self):
        out = run_converter('--organize-sections')
        topic = out / ISCSI_DIR / 't_testdist_iscsi_quickstart.dita'
        conrefs = re.findall(r'<div conref="([^"]+)"/>',
                             topic.read_text(encoding='utf-8'))
        self.assertTrue(conrefs)
        for conref in conrefs:
            self.assertTrue(conref.startswith('../../../warehouse/'), conref)
            self.assertTrue((topic.parent / conref.split('#')[0]).resolve().is_file(),
                            f'conref target missing: {conref}')


class TestScopedRun(ConverterCase):
    """-d/-p filters restrict what is emitted but not how hrefs are computed."""

    FLAGS = CANONICAL + ('-d', 'testdist', '-p', 'iscsi')

    def test_only_the_scoped_guides_are_converted(self):
        names = {p.name for p in self.all_topics()}
        self.assertIn('t_testdist_iscsi_quickstart.dita', names)
        self.assertNotIn('t_testdist_nvme-tcp_quickstart.dita', names)
        self.assertNotIn('t_testlocal_disaggregated_fc_quickstart.dita', names)

    def test_hrefs_to_unconverted_targets_are_still_correct(self):
        # The href is a function of the source path, so a scoped run keeps links
        # that a full import will resolve.
        text = self.read(QS)
        self.assertIn('<xref href="../nvme-tcp/t_testdist_nvme-tcp_quickstart.dita"', text)

    def test_scoped_map_title_names_the_filters(self):
        self.assertIn('<title>Testdist iSCSI Storage Guide</title>',
                      self.read('maps/linux-storage-guides.ditamap'))


class TestDeploymentScopedRun(ConverterCase):
    """-D accepts aliases and narrows to one deployment topology."""

    FLAGS = CANONICAL + ('-d', 'testlocal', '-D', 'disagg')

    def test_alias_resolves_and_filters(self):
        names = {p.name for p in self.all_topics()}
        self.assertIn('t_testlocal_disaggregated_fc_quickstart.dita', names)
        self.assertNotIn('t_testdist_iscsi_quickstart.dita', names)

    def test_map_title_includes_the_deployment(self):
        self.assertIn('<title>Testlocal Disaggregated Storage Guide</title>',
                      self.read('maps/linux-storage-guides.ditamap'))


# ==========================================================================
# Integration: standalone (--file) mode
# ==========================================================================

class TestStandaloneChapters(ConverterCase):

    FLAGS = ()
    SOURCE = STANDALONE

    def test_one_concept_topic_per_h1(self):
        names = {p.name for p in self.all_topics()}
        self.assertEqual(names, {'c_chapter_one.dita', 'c_chapter_two.dita'})

    def test_table_of_contents_is_removed(self):
        blob = ''.join(p.read_text(encoding='utf-8') for p in self.all_topics())
        self.assertNotIn('MARKER_STANDALONE_TOC_ITEM', blob)

    def test_h2_sections_become_dita_sections(self):
        text = self.read('topics/c_chapter_one.dita')
        self.assertIn('<section id="chapter_one_second_section">', text)
        self.assertIn('MARKER_STANDALONE_CODE', text)

    def test_sibling_images_directory_is_copied(self):
        self.assertTrue((self.out() / 'images/standalone-shot.png').is_file())
        self.assertIn('<image href="../images/standalone-shot.png" scope="local">',
                      self.read('topics/c_chapter_one.dita'))

    def test_standalone_map_hrefs_are_relative_to_the_maps_directory(self):
        text = self.read('maps/standalone.ditamap')
        for href in re.findall(r'href="([^"]+)"', text):
            self.assertTrue((self.out() / 'maps' / href).resolve().is_file(), href)

    def test_standalone_map_root_declares_xml_lang(self):
        self.assertIn('<map xml:lang="en-US">', self.read('maps/standalone.ditamap'))


class TestStandaloneSingleTask(ConverterCase):

    FLAGS = ('--single-task',)
    SOURCE = STANDALONE

    def test_a_single_task_topic_is_emitted(self):
        names = {p.name for p in self.all_topics()}
        self.assertEqual(names, {'t_standalone.dita'})

    def test_h2s_become_steps_and_pre_h2_content_becomes_context(self):
        text = self.read('topics/t_standalone.dita')
        self.assertOrdered(text, '<context>', 'MARKER_STANDALONE_CH1_PARAGRAPH',
                           '</context>', '<steps>',
                           '<cmd>Chapter One Second Section</cmd>',
                           '<cmd>Chapter Two First Section</cmd>')

    def test_table_and_note_survive_inside_steps(self):
        text = self.read('topics/t_standalone.dita')
        self.assertIn('<entry>MARKER_STANDALONE_TABLE_CELL</entry>', text)
        self.assertIn('<note type="important"><p>MARKER_STANDALONE_NOTE.</p></note>', text)

    def test_output_parses_and_taskbody_order_is_legal(self):
        root = self.tree('topics/t_standalone.dita')
        children = [c.tag for c in root.find('taskbody')]
        self.assertEqual(children, sorted(children, key=['prereq', 'context', 'steps',
                                                         'postreq'].index))


if __name__ == '__main__':
    unittest.main(verbosity=2)
