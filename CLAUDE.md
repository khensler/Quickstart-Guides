# CLAUDE.md

Guidance for working in this repo. `STYLEGUIDE.md` is the authoritative spec for
Markdown→DITA conventions — read it before editing guides or the converter. This
file records the rules and gotchas that are easy to get wrong.

## What this repo is

Jekyll-rendered Markdown quickstart guides for connecting platforms to Everpure Data
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

- The company is **Everpure Data** (or "Everpure" where it reads better). Never
  "Pure Storage". Product names like **FlashArray** are unchanged.
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
- Include `{% include quickstart/disclaimer.md %}` after the H1 — it lands in
  `<prereq>` as an important note.
- A `## Next Steps` section becomes `<postreq>`. Guides without one produce no postreq.
- Prefer existing `_includes/quickstart/*.md` snippets over restating shared content.

Some older guides (the Azure Local disaggregated pair) use `## Phase N` / `### N.N`
instead of numbered steps. That still converts, but new guides should use `## Step N:`.

## How the converter maps Markdown to DITA

Facts worth remembering before debugging output:

- Any H2 becomes a `<step>`, so `## Troubleshooting`, `## Additional Notes`, and
  `## Related Articles` all show up as steps. That is expected, not a bug.
- H2s matching `prerequisite` / `disclaimer` / `important` / `next step` are routed to
  `<prereq>` / `<postreq>` instead.
- H3 bullets under `## Prerequisites` are flattened into the prereq `<ul>`; the H3
  subheading itself is dropped.
- Content before the first H2 goes to `<context>`; intro notes and includes go to
  `<prereq>`. `<taskbody>` order is enforced as prereq → context → steps → postreq.
- **Nested emphasis mangles.** `**bold with *italic* inside**` produces broken
  `*<i>…</i>` markup. Use one level of emphasis per span.
- Image `href`s are computed from the topic's nesting depth (`set_topic_subdir`).
  With `--organize-sections` topics sit three levels deep, so hrefs are
  `../../../images/`. Touching image path logic means re-checking both layouts.
- Authored screenshots referenced from a guide are copied into `images/` by
  `_copy_local_images` (markdown paths are URI-encoded, files on disk are not).
- Map `href`s are **collection-root relative** (`topics/...` from inside `maps/`).
  This is deliberate — Heretto resolves from the imported root. Do not "fix" it.

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

## Technical accuracy in guides

- Never present two conflicting config blocks as compatible. Pick one authoritative
  block and explain deviations in a note. (This bit the MPIO
  `Set-MPIOSetting -NewPDORemovePeriod` values: Microsoft's Azure Local docs say 20,
  Everpure Data's general Windows guidance says 30.)
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
