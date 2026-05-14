# Method 1: ARIA Role-Based Table Detection

This directory contains an implementation for extracting tabular data from modern web applications that use ARIA (Accessible Rich Internet Applications) roles to define table structures instead of traditional HTML `<table>` tags.

## What It Does & How It Works

**What it does:** Many modern web frameworks use `<div>` or `<span>` elements with CSS Grid or Flexbox to build tables. To ensure accessibility, these elements are often marked with ARIA roles such as `role="table"`, `role="row"`, and `role="cell"`. This tool identifies these semantic markers to extract data that standard table parsers would miss.

**How it works:**
1. **DOM Access**: Uses Selenium to render the page and execute JavaScript, ensuring dynamic content is fully loaded.
2. **Role Discovery**: Scans the DOM for elements with table-related ARIA roles.
3. **Container Identification**: Validates that detected containers have a logical table structure (rows containing cells).
4. **Data Extraction**:
   - **Rows**: Extracts elements with `role="row"`, respecting document order and `role="rowgroup"` (thead/tbody).
   - **Cells**: Extracts cells (`role="cell"`, `role="gridcell"`, etc.) and handles spanning using `aria-colspan` and `aria-rowspan`.
   - **Ordering**: Uses `aria-colindex` or visual x-coordinates (via bounding boxes) to ensure correct column alignment.
5. **Validation**: Checks for minimum row/column counts and data density to filter out non-table structures.

## How to Run the Code

### 1. Installation
Install the required dependencies:
```bash
pip install selenium webdriver-manager
```

### 2. Run Directly (CLI)
The `method_2.py` script is configured to run a test against the included `test_aria.html` file.

```bash
python method_2.py
```
*This will initialize a Chrome browser (via Selenium), extract the ARIA-based tables, and print the results to the terminal.*

### 3. Quick Start (Importing)

*Note: The code below should be put in a new Python file within this directory.*
You can use the extractor in your own projects:

```python
from method_2 import ARIATableExtractor

extractor = ARIATableExtractor()
tables = extractor.extract_tables("https://example.com/aria-table-page")

for table in tables:
    print(f"Found table with {len(table.rows)} rows")
```

## Directory Contents
- `method_2.py`: The main implementation of the ARIA table extractor.
- `method_2.md`: Detailed design document for this method.
- `test_aria.html`: A sample HTML file containing various ARIA-based table structures for testing.
