# CLAUDE.md

Guidance for working in this repo. `STYLEGUIDE.md` is the authoritative spec for
Markdown→DITA conventions — read it before editing guides or the converter. This
file records the rules and gotchas that are easy to get wrong.

## What this repo is

Jekyll-rendered Markdown quickstart guides for connecting platforms to Everpure
FlashArray, which are also converted to DITA XML for the Heretto CCMS. Every guide
therefore has **two consumers**: the static site and the DITA pipeline. A change that
reads fine in Markdown can still break the DITA output — always check both.

Layout:

- `distributions/<platform>/[<deployment>/]<protocol>/QUICKSTART.md` — procedures
- `distributions/<platform>/<protocol>/BEST-PRACTICES.md` — concepts
- `_includes/quickstart/*.md` — reusable snippets pulled in with Jekyll includes
- `common/`, `_includes/` — shared reference content
- `scripts/convert_to_dita.py` — the Markdown→DITA converter
- `README.md` + `index.md` — the two navigation indexes (**both** must be updated)
- `dita_output/`, `articles/`, `*.zip` — build artifacts, all gitignored

## Naming and links

- The company is **Everpure** — not "Everpure Data", never "Pure Storage". The
  `everpuredata.com` domain keeps the "data" but the company name does not.
  Product names like **FlashArray** are unchanged.
- Exception: `-VendorId "PURE"` is a literal SCSI vendor ID. Never rewrite it.
  Same for `PureStoragePowerShellSDK2`, `Connect-PFA2Array`, `New-Pfa2*`.
- Support links use **`support.everpuredata.com`**. Paths carry over unchanged from
  the old `support.purestorage.com` host (both `/bundle/...` and legacy
  `/Solutions/...` forms resolve). Most non-Azure guides still point at the old
  host — migrate opportunistically, and verify the URL before changing it.
- Relative links between guides must resolve on disk. Cross-link siblings in both
  directions (protocol siblings and, where applicable, deployment-topology siblings).

## QUICKSTART structure (required)

```markdown
---
layout: default
title: <same text as the H1>
---

# <Title>

---

{% include quickstart/disclaimer.md %}

---

## Overview            <- optional; intro prose and cross-link callouts

## Prerequisites

## Background          <- optional

## Step 1: <action>
## Step 2: <action>
...

## Troubleshooting
## Additional Notes
## Next Steps
## Related Articles
```

Hard rules:

- **YAML front matter is required.** Without it Jekyll copies the file verbatim and
  `{% include %}` never expands.
- **Steps must be H2 (`## Step N:`).** The converter builds `<step>` from H2 only;
  H3 becomes a bold paragraph. Nesting steps under a `## Step-by-Step Instructions`
  wrapper collapses the entire procedure into one DITA step.
- **Step numbers run 1..N with no gaps and no repeats**, counting any step an
  include contributes. An optional step still takes its own number and is marked
  with a trailing `(Optional)` — `## Step 4: Configure Authentication (Optional)`.
  Don't reuse the previous number for an optional step; `proxmox/iscsi` did that
  and published two "Step 3"s on the site.

  **Before renumbering anything, check for an include that carries a step.**
  `_includes/quickstart/nvme-enable-multipath.md` owns `## Step 2: Enable Native
  NVMe Multipath`, so all four NVMe-TCP guides (Debian, RHEL, SUSE, Oracle) jump
  1 → 3 in their own source and are *correct*. A naive "renumber the headings
  1..N" pass over those files would silently produce two Step 2s. The numbering
  check has to add the include's step before comparing.

  Oracle was missing that include until September 2026, which is why it numbered
  a clean 1..9 while its siblings went 1,3..10 — the tidy-looking one was the
  broken one. Its quickstart never told the reader to enable native NVMe
  multipath at all, even though its own best-practices guide requires it.
- A `## Next Steps` section becomes `<postreq>`. Guides without one produce no postreq.
- Prefer existing `_includes/quickstart/*.md` snippets over restating shared content.

**The intro note block (required, and in this order).** Every QUICKSTART/GUIDE
carries the same three notes after the H1 and its intro prose, between two `---`
rules:

```markdown
{% include quickstart/disclaimer.md %}

{% include quickstart/glossary-link-<fc|iscsi|nvme|nfs>.md %}

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [<Label> Best Practices](./BEST-PRACTICES.md)
```

All three land in `<prereq>` in source order regardless of where the disclaimer's
own H2 falls, so the order here is the order on the page. Rules:

- The **disclaimer** is in all 40 guides, no exceptions.
- The **glossary link** matches the guide's protocol directory. `nvme-tcp` uses
  the `nvme` include and `nfs-tls` uses the `nfs` one. These are *Jekyll-site*
  links, so their anchors are kramdown slugs — hence `#fc--san-terminology` with
  two hyphens, from `FC / SAN Terminology`. The glossary has no NFS-specific
  section, so `glossary-link-nfs.md` points at Common Storage Terms.
- The **best-practices note** appears **only** where a sibling
  `BEST-PRACTICES.md` actually exists. Do not add it to a guide without one.
- Guide-specific notes (a topology pointer, a CLI/GUI cross-link, an NFSv3
  warning) go **above** the block with the intro prose; per-step warnings stay
  where they belong. Don't interleave them with the three.
- Don't restate the best-practices pointer in a bespoke note — that produced two
  near-identical notes on the XCP-ng GUI guides.

This was normalized in September 2026; before that some guides had the glossary
link, some the best-practices link, some both in one note, some in two, and some
had the glossary include stranded at the bottom of `## Prerequisites` — which is
why Oracle's page rendered its prereq bullets sandwiched between two notes.

**`{% include quickstart/arp-warning.md %}` goes in the step where the reader
configures the interfaces**, not in `## Prerequisites`. Four guides had it in
prereq, which is the other half of why Oracle's note stack looked wrong. All 11
guides that carry it (5 NVMe-TCP, 6 iSCSI) now place it in their network or
interface-binding step. The include links both `common/network-concepts.html`
(what the settings do) and `./BEST-PRACTICES.md` (the values). That relative link
resolves per-including-guide even though the include is shared — verified — so
every guide that includes it must have a sibling `BEST-PRACTICES.md`. All 11 do.

**Literal Liquid in guides.** `jekyll-optional-front-matter` makes Jekyll render *every*
`.md` in the repo, front matter or not. Any `{{ ... }}` that isn't valid Liquid warns and
renders empty (this silently blanked the `oc get secret -o go-template='{{index .data ...}}'`
commands in the OpenShift NFS-TLS guide), and a malformed `{% include %}` is a **hard build
failure**. Wrap Go/Helm/Jinja templating in `{% raw %}` / `{% endraw %}` on their own lines
around the fence — `convert_to_dita.py` strips those markers, so DITA output is unaffected.
Root-level dev docs that discuss Liquid syntax (`CLAUDE.md`) are listed in `_config.yml`
`exclude:` instead.

Some older guides (the Azure Local disaggregated pair) use `## Phase N` / `### N.N`
instead of numbered steps. That still converts, but new guides should use `## Step N:`.

## How the converter maps Markdown to DITA

Facts worth remembering before debugging output:

- Any H2 becomes a `<step>`, so `## Troubleshooting`, `## Additional Notes`, and
  `## Related Articles` all show up as steps. That is expected, not a bug.
- H2s matching `prerequisite` / `disclaimer` / `important` / `next step` are routed to
  `<prereq>` / `<postreq>` instead.
- Under `--inline-includes` an include's elements are **spliced into the parent's**
  element stream (`_splice_inlined_includes`), so an H2 the include carries becomes a
  real `<step>` — that is how `## Quick Reference` and `## Step 2: Enable Native NVMe
  Multipath` get their own steps. The include's own sectioning is scoped to it: the
  region an include opens closes again at its end, so the `disclaimer.md` H2 cannot
  swallow the intro prose that follows it into `<prereq>`. Without the flag an
  include stays a conref and none of this applies.
- **No emoji reaches the output at all**, anywhere — not as a glyph and not as a
  `[WARNING]`-style token. They remain useful *in the Markdown* as authoring
  signals: `_detect_note_type` reads a raw `⚠️` to type a note, and it does that
  before normalisation, so the emoji does its job and then disappears. A lone
  emoji is the exception — see **Characters** below.
- See **Characters** below for what survives to the published page. In short:
  extended ASCII is fine, emoji are not, and nothing is dropped in silence.
- Bullets authored inside a blockquote become a real `<ul>` in the note
  (`_note_body`); notes with no bullets **and no code fence** keep their
  single-`<p>` shape, which is what `collapse_consecutive_notes` matches on.
  `## Next Steps` bullets likewise become a `<ul>` in `<postreq>` rather than one
  `<p>- text</p>` per bullet.
- A **code fence authored inside a blockquote** becomes a real `<codeblock>`,
  emitted as a direct child of the `<note>`. Prose on either side of the fence
  stays in its own `<p>`. Two things make this work and are easy to undo by
  accident: the blockquote collector strips only `>` plus at most one space
  (`_QUOTE_MARKER_RE`), so the fence's own indentation survives, and
  `_note_body` must never wrap the `<codeblock>` in a `<p>`. Before this,
  the fence survived as inline markup and published as `` ``<codeph>bash ``
  with the commands run together on one line — 29 blocks across 11 topics,
  including one where the closing fence tangled with the following prose into
  alternating `<codeph>` runs.
- `Go to: A -> B` after a trigger verb (`Go to` / `Navigate to` / `Browse to` /
  `Click`) becomes `<menucascade>`. A label must be quoted or capitalised, which is
  what keeps trailing prose out of the chain — in `Go to Pool -> Advanced tab`, `tab`
  stays narrative.
- H3 bullets under `## Prerequisites` are flattened into the prereq `<ul>`; the H3
  subheading itself is dropped. Prose, code and tables in that section land in
  `<prereq>` too — before the `<ul>` if authored above the bullets, after it
  otherwise. Same for a `## Important…` / `## Disclaimer…` section.
- Content before the first H2 goes to `<context>`; intro notes and includes go to
  `<prereq>`. `<taskbody>` order is enforced as prereq → context → steps → postreq.
- In a BEST-PRACTICES file, prose between the H1 and the first H2 is prepended to
  the first section's topic (which is also where a bare link to the file lands).
- **A `## Troubleshooting` section in a BEST-PRACTICES file is deliberately not
  converted.** It stays on the GitHub Pages site and is withheld from the support site,
  which has its own troubleshooting KBs — about 1,900 lines across the 25 guides. Both
  `_convert_best_practices_sections` and `_build_link_registry` skip it, in step.
  Intentional; don't "restore" it. Every other H2 becomes its own topic.
- Notes mentioning `disclaimer` or `vendor documentation priority` are typed
  `important`, ahead of the `warning`/⚠️ rule, so the standard disclaimer include
  is consistent whether or not it carries an emoji.
- Emphasis nests: `**bold with *italic* inside**` converts correctly. The bold
  pattern is non-greedy **and** DOTALL — authored spans wrap across source lines
  (blockquote lines are newline-joined), so dropping DOTALL silently leaves stray
  `*` in the output.
- Indented code fences are recognised, including under a list item, and the
  fence's own indentation is stripped. A fence indented **under a list item**
  emits its `<codeblock>` as a **direct child of that `<li>`**, and the list is
  not split — `_adopt_indented_codeblocks_into_list_items` moves it there in a
  post-pass, keyed off `MarkdownElement.fence_indent`. A fence at column zero
  still emits a sibling of the list.

  Two reasons this matters, both learned the hard way:
  - The parser flattens the element stream, so the block used to land *between*
    two lists. Seven authored steps became seven one-item `<ol>`s, each
    restarting at "1." (50 such splits across the repo; now zero.)
  - Editors in Heretto then fixed that by hand, and they did it by putting the
    block inside the `<li>` **wrapped in a `<p>`**. A `<codeblock>` inside a
    `<p>` gets its newlines normalised away, so three commands published as one
    unusable line with a Copy button next to it. Emitting the shape they want,
    with no `<p>` wrapper, removes the reason to touch it. **Never wrap a
    `<codeblock>` in a `<p>`** — there is a test asserting the count is zero.
- Image `href`s are computed from the topic's nesting depth (`set_topic_subdir`).
  With `--organize-sections` topics sit three levels deep, so hrefs are
  `../../../images/`. Touching image path logic means re-checking both layouts.
- Authored screenshots referenced from a guide are copied into `images/` by
  `_copy_local_images` (markdown paths are URI-encoded, files on disk are not).
- Map `href`s are **collection-root relative** (`topics/...` from inside `maps/`).
  This is deliberate — Heretto resolves from the imported root. Do not "fix" it.

## Characters

`normalize_characters()` (still exported under its old name `remove_non_ascii`)
decides what reaches the page. Two rules:

- **Extended ASCII is allowed.** Latin-1 (U+00A0–U+00FF) passes through
  untouched, so `×`, `±`, `°`, `·` and accented letters publish as authored.
  Anything above U+00FF must be mapped in `_CHARACTER_REPLACEMENTS`, because
  only Latin-1 is known to survive the whole Heretto → portal path.
- **No emoji.** None reaches the page. Emoji in the Markdown are fine — they are
  authoring signals, and `_detect_note_type` reads `⚠️` off the raw source
  before normalisation runs — but `_strip_emoji_from_runs` then removes them.
  Every one found is reported, so the source can be cleaned up over time.

  The one subtlety is **what the emoji was worth**. Where it decorated text it
  is simply dropped: `✅ Yes` → `Yes`, `**⚠️ Important Disclaimers**` →
  `**Important Disclaimers**`. A note's `@type` already says "warning", so the
  old `[WARNING]` token was noise on top of markup that said it better. But
  where the emoji was the *whole* run it carried the meaning by itself — a bare
  `| ✓ |` in a checklist column — so it becomes a word (`Yes` / `No`) rather
  than an empty cell. 171 of the repo's 180 emoji are decoration; only `✓`
  appears alone.

Gotchas worth remembering:

- This runs on the **already-escaped XML string**, so a replacement must never
  introduce a raw `<`, `>` or `&`. Use `&lt;` / `&gt;` (see `≥` → `&gt;=`).
- Nothing is dropped silently any more. An unmapped character above U+00FF
  prints a `Warning:` naming the code point — fix the source or add a mapping,
  don't ignore it. This is how `2×2 topology` was found publishing as
  `22 topology` and `(≥ 250 GB)` as `( 250 GB)`: the old code ended with a
  blanket `encode('ascii', 'ignore')`.
- Box-drawing glyphs fold to `-`, `|` and `+` so the ASCII-art topology
  diagrams keep their alignment; deleting them left every label at an odd
  indent.
- Letters above Latin-1 fold to their base letter (`Ā` → `A`) rather than
  vanishing.

## The published content has diverged from this repo

Checked September 2026 against the five iSCSI best-practices multipath topics on
`support-stage.everpuredata.com`: the topics in Heretto are **hand-edited
derivatives** of this repo's Markdown, not a faithful render of it. H3s that the
converter emits as `<p><b>` runs have been promoted to real `<section>`s (Debian
3 → 12 sections), and some prose differs outright — the path-redundancy example
on four of the five topics uses numbers that exist nowhere in this repo.

So a re-import from `convert_to_dita.py` will *regress* that work. Before
republishing an existing topic, diff the generated DITA against what Heretto
holds and decide deliberately which side wins; don't assume our output is newer.

## Running the conversion

Canonical flag set (also in `STYLEGUIDE.md`):

```bash
python scripts/convert_to_dita.py --inline-includes --section-maps --organize-sections
```

- Add `--skip-diagrams` for fast iteration; `--use-existing-images` to avoid
  re-downloading the ~120 Mermaid renders (that download takes >10 minutes).
- Scope a run with `-d <distribution> [-D <deployment>] [-p <protocol>]`, and add
  `--zip` to produce a dated archive named after the flags used.
- `--zip` writes into the output directory's parent, so **separate scoped runs reusing
  the default `dita_output/` overwrite each other's directory** — the zips persist,
  the directory holds only the last run.

Always validate generated output rather than assuming success. Check: XML parses,
`<taskbody>` child order is legal, map hrefs resolve from the output root, image
hrefs resolve from each topic's directory, and no topic lost text versus the previous
build. When changing the converter, diff a full-repo run against a run from the
pre-change script (`git show HEAD:scripts/convert_to_dita.py`) — a fix that quietly
drops content elsewhere is worse than the bug.

## Testing the converter

`python tests/test_converter.py` runs the converter over the fixture tree in
`tests/fixtures/` and asserts on the DITA. It is stdlib `unittest` (no pytest) and
needs no network — `--skip-diagrams` is always passed. Run it before and after any
converter change; see `tests/README.md` for what is covered and how to extend it.

`tests/` is in `_config.yml` `exclude:` — the fixtures reference includes that exist
only under `tests/fixtures/_includes/`, and a missing include is a hard Jekyll build
failure. The converter also skips a `tests/` prefix when globbing guides, so a
repo-root run does not pick the fixtures up.

A passing suite is not a substitute for the full-repo diff above: the fixtures cover
constructs, the diff covers the 60-odd real guides.

## Technical accuracy in guides

- Never present two conflicting config blocks as compatible. Pick one authoritative
  block and explain deviations in a note. (This bit the MPIO
  `Set-MPIOSetting -NewPDORemovePeriod` values: Microsoft's Azure Local docs say 20,
  Everpure's general Windows guidance says 30.)
- `New-Pfa2Host` takes **arrays**: `-Wwns` (FC) and `-Iqns` (iSCSI), not `-Wwn`.
  Pass every WWPN/IQN a node reports, and say so in the prose and checklists.
- Don't run state-changing cmdlets unconditionally on live cluster nodes. Check
  first (`Get-WindowsOptionalFeature`), then act, and use `-NoRestart` so nothing
  prompts for a reboot mid-procedure.
- Destructive loops (disk initialize/format) need a confirm-the-selection step before
  the loop and an explicit warning.
- Prefer exact identifiers over wildcards in commands that mutate system tables
  (e.g. `Remove-MSDSMSupportedHW -VendorId 'Vendor 8' -ProductId 'Product 16'`).
- Keep protocol siblings symmetric: if the iSCSI guide has an array-side SDK example,
  the FC guide should too.

## Platform notes

Windows-first environment. The Bash tool is Git Bash; PowerShell is the primary
shell and each takes its own syntax. There is no `.gitattributes`; the repo relies on
`core.autocrlf=true`, so `git diff --stat` emits "LF will be replaced by CRLF"
warnings for files you didn't touch — that's noise, not a change you introduced.

