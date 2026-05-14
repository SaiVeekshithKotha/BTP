# Method 3: Non-Semantic Table Extraction (VIPS + MDR)

This directory contains an implementation for extracting tables from modern web pages that do not use `<table>` tags or ARIA roles, relying instead on visual layout and repetitive patterns.

## What It Does & How It Works

**What it does:** Many modern websites represent data in grid-like formats using `<div>` elements, CSS Flexbox, or Grid layouts without any semantic markers. This method identifies these "visual tables" by analyzing the spatial relationships between elements and detecting repetitive structural patterns.

**How it works:**
The extraction follows a robust 8-phase pipeline:
1. **Visual Segmentation (VIPS)**: Partitions the webpage into visual blocks based on visual cues like borders, background colors, and whitespace gaps.
2. **Candidate Selection**: Filters blocks using heuristics (size similarity, text density) to find potential table areas.
3. **Pattern Detection (MDR)**: Uses Mining Data Records (MDR) to detect repeated structural patterns (Levenshtein distance + clustering), identifying potential rows.
4. **Row & Column Alignment**: Groups detected patterns into rows and aligns them into columns based on spatial coordinates and DOM boundaries.
5. **Header & Validation**: Identifies header rows through visual/content analysis and validates the final table quality.

## How to Run the Code

### 1. Installation
It is recommended to use a virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install selenium webdriver-manager beautifulsoup4
```

### 2. Run Directly (CLI)
The `method_3.py` script is configured to run a test against the included `test_vips.html` file, which contains Flexbox and CSS Grid table examples.

```bash
python method_3.py
```
*This will execute the full 8-phase pipeline and print the extracted tables and their metadata to the terminal.*

### 3. Quick Start (Importing)

*Note: The code below should be put in a new Python file within this directory.*
```python
from method_3 import extract_tables

# Extract tables from a URL
tables = extract_tables("https://example.com/complex-data", headless=True)

for table in tables:
    print(f"Extracted Table {table['id']} with {len(table['rows'])} rows")
```

## Directory Contents
- `method_3.py`: The core implementation of the VIPS + MDR extraction pipeline.
- `method_3.md`: Detailed design document and theoretical background.
- `test_vips.html`: Local test file with non-semantic (Flexbox/Grid) table structures.
