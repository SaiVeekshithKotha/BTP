# ARIA Role-Based Table Detection

**Design Document**

---

## 📋 Table of Contents

- [Problem Statement](#problem-statement)
- [Core Idea](#core-idea)
- [Assumptions](#assumptions)
- [High-Level Architecture](#high-level-architecture)
- [Phase-by-Phase Pipeline](#phase-by-phase-pipeline)
- [Strengths of the Approach](#strengths-of-the-approach)
- [Known Limitations](#known-limitations)

---

## Problem Statement

Modern web applications increasingly prioritize **accessibility** and **semantic markup** by using ARIA (Accessible Rich Internet Applications) roles to convey structure to assistive technologies. Many frameworks and component libraries implement table-like structures using:

- `<div role="table">`
- `<div role="row">`
- `<div role="cell">` or `<div role="gridcell">`
- `<div role="columnheader">` or `<div role="rowheader">`

**Challenge**: These structures are **semantically marked as tables** through ARIA attributes but do not use traditional `<table>`, `<tr>`, `<td>` HTML elements. Standard HTML table parsers fail to extract data from these ARIA-based tables.

### Objective

Extract tabular data from webpages that use ARIA roles to define table structure by:
- **Identifying ARIA table roles** in the DOM
- **Parsing the hierarchical structure** defined by ARIA relationships
- **Extracting cell content** while preserving row and column relationships

---

## Core Idea

This approach leverages the **explicit semantic information** provided by ARIA roles to detect and extract tables.

### Key Principle

> If developers have explicitly marked elements with table-related ARIA roles, we can trust this semantic information to identify table structure without relying on visual layout analysis.

### ARIA Table Roles

The following ARIA roles define table structure:

| ARIA Role | Purpose | HTML Equivalent |
|-----------|---------|-----------------|
| `role="table"` | Container for tabular data | `<table>` |
| `role="grid"` | Interactive table with keyboard navigation | `<table>` (interactive) |
| `role="rowgroup"` | Groups rows (thead, tbody, tfoot) | `<thead>`, `<tbody>`, `<tfoot>` |
| `role="row"` | Table row | `<tr>` |
| `role="columnheader"` | Column header cell | `<th scope="col">` |
| `role="rowheader"` | Row header cell | `<th scope="row">` |
| `role="cell"` | Data cell | `<td>` |
| `role="gridcell"` | Interactive data cell | `<td>` (interactive) |

---

## Assumptions

The following assumptions guide this approach:

1. The webpage uses **proper ARIA markup** for table structures
2. ARIA roles follow **WAI-ARIA specifications** correctly
3. The DOM is **fully loaded** (including dynamic content)
4. ARIA attributes are **not misleading** or incorrectly applied
5. This phase does **not handle** improperly nested or malformed ARIA structures

---

## High-Level Architecture

```
Rendered Webpage (DOM)
        ↓
ARIA Role Discovery
        ↓
Table Container Identification
        ↓
Row Extraction
        ↓
Cell Extraction & Ordering
        ↓
Header Detection
        ↓
Table Validation
        ↓
Structured Table Output
```

---

## Phase-by-Phase Pipeline

### Phase 0: Page Loading & DOM Access

#### Input
- URL or raw HTML

#### Process
Load the webpage and ensure:
- DOM is fully constructed
- JavaScript has executed (for dynamically rendered content)
- ARIA attributes are present in the DOM

#### Output
- Complete DOM tree with ARIA attributes

---

### Phase 1: ARIA Role Discovery

#### Objective
Scan the DOM for elements with table-related ARIA roles.

#### Method

Use CSS selectors or XPath to find elements with ARIA table roles:

```javascript
// Find all table containers
document.querySelectorAll('[role="table"], [role="grid"]')

// Find all rows
document.querySelectorAll('[role="row"]')

// Find all cells
document.querySelectorAll('[role="cell"], [role="gridcell"], [role="columnheader"], [role="rowheader"]')
```

#### Output
- List of potential **table container elements**
- Associated child elements with row/cell roles

---

### Phase 2: Table Container Identification

#### Objective
Identify valid table containers and establish their boundaries.

#### Process

For each element with `role="table"` or `role="grid"`:

1. **Verify it contains rows**: Check for child/descendant elements with `role="row"`
2. **Establish hierarchy**: Identify if `role="rowgroup"` elements exist (for thead/tbody/tfoot distinction)
3. **Validate structure**: Ensure rows contain cells

#### Validation Criteria

A valid ARIA table container must:
- Have `role="table"` or `role="grid"`
- Contain at least one element with `role="row"`
- Rows must contain elements with cell-related roles

#### Output
- List of **validated table containers**
- Hierarchical structure (table → rowgroups → rows → cells)

---

### Phase 3: Row Extraction

#### Objective
Extract all rows from each table container in document order.

#### Method

For each table container:

1. **Find all row elements**: Query for `[role="row"]` within the container
2. **Preserve order**: Maintain DOM order (top to bottom)
3. **Group by rowgroup**: If `role="rowgroup"` exists, separate thead/tbody/tfoot rows

#### Handling Row Groups

```
Table Container
├── rowgroup (thead)
│   └── row (header row)
├── rowgroup (tbody)
│   ├── row (data row 1)
│   ├── row (data row 2)
│   └── row (data row 3)
└── rowgroup (tfoot)
    └── row (footer row)
```

#### Output
- Ordered list of **row elements** per table
- Row group classification (header/body/footer)

---

### Phase 4: Cell Extraction & Ordering

#### Objective
Extract cells from each row and determine column positions.

#### Method

For each row:

1. **Find all cell elements**: Query for elements with:
   - `role="cell"`
   - `role="gridcell"`
   - `role="columnheader"`
   - `role="rowheader"`

2. **Determine order**: Sort cells by:
   - **DOM order** (default)
   - **aria-colindex** attribute (if present)
   - **Visual position** (x-coordinate as fallback)

3. **Handle spanning**: Check for:
   - `aria-colspan`: Cell spans multiple columns
   - `aria-rowspan`: Cell spans multiple rows

#### ARIA Attributes for Cell Positioning

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `aria-colindex` | Explicit column position | `aria-colindex="3"` |
| `aria-colspan` | Number of columns spanned | `aria-colspan="2"` |
| `aria-rowindex` | Explicit row position | `aria-rowindex="5"` |
| `aria-rowspan` | Number of rows spanned | `aria-rowspan="3"` |

#### Output
- **Cell grid** for each table
- Cell content with position information
- Spanning information preserved

---

### Phase 5: Header Detection

#### Objective
Identify header cells to distinguish them from data cells.

#### Method

Headers are detected through:

1. **ARIA role detection**:
   - `role="columnheader"` → Column header
   - `role="rowheader"` → Row header

2. **Row group analysis**:
   - Cells in `role="rowgroup"` with implicit thead semantics

3. **Position heuristics**:
   - First row often contains headers (if not explicitly marked)

#### Header Types

**Column Headers**: Define column meanings
```html
<div role="row">
  <div role="columnheader">Name</div>
  <div role="columnheader">Age</div>
  <div role="columnheader">City</div>
</div>
```

**Row Headers**: Define row meanings
```html
<div role="row">
  <div role="rowheader">Q1 2024</div>
  <div role="cell">$1.2M</div>
  <div role="cell">$800K</div>
</div>
```

#### Output
- **Header rows** (column headers)
- **Header cells** within data rows (row headers)
- **Data cells** (non-header cells)

---

### Phase 6: Table Validation

#### Objective
Validate that extracted structures represent genuine tables.

#### Validation Criteria

A structure is accepted as a valid table if:

- **Minimum row count**: ≥ 2 rows (including headers)
- **Consistent column count**: Most rows have the same number of cells (accounting for colspan)
- **Proper nesting**: Cells are properly contained within rows
- **Content presence**: Cells contain extractable text or meaningful content
- **No malformed ARIA**: Roles are properly nested according to WAI-ARIA spec

#### Rejection Criteria

Reject structures that:
- Have only one row (likely not a table)
- Have highly inconsistent column counts (likely a list or menu)
- Contain no text content (decorative elements)
- Have improperly nested ARIA roles

#### Output
- **Validated tables** ready for extraction
- **Rejected structures** with reasons

---

### Phase 7: Content Extraction

#### Objective
Extract text content from cells while preserving structure.

#### Method

For each cell:

1. **Extract text content**: Use `textContent` or `innerText`
2. **Clean whitespace**: Normalize spaces and line breaks
3. **Handle nested elements**: Extract text from child elements
4. **Preserve links**: Optionally extract `href` attributes from links
5. **Handle images**: Extract `alt` text or `aria-label` for images

#### Special Cases

**Interactive cells** (`role="gridcell"`):
- May contain buttons, inputs, or links
- Extract both text and interactive element information

**Cells with aria-label**:
- Prefer `aria-label` over visible text for screen reader content

**Empty cells**:
- Preserve as empty strings to maintain grid structure

#### Output
- **Text content** for each cell
- **Metadata** (links, labels, interactive elements)

---

### Phase 8: Table Reconstruction

#### Output Format

Structured table representation:

```json
{
  "table_id": "table_1",
  "aria_role": "table",
  "headers": {
    "column_headers": ["Name", "Age", "City"],
    "row_headers": []
  },
  "rows": [
    {
      "row_index": 0,
      "is_header": true,
      "cells": [
        {"content": "Name", "role": "columnheader", "colspan": 1},
        {"content": "Age", "role": "columnheader", "colspan": 1},
        {"content": "City", "role": "columnheader", "colspan": 1}
      ]
    },
    {
      "row_index": 1,
      "is_header": false,
      "cells": [
        {"content": "Alice", "role": "cell", "colspan": 1},
        {"content": "30", "role": "cell", "colspan": 1},
        {"content": "New York", "role": "cell", "colspan": 1}
      ]
    }
  ],
  "metadata": {
    "total_rows": 2,
    "total_columns": 3,
    "has_rowgroups": false
  }
}
```

> **Note**: This output preserves **ARIA semantic information** alongside extracted data.

---

## Strengths of the Approach

| Strength | Description |
|----------|-------------|
| **Semantic accuracy** | Leverages explicit developer intent through ARIA roles |
| **Accessibility-first** | Works with properly accessible web applications |
| **Computationally efficient** | Simple DOM queries, no visual analysis required |
| **Framework-agnostic** | Works with any framework that uses ARIA (React, Vue, Angular) |
| **Handles complex structures** | Supports rowspan, colspan, row/column headers |
| **No rendering required** | Can work on raw HTML without browser rendering |
| **Predictable** | Deterministic extraction based on explicit markup |

---

## Known Limitations

| Limitation | Explanation |
|------------|-------------|
| **Requires proper ARIA** | Fails if developers don't use ARIA roles correctly |
| **Not universal** | Many tables still use `<div>` without ARIA roles |
| **Trusts developers** | Assumes ARIA roles accurately reflect structure |
| **No visual validation** | Cannot detect visually broken tables with correct ARIA |
| **Limited to compliant sites** | Only works on accessibility-conscious websites |
| **Misuse vulnerability** | Incorrect ARIA usage leads to incorrect extraction |
| **Dynamic content** | Requires waiting for JavaScript to render ARIA attributes |

> **Note**: This approach is **complementary** to visual methods. It excels where ARIA is used but fails where it's absent.

---

