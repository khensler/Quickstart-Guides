# Converter validation suite

Fixtures and assertions for `scripts/convert_to_dita.py`. Every Markdown
construct the guides use appears in a fixture here, so a converter change that
alters (or silently drops) any of them fails a test.

```bash
python tests/test_converter.py          # all tests
python tests/test_converter.py -v       # per-test output
python tests/test_converter.py TestTaskTopic TestCrossReferences
```

Stdlib `unittest` only — no pytest, no network. `--skip-diagrams` is always
passed, so no Kroki server is needed; Mermaid blocks are asserted as the
`<!-- Mermaid diagram N (skipped) -->` placeholder.

`tests/` is listed in `_config.yml` `exclude:` — the fixtures reference includes
that exist only under `tests/fixtures/_includes/`, and Jekyll would fail the
build on them.

## Layout

```
tests/
  test_converter.py                      # the whole suite
  fixtures/                              # a miniature copy of the repo, used as -i
    _includes/
      quickstart/test-disclaimer.md       # mirrors the real disclaimer include
      quickstart/test-outer-include.md    # every block type + a nested include
      quickstart/test-inner-include.md    # reached only by recursive expansion
      glossary.md                         # a REFERENCE_TOPICS entry
      iscsi-multipath-config.md           # a REFERENCE_TOPICS entry + link target
    distributions/
      testdist/iscsi/QUICKSTART.md        # the main task fixture
      testdist/iscsi/BEST-PRACTICES.md    # the main concept fixture
      testdist/iscsi/GUI-QUICKSTART.md    # the GUI-QUICKSTART glob
      testdist/nvme-tcp/QUICKSTART.md     # protocol-sibling cross-link target
      testlocal/disaggregated/fc/         # deployment nesting + 4-hop images
    standalone/STANDALONE.md              # --file / --single-task modes
```

Fixture prose is tagged with `MARKER_*` tokens. `test_no_authored_content_is_lost`
collects every marker in the fixtures and asserts it reaches the output, minus an
explicit list of by-design drops — so a construct that starts disappearing gets
caught even if no one wrote a specific assertion for it.

## What is covered

Converter runs (each cached for the whole session):

| Flags | Purpose |
|-------|---------|
| `--inline-includes --section-maps --organize-sections` | the canonical run |
| `--inline-includes` | flat `topics/`, one-hop image prefix |
| *(none)* | conref mode + warehouse topics |
| `--organize-sections` | conref/organized interaction |
| canonical `+ -d/-p`, `+ -d/-D` | scoped runs and deployment aliases |
| `-f STANDALONE.md`, `+ --single-task` | standalone modes |

Assertions cover: front matter and title extraction; `<prereq>` / `<context>` /
`<steps>` / `<postreq>` routing and legal `<taskbody>` order; `Step N:` prefix
stripping; H3 handling in prereqs and steps; H2-per-section concept splitting
with troubleshooting and TOC exclusion; section-level selection for deep heading
levels; Quick Reference tip wrapping; note-type detection, prefix stripping and
collapsing; lists (flat, wrapped, nested `ol`/`ul` to three levels); tables
(header/body, inline markup, malformed rows); code blocks and `{% raw %}`
templating; inline bold/italic/`codeph`/xref with code-span protection; images
(local, external, URI-encoded names, per-depth `../` hops, copied files);
Jekyll includes (inline, nested, conref); cross-reference resolution through the
link registry (anchors, slug forms, `.html` spellings, basename fallback,
unresolvable fallback); every map variant and href resolution; ASCII-only output;
and XML well-formedness across all output.

## Regression tests for fixed bugs

The suite originally documented seven wrong-but-current behaviours. All are fixed;
these tests now assert the correct behaviour and fail if it regresses.

| Test | Bug it guards |
|------|---------------|
| `test_nested_emphasis_converts_both_levels` | `**bold with *italic* inside**` emitted broken `*<i>` markup |
| `test_bold_span_wrapping_across_source_lines` | a bold span wrapping across source lines left stray `*` in the text (blockquote lines are newline-joined, so the bold pattern needs DOTALL) |
| `test_indented_code_fence_under_a_list_item_is_a_code_block` | an indented fence degraded to a paragraph, backticks and all |
| `test_intro_before_first_h2_is_prepended_to_the_first_section` | BEST-PRACTICES prose between the H1 and first H2 was discarded |
| `test_prose_in_an_important_h2_is_kept_in_prereq`, `test_prereq_prose_before_the_list_precedes_the_ul` | prose/code/tables in `## Prerequisites` or `## Important…` matched no branch and were dropped |
| `test_conref_paths_track_topic_nesting_under_organize_sections` | conrefs were hard-coded `../warehouse/`, resolving only in the flat layout |
| `test_sanitize_id_never_starts_with_a_digit` | `.strip('_')` undid the NCName guard, so `### 1.1 …` produced an illegal id |
| `test_standalone_map_root_declares_xml_lang` | the standalone `<map>` root omitted `xml:lang="en-US"` |
| `test_disclaimers_are_important_even_when_emoji_decorated` | disclaimer notes were typed `note`/`warning` instead of `important` |

If you ever need to keep a behaviour that is wrong-but-deliberate, name the test
`..._known_limitation` / `..._known_gap` and say why in a comment, so a later fix is
noticed rather than silently breaking something downstream.

## Adding coverage

1. Add the construct to the relevant fixture, tagged with a new `MARKER_*` token.
2. Run the suite; `test_no_authored_content_is_lost` fails if it is dropped.
3. Add a specific assertion for the shape you expect.

Verify a new test can fail: temporarily break the converter behaviour it targets
and confirm the test catches it.
