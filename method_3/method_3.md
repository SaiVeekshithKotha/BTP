# Non-Semantic Table Extraction Using VIPS and MDR

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

Modern webpages often represent tabular data **without using `<table>` tags**, relying instead on:

- `<div>`-based layouts
- CSS Grid / Flexbox
- Component-based frameworks (React, Vue, Angular)

**Challenge**: Traditional HTML parsers fail in these cases because **semantic structure does not reflect visual structure**.

### Objective

Extract tables from such webpages by analyzing:
- **Visual layout** (how elements are rendered on screen)
- **Repetitive structural patterns** (similar DOM structures)

---

## Core Idea

This approach combines two classical algorithms:

### 1. VIPS (Vision-based Page Segmentation)
→ Segments a rendered webpage into visually coherent blocks.

### 2. MDR (Mining Data Records)
→ Detects repeated structural patterns within those blocks.

### Table Definition

A table is identified as:
> A visually coherent block containing multiple repeated sub-blocks that align spatially into a grid-like structure.

---

## Assumptions

The following assumptions guide this approach:

1. The webpage is **fully rendered** (DOM + CSS applied)
2. Visual layout **reflects semantic grouping**
3. Table rows are **structurally similar**
4. Columns are **visually aligned**
5. This phase does **not handle** infinite scroll or lazy loading (handled later)

---

## High-Level Architecture

```
Rendered Webpage
        ↓
VIPS (Visual Segmentation)
        ↓
Candidate Block Selection
        ↓
MDR (Repeated Pattern Mining)
        ↓
Row Detection
        ↓
Column Alignment
        ↓
Table Validation
        ↓
Structured Table Output
```

---

## Phase-by-Phase Pipeline

### Phase 0: Page Rendering

#### Input
- URL or raw HTML

#### Process
Load page using a rendering engine (browser / headless browser) and extract:
- DOM tree
- Computed CSS
- Bounding boxes for each element

#### Output
- Rendered DOM with layout metadata

---

### Phase 1: VIPS – Visual Page Segmentation

#### Objective
Partition the webpage into visually meaningful blocks, **independent of HTML semantics**.

#### Method
VIPS recursively divides the page based on:
- Whitespace separation
- Borders and background differences
- Font size and style changes
- Layout differences (block, inline, grid, flex)

Each block is assigned:
- **Bounding box** (x, y, width, height)
- **DOM subtree** (underlying HTML elements)
- **Degree of Coherence (DoC)** (visual cohesion metric)

#### Output
- A **Visual Block Tree**, representing the page structure at multiple granularities

---

### Phase 2: Candidate Block Selection

#### Objective
Reduce the search space by identifying blocks that **may contain tables**.

#### Heuristics

A VIPS block is considered a **candidate** if:
- It contains **many child blocks**
- Children are **vertically aligned**
- Children have **similar sizes**
- **Text density** is high

#### Output
- A small set of **candidate container blocks**

---

### Phase 3: MDR – Mining Data Records

#### Objective
Detect **repeated structural patterns** inside candidate blocks.

#### Definition: Data Record

A data record corresponds to one repeated visual unit (potential table row), represented by:
- DOM subtree structure
- Tag sequence (ignoring text)
- CSS class patterns
- Relative layout features

#### Process

1. Compare child blocks within a candidate container
2. Identify structurally similar subtrees
3. Group them by frequency

#### Output

Repeated patterns with occurrence counts:
```
Pattern P → appears N times
```

---

### Phase 4: Row Identification

#### Objective
Convert MDR patterns into **table rows**.

#### Logic

If a pattern:
- Appears **multiple times**
- Occurs under the **same container**
- Is **vertically ordered**

Then:
- Each occurrence = **one table row**

#### Output
- Ordered list of **row blocks**

---

### Phase 5: Column Identification

#### Objective
Infer columns using **spatial alignment**.

#### Method

**For each row:**
1. Extract child elements
2. Sort by horizontal (x-axis) position

**Across rows:**
1. Cluster elements with similar x-ranges
2. Each cluster represents a **column**

#### Output
- **Row × Column grid structure**

---

### Phase 6: Header Detection

#### Objective
Identify **header rows** if present.

#### Heuristics

Headers are detected based on:
- **Visual distinction** (bold text, background color)
- **Different font size**
- **Appears before repeated rows**
- **Not part of MDR pattern set** (unique structure)

#### Output
- Header row(s)
- Data rows

---

### Phase 7: Table Validation

#### Objective
Filter out **false positives** such as lists, cards, or menus.

#### Validation Criteria

A structure is accepted as a table if:
- **Consistent column count** across rows
- **Strong column alignment** (x-positions match)
- **Rectangular grid** structure
- **Minimum row count** (e.g., ≥ 3)
- **Predominantly textual content**

Only validated structures are accepted as tables.

---

### Phase 8: Table Reconstruction

#### Output Format

Structured table representation:

```json
{
  "headers": ["Column A", "Column B", "Column C"],
  "rows": [
    ["Row1-A", "Row1-B", "Row1-C"],
    ["Row2-A", "Row2-B", "Row2-C"]
  ]
}
```

> **Note**: This output is **independent of the original HTML structure**.

---

## Strengths of the Approach

| Strength | Description |
|----------|-------------|
| **No `<table>` dependency** | Works with any visual table representation |
| **Framework-agnostic** | Robust to React, Vue, Angular, etc. |
| **Interpretable** | Deterministic, rule-based approach |
| **Language-agnostic** | Works across different human languages |
| **No training required** | No need for labeled datasets |

---

## Known Limitations

| Limitation | Explanation |
|------------|-------------|
| **Computational cost** | Full VIPS is expensive for large pages |
| **Irregular tables** | MDR assumes repetition; fails on unique rows |
| **Nested tables** | Hard to disambiguate parent/child relationships |
| **Lazy loading** | Needs viewport handling and scrolling |
| **Responsive layouts** | Layout changes with screen size affect detection |

> **Note**: These are design trade-offs, not implementation flaws.

---