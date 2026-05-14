# Basic Table Parser

A robust Python-based HTML table extraction tool that intelligently parses tables from web pages and local HTML files, handling complex table structures including rowspan, colspan, and nested tables.

---

## 📋 Table of Contents

- [What It Does & How It Works](#what-it-does--how-it-works)
- [Features](#features)
- [Installation](#installation)
- [How to Run the Code](#how-to-run-the-code)
- [Algorithm Deep Dive](#algorithm-deep-dive)
- [API Reference](#api-reference)
- [Edge Cases & Design Decisions](#edge-cases--design-decisions)
- [Known Limitations](#known-limitations)
- [Future Improvements](#future-improvements)

---

## What It Does & How It Works

**What it does:** This parser is a Python tool designed to robustly extract tabular data from standard HTML `<table>` elements found in web pages or local files. It is specifically built to overcome the limitations of simple scraping scripts by correctly aligning data in tables that use complex `rowspan` and `colspan` attributes, while intelligently filtering out nested tables.

**How it works:** The parser employs a **grid-based extraction algorithm**. First, it calculates the maximum dimensions of a table (rows × columns) based on its structure. It then constructs an empty 2D grid and sequentially populates it by traversing the HTML cells. When a cell spans multiple rows or columns, the algorithm actively tracks its occupancy and duplicates the cell's content across all corresponding grid coordinates. This ensures that every row extracted has an identical number of columns, perfectly mirroring the table's visual layout.

### High-Level Algorithm Flow

```
Input Source (URL/File)
    ↓
Fetch HTML Content
    ↓
Find All <table> Tags (excluding nested tables)
    ↓
For Each Table:
    ├─ Calculate Table Dimensions (rows × columns)
    ├─ Build 2D Grid with Occupancy Tracking
    ├─ Fill Grid (handling rowspan/colspan)
    ├─ Detect Headers (multiple strategies)
    └─ Export to CSV (optional)
    ↓
Return Structured Data
```

---

## Core Capabilities / Major Features :

- **Dual Input Support**: Works with both URLs and local HTML files
- **Grid-Based Extraction**: Accurately handles `rowspan` and `colspan` attributes
- **Smart Header Detection**: Multiple fallback strategies for identifying table headers
- **Nested Table Handling**: Intelligently filters out nested tables to avoid duplication
- **Semantic HTML Awareness**: Respects `<thead>`, `<tbody>`, and `<tfoot>` sections
- **Orphan Row Detection**: Handles malformed HTML with rows outside semantic sections
- **CSV Export**: Automatic export to CSV format with proper formatting
- **Robust Error Handling**: Comprehensive exception handling with descriptive messages
- **Multi-level Header Support**: Extracts the most relevant header row from complex multi-row headers
- **Mixed Cell Type Handling**: Processes both `<th>` and `<td>` cells (useful for row headers)
- **Empty Row Filtering**: Automatically skips empty rows from malformed HTML
- **Layout Table Detection**: Identifies and skips non-data tables (< 2 rows or columns)
- **Debug Output**: Detailed logging for troubleshooting complex tables

---

## Installation

### Dependencies

```bash
Python 3.7+
```


```bash
pip install requests beautifulsoup4
```

### Project Directory Structure

```
basic_table_parser/
├── basic_table_parser.py    # Main parser implementation
├── README.md                 # This documentation
└── test_span.html           # Test file (optional)
```

---

## How to Run the Code

You can run the script directly to see it in action, or import it into your own Python projects.

### 1. Run Directly (Command Line)

By default, the `__main__` block at the bottom of the script is configured to test the parser on the provided `test_span.html` file (or you can edit the `source` variable to point to any URL).

```bash
python basic_table_parser.py
```
*This will execute the parser and print the extracted table dimensions, headers, and the first few rows directly to your terminal.*

### 2. Import as a Module (Quick Start)

```python
from basic_table_parser import parse_tables

# Extract all tables from a webpage
results = parse_tables("https://example.com/data.html", extract_to_csv=True, use_grid=True)

print(f"Found {len(results)} table(s)")
for i, table in enumerate(results, 1):
    print(f"Table {i}: {len(table['rows'])} rows, {len(table['headers'])} headers")
```

### Example 2: Parse from Local HTML File

```python
from basic_table_parser import parse_tables

# Extract tables from a local file
results = parse_tables("path/to/file.html", extract_to_csv=False, use_grid=True)

# Access the data
for table in results:
    print("Headers:", table['headers'])
    print("First row:", table['rows'][0] if table['rows'] else "No data")
```

### Example 3: Manual Control

```python
from basic_table_parser import fetch_html, find_tables, extract_table_with_grid

# Step-by-step extraction
html_content = fetch_html("https://example.com")
tables = find_tables(html_content)

for table_tag in tables:
    data = extract_table_with_grid(table_tag)
    print(data['headers'])
    print(data['rows'])
```

---

## Algorithm Deep Dive

### 1. Input Acquisition: `fetch_html()`

**Purpose**: Retrieve HTML content from either a URL or local file.

**Logic**:
- Detects source type by checking for `http://` or `https://` prefix
- **URL Path**: Uses `requests` library with 10-second timeout
  - Automatically raises exceptions for 4xx/5xx HTTP errors
- **File Path**: Reads from filesystem with UTF-8 encoding
  - Handles `FileNotFoundError` and `IOError` gracefully

**Error Handling**:
- Network failures (timeout, connection errors)
- File not found or permission issues
- Invalid file encoding

---

### 2. Table Discovery: `find_tables()`

**Purpose**: Locate all top-level table elements in the HTML document.

**Algorithm**:
1. Parse HTML using BeautifulSoup's `html.parser`
2. Find all `<table>` tags in the document
3. **Filter nested tables**: Only keep tables that don't have a parent `<table>` tag

**Why Filter Nested Tables?**
> Nested tables (tables within tables) would be extracted twice—once as part of the outer table and once independently. By filtering them out, we avoid data duplication and focus on the primary table structure.

**Edge Case Handling**:
- Returns empty list if HTML is empty or contains no tables
- Gracefully handles malformed HTML that BeautifulSoup can parse

---

### 3. Dimension Calculation: `calculate_max_columns()`

**Purpose**: Determine the maximum number of columns across all rows in a table.

**Algorithm**:
1. Collect rows from semantic sections (`<thead>`, `<tbody>`)
   - **Note**: `<tfoot>` is intentionally excluded from calculations
2. Detect "orphan rows" (direct `<tr>` children of `<table>` not in any section)
3. For each row:
   - Find all `<td>` and `<th>` cells
   - Sum up their `colspan` values (default: 1)
4. Return the maximum column count found

**Why This Matters**:
> Tables with rowspan/colspan can have rows with different numbers of actual cell elements. This function calculates the "true" column count by accounting for spans, ensuring our grid is properly sized.

**Design Decision**:
- Orphan rows trigger a warning but are still processed
- `<tfoot>` is excluded to avoid footer rows affecting dimension calculations

---

### 4. Grid-Based Extraction: `extract_table_with_grid()` {Core Algorithm}

**Main Purpose**: The core algorithm that extracts table data while correctly handling rowspan and colspan.

#### **Phase 1: Row Collection & Classification**

```python
# Separate rows into semantic sections
thead_rows = <thead> rows
tbody_rows = <tbody> rows + orphan rows
```

**Orphan Row Handling**:
- Orphan rows are `<tr>` tags that are direct children of `<table>` but not inside `<thead>`, `<tbody>`, or `<tfoot>`
- These are treated as data rows and added to `tbody_rows`

#### **Phase 2: Grid Initialization**

```python
num_rows = len(thead_rows) + len(tbody_rows)
num_cols = calculate_max_columns(table_content)

grid = [[None] * num_cols for _ in range(num_rows)]
occupied = {}  # Tracks which cells are filled
```

**Layout Table Detection**:
- Tables with < 2 rows or < 2 columns are considered "layout tables" (used for page structure, not data)
- These are skipped and return empty results

#### **Phase 3: Grid Filling (The Core Algorithm)**

```python
for row_index, tr in enumerate(all_rows):
    col_index = 0
    
    for cell in tr.find_all(['td', 'th']):
        # Skip occupied cells (from previous rowspan/colspan)
        while occupied.get((row_index, col_index)):
            col_index += 1
        
        # Extract span attributes
        rowspan = int(cell.get('rowspan', 1))
        colspan = int(cell.get('colspan', 1))
        cell_content = cell.get_text(strip=True)
        
        # Fill all spanned positions with the same content
        for r in range(rowspan):
            for c in range(colspan):
                target_row = row_index + r
                target_col = col_index + c
                
                if target_row < num_rows and target_col < num_cols:
                    grid[target_row][target_col] = cell_content
                    occupied[(target_row, target_col)] = True
        
        col_index += colspan
```

**Key Insights**:

1. **Occupancy Tracking**: The `occupied` dictionary prevents overwriting cells that are already filled by a previous cell's span
2. **Content Duplication**: Cells with spans have their content duplicated across all spanned positions
3. **Sequential Filling**: We process cells left-to-right, top-to-bottom, skipping over occupied positions
4. **Boundary Checking**: Safety checks ensure we don't write outside the grid

**Example**:

Consider this HTML:
```html
<table>
  <tr>
    <td rowspan="2">A</td>
    <td>B</td>
  </tr>
  <tr>
    <td>C</td>
  </tr>
</table>
```

The algorithm produces this grid:
```
| A | B |
| A | C |
```

Notice how "A" appears in both rows because of `rowspan="2"`.

#### **Phase 4: Header Detection**

The parser uses a **multi-strategy / multi-fallback approach** to identify headers:

**Strategy 1: Semantic `<thead>` (Preferred)**
```python
if thead_rows:
    headers = grid[len(thead_rows) - 1]  # Last row of thead
    rows = grid[len(thead_rows):]
```

> **Why the last row?** Multi-level headers often have "super-headers" in the first rows and the actual column headers in the last row. For example:
> ```
> | Company Information (colspan=3) |
> | Name | Address | Phone |
> ```

**Strategy 2: All-`<th>` First Row (Fallback)**
```python
if all(cell.name == 'th' for cell in first_row_cells):
    headers = grid[0]
    rows = grid[1:]
```

**Strategy 3: No Headers**
```python
else:
    headers = []
    rows = grid
```

#### **Phase 5: Data Cleanup**

```python
# Replace None with empty strings
headers = [h if h is not None else '' for h in headers]
rows = [[cell if cell is not None else '' for cell in row] for row in rows]
```

**Why?**
- `None` values can appear in the grid if there are gaps in the table structure
- Empty strings are more user-friendly for CSV export and data processing

---

### 5. Simple Extraction: `extract_table_data()`

**Purpose**: A simpler extraction method that doesn't use the grid algorithm.

**When to Use**:
- Tables without rowspan/colspan
- Quick extraction where perfect alignment isn't critical
- Performance-sensitive scenarios (slightly faster)

**Limitations**:
- Does NOT handle rowspan/colspan correctly
- Rows may have inconsistent column counts

**Usage**:
```python
parse_tables(source, use_grid=False)  # Uses this simpler method
```

---

### 6. CSV Export: `export_to_csv()`

**Purpose**: Write extracted table data to a CSV file.

**Features**:
- Automatically adds `.csv` extension
- Writes headers as the first row (if present)
- Uses UTF-8 encoding for international characters
- Properly escapes special characters (commas, quotes, newlines)

**File Naming**:
```python
# Tables are numbered sequentially
Table_1.csv
Table_2.csv
Table_3.csv
```

---

### 7. Orchestration: `parse_tables()`

**Purpose**: Main entry point that coordinates the entire extraction pipeline.

**Parameters**:
- `source` (str): URL or file path
- `extract_to_csv` (bool): Whether to export tables to CSV files (default: True)
- `use_grid` (bool): Whether to use grid-based algorithm (default: True)

**Flow**:
```python
1. Fetch HTML content
2. Find all table elements
3. For each table:
   a. Extract data (grid or simple method)
   b. Optionally export to CSV
4. Return list of all extracted tables
```

---

### **Data Types**

#### `TableData` (TypedDict)

```python
{
    "headers": List[str],  # Column headers
    "rows": List[List[str]]  # Data rows
}
```
---
### **Functions**

#### `fetch_html(source: str) -> str`

Fetches HTML content from a URL or local file.

**Parameters**:
- `source`: URL (starting with `http://` or `https://`) or file path

**Returns**: HTML content as string

**Raises**: `Exception` if fetch fails

---

#### `find_tables(html_content: str) -> List[Tag]`

Finds all top-level table elements.

**Parameters**:
- `html_content`: HTML string

**Returns**: List of BeautifulSoup `Tag` objects

**Raises**: `Exception` if parsing fails

---

#### `calculate_max_columns(table_content: Tag) -> int`

Calculates maximum column count.

**Parameters**:
- `table_content`: BeautifulSoup `Tag` representing a `<table>`

**Returns**: Integer column count

**Notes**: Excludes `<tfoot>` from calculations

---

#### `extract_table_with_grid(table_content: Tag) -> TableData`

Extracts table data using grid-based algorithm (handles rowspan/colspan).

**Parameters**:
- `table_content`: BeautifulSoup `Tag` representing a `<table>`

**Returns**: `TableData` dictionary

**Features**:
- Handles rowspan/colspan
- Multi-strategy header detection
- Layout table filtering
- Debug output

---

#### `extract_table_data(table_content: Tag) -> TableData`

Extracts table data using simple algorithm (no rowspan/colspan handling).

**Parameters**:
- `table_content`: BeautifulSoup `Tag` representing a `<table>`

**Returns**: `TableData` dictionary

**Use Case**: Simple tables without spans

---

#### `parse_tables(source: str, extract_to_csv: bool = True, use_grid: bool = True) -> List[TableData]`

Main function to parse all tables from a source.

**Parameters**:
- `source`: URL or file path
- `extract_to_csv`: Export to CSV files (default: True)
- `use_grid`: Use grid-based algorithm (default: True)

**Returns**: List of `TableData` dictionaries

**Raises**: `Exception` if fetching or parsing fails

---

#### `export_to_csv(table_data: TableData, filename: str) -> None`

Exports table data to CSV file.

**Parameters**:
- `table_data`: Extracted table data
- `filename`: Output filename (`.csv` added automatically)

**Output**: Creates CSV file in current directory

---

#### `fancy_print(grid: List[List[str]]) -> None`

Prints grid in a human-readable format (for debugging).

**Parameters**:
- `grid`: 2D list representing table grid

**Output**: Prints to console with `|` separators

---

## Edge Cases & Design Decisions

#### 1. Nested Tables
**Problem**: Tables within tables would be extracted twice.

**Solution**: Filter out any `<table>` that has a parent `<table>` tag. Basically, only top level tables are extracted.

---

#### 2. Orphan Rows
**Problem**: Some HTML has `<tr>` tags directly under `<table>` without `<tbody>`.

**Solution**: Detect and include these "orphan rows" as data rows.
**Warning**: A warning is printed when orphan rows are detected.

---

#### 3. Mixed Cell Types
**Problem**: Some tables use `<th>` for row headers, not just column headers.

**Solution**: Process both `<th>` and `<td>` cells in data rows.

---


#### 4. Layout Tables
**Problem**: Some tables are used for page layout, not data (e.g., 1×1 tables).
**Solution**: Skip tables with < 2 rows or < 2 columns.

---

#### 5. `<tfoot>` Exclusion (Should be improved)
**Problem**: Footer rows can interfere with dimension calculations and data extraction.

**Solution**: `<tfoot>` is completely excluded from processing.
**Rationale**: Footer rows often contain summary data (totals, averages) that shouldn't be treated as regular data rows.

---

#### 6. Why Grid-Based Algorithm?
**Problem with Simple Extraction**:(Example for the grid based extraction algorithm)
```html
<tr>
  <td rowspan="2">A</td>
  <td>B</td>
</tr>
<tr>
  <td>C</td>
</tr>
```

**Simple extraction** would produce:
```
Row 1: ["A", "B"]
Row 2: ["C"]  # Misaligned!
```

**Grid-based extraction** produces:
```
Row 1: ["A", "B"]
Row 2: ["A", "C"]  # Correctly aligned!
```

---

#### 7. Why Duplicate Content for Spans?
**Chosen Approach**: Duplicate the content across all spanned cells.
**Rationale**:
- Easier to work with in downstream processing
- CSV export is more intuitive
- No need for special handling of `None` values

**Trade-off**: Slightly larger data structures, but better usability.

---

#### 8. Why Last Row of `<thead>` as Headers? (Should most likely to be improved)

**Observation**: Multi-level headers typically have:
- **Top rows**: Category labels with large colspan
- **Bottom row**: Actual column names
**Example**:
```
| Q1 Results (colspan=3) | Q2 Results (colspan=3) |
| Revenue | Profit | Loss | Revenue | Profit | Loss |
```
**Desired headers**: `["Revenue", "Profit", "Loss", "Revenue", "Profit", "Loss"]`
**Solution**: Use the last row of `<thead>`.

---

## Known Limitations

1. **Multi-level Headers** and **Headers Management**: 
    - Only the last header row is captured; hierarchical structure is lost. Approach for identifying headers is not robust yet.
    - Headers with colspan are duplicated, not combined with context from parent rows.

2. **No Column Type Detection**: 
    - All data is extracted as strings; no automatic type inference (numbers, dates, etc.).

3. **No Table Metadata**

4. **Only works for static HTML pages which have <table> tags**

---

## Possible(Hopefully) Future Improvements

#### 1. Hierarchical Header Support
**Goal**: Preserve multi-level header structure.
**Approach**: Flatten headers with parent context.
**Example**:
```
Input:
| Company (colspan=2) | Contact (colspan=2) |
| Name | ID | Email | Phone |

Output:
["Company - Name", "Company - ID", "Contact - Email", "Contact - Phone"]
```

---

#### 2. Configurable Logging
**Goal**: Control debug output verbosity.

**Approach**: Add logging levels (DEBUG, INFO, WARNING, ERROR).

---

#### 3. Data Type Inference
**Goal**: Automatically detect and convert data types.

**Approach**: Regex-based detection for numbers, dates, booleans.

---

#### 4. Table Metadata Extraction
**Goal**: Capture table captions, IDs, classes, and ARIA labels.

---
