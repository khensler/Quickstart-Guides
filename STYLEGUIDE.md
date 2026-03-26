# Markdown to DITA Style Guide

This guide describes the Markdown formatting conventions used in this project and how they translate to DITA XML for the Heretto CCMS.

---

## Document Types Overview

This project uses two primary document types, each with a distinct purpose and structure:

| Document | Purpose | DITA Type | Prefix |
|----------|---------|-----------|--------|
| `QUICKSTART.md` | Step-by-step procedural instructions | Task | `t_` |
| `BEST-PRACTICES.md` | Conceptual/reference information | Concept | `c_` |

---

## QUICKSTART Documents

**Purpose**: Provide step-by-step instructions for completing a specific task (e.g., configuring iSCSI on RHEL).

**DITA Output**: Single task topic (e.g., `t_rhel_iscsi_quickstart.dita`)

### Required Structure

```markdown
# Document Title

{% include quickstart/disclaimer.md %}

## Prerequisites

- Requirement one
- Requirement two

## Step 1: First Action

Instructions for the first step.

```bash
# Command example
sudo systemctl start iscsid
```

## Step 2: Second Action

Instructions for the second step.

## Step 3: Third Action

Instructions for the third step.

## Next Steps

- Follow-up action one
- Follow-up action two
```

### QUICKSTART Section Mapping

| Markdown Section | DITA Element | Notes |
|------------------|--------------|-------|
| `# Title` | `<title>` | Topic title |
| `{% include ... %}` | Inlined content | Disclaimer goes to `<prereq>` |
| `## Prerequisites` | `<prereq>` | List items become `<ul><li>` |
| `## Step N: ...` | `<step><cmd>` | Step heading becomes command |
| Content under step | `<step><info>` | Supporting content |
| `## Next Steps` | `<postreq>` | Follow-up actions |

### QUICKSTART DITA Output Structure

```xml
<task id="t_rhel_iscsi_quickstart" xml:lang="en-US">
    <title>RHEL iSCSI Quickstart</title>
    <prolog><metadata/></prolog>
    <taskbody>
        <prereq>
            <note type="important"><p>Disclaimer content...</p></note>
            <ul>
                <li><p>Requirement one</p></li>
                <li><p>Requirement two</p></li>
            </ul>
        </prereq>
        <steps>
            <step>
                <cmd>First Action</cmd>
                <info>
                    <p>Instructions for the first step.</p>
                    <codeblock>sudo systemctl start iscsid</codeblock>
                </info>
            </step>
            <step>
                <cmd>Second Action</cmd>
                <info><p>Instructions for the second step.</p></info>
            </step>
        </steps>
        <postreq>
            <p>- Follow-up action one</p>
            <p>- Follow-up action two</p>
        </postreq>
    </taskbody>
</task>
```

---

## BEST-PRACTICES Documents

**Purpose**: Provide conceptual information, architectural guidance, and reference material organized by topic.

**DITA Output**: Multiple concept topics, one per H2 section (e.g., `c_rhel_iscsi_best-practices_architecture_overview.dita`)

### Required Structure

```markdown
# Best Practices Title

## Architecture Overview

Conceptual content about architecture...

### Subsection

More detailed information...

## Firewall Configuration

Content about firewall settings...

## Performance Tuning

Content about performance optimization...

## Additional Resources

Links and references...
```

### BEST-PRACTICES Section Mapping

| Markdown Section | DITA Output | Notes |
|------------------|-------------|-------|
| `# Title` | (Used in map) | Not a separate topic |
| `## Section Name` | Separate `.dita` file | Each H2 = new concept topic |
| `### Subsection` | `<section><title>` | Nested within concept |
| Paragraphs | `<p>` | Body content |
| Lists | `<ul>` or `<ol>` | With nested `<li><p>` |

### BEST-PRACTICES DITA Output Structure

```xml
<concept id="c_rhel_iscsi_best-practices_architecture_overview" xml:lang="en-US">
    <title>Architecture Overview</title>
    <prolog><metadata/></prolog>
    <conbody>
        <p>Conceptual content about architecture...</p>
        <section id="subsection">
            <title>Subsection</title>
            <p>More detailed information...</p>
        </section>
    </conbody>
</concept>
```

### Excluded Sections

The following BEST-PRACTICES sections are **not** converted:

- `## Troubleshooting` (and variants) — excluded by design

---

## Key Differences Summary

| Aspect | QUICKSTART | BEST-PRACTICES |
|--------|------------|----------------|
| **Purpose** | How to do something | Why and what to consider |
| **DITA Type** | Task (`<task>`) | Concept (`<concept>`) |
| **File Prefix** | `t_` | `c_` |
| **Output Files** | 1 per document | 1 per H2 section |
| **Body Element** | `<taskbody>` | `<conbody>` |
| **Special Elements** | `<prereq>`, `<steps>`, `<postreq>` | `<section>` |
| **H2 Handling** | Steps or special sections | Separate topic files |

---

## Headings Reference

| Markdown | DITA Element |
|----------|--------------|
| `# Title` | `<title>` (topic title) |
| `## Section` | `<section><title>` or special handling |
| `### Subsection` | Nested `<section>` or content |

---

## Lists

### Unordered Lists

```markdown
- Item one
- Item two
- Item three
```

**DITA Output:**
```xml
<ul>
    <li><p>Item one</p></li>
    <li><p>Item two</p></li>
    <li><p>Item three</p></li>
</ul>
```

### Ordered Lists

```markdown
1. First item
2. Second item
3. Third item
```

**DITA Output:**
```xml
<ol>
    <li><p>First item</p></li>
    <li><p>Second item</p></li>
    <li><p>Third item</p></li>
</ol>
```

### Nested Lists (Ordered with Unordered Sub-items)

```markdown
1. **Main Point**: Description text
   - *Why*: Explanation of the reasoning
2. **Second Point**: More description
   - *Why*: Another explanation
```

**DITA Output:**
```xml
<ol>
    <li><p><b>Main Point</b>: Description text</p>
        <ul>
            <li><p><i>Why</i>: Explanation of the reasoning</p></li>
        </ul>
    </li>
    <li><p><b>Second Point</b>: More description</p>
        <ul>
            <li><p><i>Why</i>: Another explanation</p></li>
        </ul>
    </li>
</ol>
```

> **Important**: Nested bullet items must be indented with at least 2 spaces under their parent numbered item.

---

## Inline Formatting

| Markdown | DITA | Rendered |
|----------|------|----------|
| `**bold**` | `<b>bold</b>` | **bold** |
| `*italic*` | `<i>italic</i>` | *italic* |
| `` `code` `` | `<codeph>code</codeph>` | `code` |
| `[link](url)` | `<xref href="url">link</xref>` | [link](url) |

---

## Notes and Callouts

Blockquotes (`>`) are converted to DITA `<note>` elements. The note type is detected automatically from keywords in the content.

### Note Types

| Keyword in Content | DITA Note Type |
|--------------------|----------------|
| `warning`, `⚠️` | `<note type="warning">` |
| `important` | `<note type="important">` |
| `caution` | `<note type="caution">` |
| `tip` | `<note type="tip">` |
| (default) | `<note type="note">` |

### Example

```markdown
> **Warning:** This operation cannot be undone.
```

**DITA Output:**
```xml
<note type="warning"><p>This operation cannot be undone.</p></note>
```

> **Note**: The converter automatically strips redundant prefixes like "Warning:", "**Important:**", "[WARNING]", and emoji prefixes (⚠️, 📖) since the DITA `<note type="">` already provides the label.

---

## Code Blocks

### Standard Code Blocks

````markdown
```bash
sudo systemctl start iscsid
```
````

**DITA Output:**
```xml
<codeblock>sudo systemctl start iscsid</codeblock>
```

### Mermaid Diagrams

Mermaid code blocks are automatically rendered to PNG images and stored in `dita_output/images/`.

````markdown
```mermaid
graph LR
    A[Host] --> B[Switch]
    B --> C[Storage]
```
````

**DITA Output:**
```xml
<fig>
    <image href="../images/rhel-iscsi-best-practices-diagram-01.png" scope="local">
        <alt>Diagram</alt>
    </image>
</fig>
```

---

## Tables

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Cell A   | Cell B   | Cell C   |
| Cell D   | Cell E   | Cell F   |
```

**DITA Output:**
```xml
<table>
    <tgroup cols="3">
        <thead>
            <row>
                <entry>Column 1</entry>
                <entry>Column 2</entry>
                <entry>Column 3</entry>
            </row>
        </thead>
        <tbody>
            <row>
                <entry>Cell A</entry>
                <entry>Cell B</entry>
                <entry>Cell C</entry>
            </row>
            <row>
                <entry>Cell D</entry>
                <entry>Cell E</entry>
                <entry>Cell F</entry>
            </row>
        </tbody>
    </tgroup>
</table>
```

---

## Jekyll Includes

Jekyll include statements are inlined during conversion (with `--inline-includes` flag).

```markdown
{% include quickstart/disclaimer.md %}
```

The content of the referenced file is embedded directly into the DITA output.

---

## Images

Standard Markdown images are converted to DITA image elements.

```markdown
![Alt text](path/to/image.png)
```

**DITA Output:**
```xml
<image href="../images/image.png" scope="local">
    <alt>Alt text</alt>
</image>
```

---

## Topic Structure

### Task Topic (QUICKSTART)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "task.dtd">
<task id="t_rhel_iscsi_quickstart" xml:lang="en-US">
    <title>RHEL iSCSI Quickstart</title>
    <prolog>
        <metadata/>
    </prolog>
    <taskbody>
        <prereq>
            <!-- Prerequisites content -->
        </prereq>
        <steps>
            <step>
                <cmd>Step command</cmd>
                <info>Additional info</info>
            </step>
        </steps>
        <postreq>
            <!-- Next Steps content -->
        </postreq>
    </taskbody>
</task>
```

### Concept Topic (BEST-PRACTICES)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE concept PUBLIC "-//OASIS//DTD DITA Concept//EN" "concept.dtd">
<concept id="c_rhel_iscsi_best-practices_architecture" xml:lang="en-US">
    <title>Architecture Overview</title>
    <prolog>
        <metadata/>
    </prolog>
    <conbody>
        <section id="section_id">
            <title>Section Title</title>
            <p>Content...</p>
        </section>
    </conbody>
</concept>
```

---

## Excluded Content

The following content is **not** converted to DITA:

| Content | Reason |
|---------|--------|
| Troubleshooting sections | Excluded by converter |
| YAML front matter | Stripped during parsing |
| HTML comments | Not processed |

---

## File Naming Conventions

| Type | Prefix | Example |
|------|--------|---------|
| Task topics | `t_` | `t_rhel_iscsi_quickstart.dita` |
| Concept topics | `c_` | `c_rhel_iscsi_best-practices_firewall.dita` |
| Reference topics | `c_` | `c_glossary.dita`, `c_network-concepts.dita` |

---

## Heretto Compatibility

All DITA output includes:

- `xml:lang="en-US"` attribute on root elements
- `scope="local"` on image references
- Empty `<metadata/>` block in `<prolog>` for external metadata management
- Proper `<p>` wrapping inside all `<li>` elements

---

## Running the Converter

```bash
# Full conversion with diagrams
python scripts/convert_to_dita.py --inline-includes --section-maps --organize-sections

# Test run (skip diagram generation)
python scripts/convert_to_dita.py --inline-includes --section-maps --organize-sections --skip-diagrams

# Convert specific distribution/protocol
python scripts/convert_to_dita.py --inline-includes -d rhel -p iscsi --section-maps --organize-sections
```

### Output Structure

```
dita_output/
├── images/       # PNG diagrams from Mermaid
├── maps/         # DITA navigation maps (.ditamap)
├── topics/       # DITA topics organized by distribution
│   ├── common/   # Glossary, network-concepts, multipath-concepts
│   ├── rhel/
│   ├── debian/
│   └── ...
└── warehouse/    # (Empty when using --inline-includes)
```

