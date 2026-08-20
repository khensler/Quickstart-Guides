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

## Known-limitation tests

Tests ending in `_known_limitation` or `_known_gap` lock in behaviour that is
wrong-but-current, so a fix is noticed instead of silently breaking something
downstream. When you fix the converter, invert the assertion rather than deleting
the test.

| Test | Behaviour |
|------|-----------|
| `test_nested_emphasis_is_a_known_limitation` | `**bold with *italic* inside**` emits broken `*<i>` markup |
| `test_indented_code_fence_under_a_list_item_known_limitation` | an indented fence under a bullet degrades to a paragraph |
| `test_intro_before_first_h2_is_dropped_known_limitation` | BEST-PRACTICES prose between the H1 and first H2 is discarded |
| `test_prose_in_an_important_h2_is_dropped_known_limitation` | non-note content in a `## Important…` H2 has nowhere to go |
| `test_conref_paths_break_under_organize_sections_known_gap` | conrefs are hard-coded `../warehouse/`, which only resolves in flat mode |
| `test_sanitize_id_can_start_with_a_digit_known_gap` | `.strip('_')` undoes the NCName guard for headings starting with a digit |
| `test_standalone_map_root_lacks_xml_lang_known_gap` | the standalone `<map>` root omits `xml:lang="en-US"` |

## Adding coverage

1. Add the construct to the relevant fixture, tagged with a new `MARKER_*` token.
2. Run the suite; `test_no_authored_content_is_lost` fails if it is dropped.
3. Add a specific assertion for the shape you expect.

Verify a new test can fail: temporarily break the converter behaviour it targets
and confirm the test catches it.
