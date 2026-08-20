---
layout: default
title: Testdist iSCSI Converter Fixture
---

# Testdist iSCSI Converter Fixture

---

{% include quickstart/test-disclaimer.md %}

---

MARKER_CONTEXT_PARAGRAPH sits before the first H2, so it must land in
`<context>` — and this second source line must join the same paragraph.

- MARKER_CONTEXT_BULLET one
- MARKER_CONTEXT_BULLET two

```bash
echo "MARKER_CONTEXT_CODE"
```

## Overview

MARKER_OVERVIEW_PARAGRAPH with **bold**, *italic*, `codeph`, and an
[external link](https://support.everpuredata.com/bundle/test).

Unicode round-trip: host → array, an em—dash, "smart quotes", and a ⚠️ emoji.

Nested emphasis: **MARKER_NESTED_EMPHASIS is bold with *italic* inside** it, and
*italic with **bold** inside* it.

## Prerequisites

MARKER_PREREQ_INTRO_PARAGRAPH is authored above the bullet list, so it belongs in
prereq ahead of the `<ul>`.

- MARKER_PREREQ_ONE with `codeph` and a [sibling protocol guide](../nvme-tcp/QUICKSTART.md)
- MARKER_PREREQ_TWO that wraps across two source lines and
  therefore has to be folded back into a single list item

### Additional Requirements

- MARKER_PREREQ_H3_ITEM flattened up into the same prereq list

```bash
echo "MARKER_PREREQ_CODE_AFTER_LIST"
```

> **Note:** MARKER_PREREQ_NOTE belongs inside prereq, after the list.

## Background

MARKER_BACKGROUND_PARAGRAPH — an ordinary H2 that is neither a step nor a
special section, so it still becomes a `<step>`.

## Step 1: Verify the initiator

MARKER_STEP1_PARAGRAPH.

```bash
sudo systemctl start iscsid
iscsiadm -m session -P 3
```

| Setting | Value | Notes |
|---------|-------|-------|
| `node.session.timeo.replacement_timeout` | 60 | MARKER_STEP1_TABLE_CELL |
| Queue depth | 128 | Per-session default |
| Broken row with too few cells | dropped |

## Step 2: Configure multipath

1. **Discover the portal**: run discovery against every portal
   - *Why*: MARKER_NESTED_WHY_ONE
   - MARKER_NESTED_SECOND_BULLET
2. **Log in to all portals**: MARKER_OL_ITEM_TWO
   1. MARKER_NESTED_ORDERED_SUB
      - MARKER_NESTED_DEEP_BULLET
3. Plain third item with no sublist

> **Warning:** MARKER_WARNING_ONE — this operation cannot be undone.

> **Warning:** MARKER_WARNING_TWO — consecutive same-type note.

> **Caution:** MARKER_CAUTION_NOTE.

> **Tip:** MARKER_TIP_NOTE.

> MARKER_PLAIN_NOTE with no keyword prefix at all.

> **MARKER_WRAPPED_BOLD spans two source lines and contains an *italic* run, and
> must still close.** Trailing prose after the bold span.

### Subheading Inside A Step

MARKER_STEP2_H3_BODY — the H3 above becomes a bold paragraph, not a step.

- Bullet directly above an indented fence
  ```bash
  echo "MARKER_FENCE_AFTER_LIST"
  ```

> **Vendor Documentation Priority:** MARKER_VENDOR_PRIORITY_NOTE is hoisted out of this step and into prereq.

## Important Notes

MARKER_IMPORTANT_SECTION_PARAGRAPH is prose in a disclaimer/important H2, which
is routed into prereq alongside that section's notes.

> **Important:** MARKER_IMPORTANT_SECTION_NOTE is routed to `<prereq>`.

## Step 3: Images, diagrams, and templating

![Test screenshot](img/test%20screenshot.png)

![Local diagram](img/diagram.png)

![Remote screenshot](https://example.com/remote.png)

```mermaid
graph LR
    A[Host] --> B[Switch]
    B --> C[FlashArray]
```

{% raw %}
```bash
oc get secret test-secret -o go-template='{{index .data "tls.crt"}}'
```
{% endraw %}

{% include quickstart/test-outer-include.md %}

## Troubleshooting

MARKER_TROUBLESHOOTING_BODY — kept for QUICKSTART topics, unlike BEST-PRACTICES.

## Additional Notes

MARKER_ADDITIONAL_NOTES_BODY.

## Next Steps

MARKER_POSTREQ_PARAGRAPH.

- MARKER_POSTREQ_BULLET_ONE
- MARKER_POSTREQ_BULLET_TWO

> **Tip:** MARKER_POSTREQ_NOTE.

## Related Articles

- [Best Practices anchor](BEST-PRACTICES.md#performance-tuning)
- [Best Practices, no anchor](BEST-PRACTICES.md)
- [Best Practices H3 anchor](BEST-PRACTICES.md#nconnect-tuning)
- [Best Practices mixed-case anchor](BEST-PRACTICES.md#Queue-Depth)
- [Best Practices punctuated anchor](BEST-PRACTICES.md#understanding-apd-all-paths-down)
- [Sibling quickstart anchor](../nvme-tcp/QUICKSTART.md#step-1-connect)
- [Glossary via Jekyll html]({{ site.baseurl }}/common/glossary.html)
- [Unregistered markdown target](../../../README.md)
- [External support article](https://support.everpuredata.com/bundle/other)
