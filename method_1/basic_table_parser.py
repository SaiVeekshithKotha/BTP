import requests
from typing import List , Dict , TypedDict
from bs4 import BeautifulSoup , Tag
import csv
import logging

# Type Declaration
class TableData(TypedDict):
    headers: List[str]
    rows: List[List[str]]

# Constants
URL_PREFIXES = ("http://", "https://")
DEFAULT_TIMEOUT = 10

# Configure logging
logger = logging.getLogger(__name__)

def set_log_level(level: str = "WARNING") -> None:
    """
    Set the logging level for the table parser.
    
    Args:
        level: Logging level as string. Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
               Default is "WARNING" which shows only warnings and errors.
    
    Examples:
        set_log_level("DEBUG")    # Show all debug information
        set_log_level("INFO")     # Show informational messages
        set_log_level("WARNING")  # Show only warnings and errors (default)
        set_log_level("ERROR")    # Show only errors
    """
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(levelname)s: %(message)s'
    )
    logger.setLevel(numeric_level)

# Set default log level to WARNING (only show warnings and errors)
set_log_level("WARNING")

def fetch_html(source: str) -> str:
    """
    Fetches HTML content from a URL or local file.
    
    Args:
        source: Either a URL (starting with http:// or https://) 
                or a local file path to an HTML file.
    
    Returns:
        The HTML content as a string.
    
    Raises:
        Exception: If URL request fails or file cannot be read.
    """

    if source.startswith(URL_PREFIXES) :
        # The Source is an url. Reads from the url.
        try :
            web_response = requests.get(source , timeout= DEFAULT_TIMEOUT)
            web_response.raise_for_status() # This basically raises any errors regarding the 4xx/5xx server codes
            return web_response.text
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch the web page for url {source} : {e}") 
        

    else :
        # The Source is filepath. Reads from the local file.
        try : 
            with open(source , "r" , encoding= "utf-8") as f:
                content = f.read()
            
            return content
        except FileNotFoundError:
            raise Exception(f"File not found : {source}")
        except IOError as e:
            raise Exception(f"Error Reading file {source} : {e}")
        
def find_tables(html_content: str) -> List[Tag]:
    """
    Finds all table elements from the HTML content.
    
    Args:
        html_content: HTML content as a string.

    Returns:
        List of BeautifulSoup Tag objects representing <table> elements.
        Returns empty list if no tables found.
    
    Raises:
        Exception: If HTML parsing fails.
    """

    # Some Edge cases:
    # If there are nested tables, for now this function returns all the tables (outer and inner). Later on should figure out what to do with the nested tables case. For now ignoring the nested tables, only extracting the outer one.

    if not html_content or not html_content.strip():
        return []

    try:
        # BeautifulSoup Object.
        soup = BeautifulSoup(html_content , "html.parser")

        # Each table is represented in str, from <table> to </table> 
        all_tables = soup.find_all('table')

        # We are for now ignoring the nested tables
        top_level_tables = []
        for table in all_tables:
            if not table.find_parent('table'):
                top_level_tables.append(table)
        
        return top_level_tables
    
    except Exception as e:
        raise Exception(f"Error in parsing HTML : {e}")
    
def extract_table_data(table_content: Tag) -> TableData:
    """
    Robustly extracts table data from a <table> element.
    
    Args:
        table_content: A BeautifulSoup Tag object representing a <table> element.
    
    Returns:
        A dictionary with 'headers' and 'rows':
        {
            "headers": ['Header1', 'Header2', ...],
            "rows": [['cell1', 'cell2', ...], ...]
        }
    
    Header Detection Strategy:
        1. If <thead> exists: Use the last row in <thead> as headers
        2. Otherwise: If first data row contains only <th> tags, treat as header
        3. Otherwise: Empty headers list
    
    Notes:
        - Handles both <th> and <td> cells in data rows (e.g., row headers)
        - Skips empty rows from malformed HTML
        - Multi-level headers: Only the last header row is captured
    """
    headers = []
    rows = []

    # 1. Attempting to find headers in semantic <thead>
    thead = table_content.find('thead')
    if thead:
        # Usually the last row in thead is the header (to account for super-headers)
        header_rows = thead.find_all('tr')
        if header_rows:
            headers = [th.get_text(strip=True) for th in header_rows[-1].find_all(['th', 'td'])]

    # 2. Define the search area for data. 
    # If tbody exists, use it. Otherwise, fall back to the main table
    tbody = table_content.find('tbody')
    row_search_area = tbody.find_all('tr') if tbody else table_content.find_all('tr')

    for tr in row_search_area:
        # SKIP LOGIC: 
        # If we are falling back to 'table_content', we might encounter the 'thead' rows again.
        if thead and tr in thead.find_all('tr'):
            continue
        
        # EXTRACT ALL CELLS:
        # Crucial Fix: Look for BOTH 'td' and 'th'. 
        cells = tr.find_all(['td', 'th'], recursive=False)
        
        # Parse text
        row_data = [cell.get_text(strip=True) for cell in cells]

        # HEADER FALLBACK (If no thead existed):
        # If we haven't found headers yet, and this is the first row,
        # and it looks like a header (all bold/th), treat it as header.
        if not headers and not rows and all(c.name == 'th' for c in cells):
            headers = row_data
            continue
        
        # Only add non-empty rows (to avoid empty tr tags often found in messy html)
        if row_data:
            rows.append(row_data)

    return {"headers": headers, "rows": rows}

def parse_tables(source: str , extract_to_csv: bool = True, use_grid: bool = True) -> List[TableData]:
    """
    Parse all tables from a URL or HTML file.
    
    Args:
        source: Either a URL (starting with http:// or https://) 
                or a local file path to an HTML file.
    
    Returns:
        List of dictionaries, each representing a table with 
        'headers' and 'rows' keys. Returns empty list if no tables found.
    
    Raises:
        Exception: If fetching or parsing fails.
    """
    
    # Fetch HTML content
    html_content = fetch_html(source)
    
    # Find all table elements
    tables = find_tables(html_content)
    
    # Extract data from each table
    tables_data = []
    for i , table in enumerate(tables):
        if use_grid:
            data = extract_table_with_grid(table_content= table)
        else:
            data = extract_table_data(table_content= table)
        
        tables_data.append(data)

        if extract_to_csv:
            export_to_csv(table_data=data , filename= f"Table_{i + 1}")

    return tables_data

def export_to_csv(table_data: TableData , filename: str) -> None:
    """ 
        Export the table data as a csv file.
        Params:
            table_data: extracted table data
            filename: filename
    """

    filename += ".csv"
    with open(filename , 'w' , newline= '', encoding= 'utf-8') as f:
        write = csv.writer(f)
        if table_data['headers']:
            write.writerow(table_data['headers'])
        write.writerows(table_data['rows'])

def calculate_max_columns(table_content: Tag) -> int:
    """
    Calculates the maximum number of columns in the given table data.

    Args:
        table_content: A BeautifulSoup Tag object representing a <table> element.

    Returns:
        A int value representing the maximum number of columns in the given table data.
    
    notes:
        - tfoot is not considered.
    """

    # rows = table_content.find_all('tr')
    rows = []
    
    # Collect rows from semantic sections
    thead = table_content.find('thead')
    tbody = table_content.find('tbody')
    tfoot = table_content.find('tfoot')
    
    if thead:
        rows.extend(thead.find_all('tr', recursive=False))
    if tbody:
        rows.extend(tbody.find_all('tr', recursive=False))

    # tfoot is excluded
    # if tfoot:
    #     rows.extend(tfoot.find_all('tr', recursive=False))
    
    # Finding orphan <tr> tags (direct children of <table>)
    all_direct_trs = table_content.find_all('tr', recursive=False)
    
    # Filtering out rows already in semantic sections (direct children of tables)
    section_rows = set(rows)
    orphan_rows = [tr for tr in all_direct_trs if tr not in section_rows]
    
    if orphan_rows:
        logger.warning(f"Found {len(orphan_rows)} orphan <tr> tag(s) outside semantic sections")
        rows.extend(orphan_rows)
    
    max_columns = 0

    for row in rows:
        current_columns = 0
        cells = row.find_all(['td' , 'th'])

        for cell in cells:
            colspan = int(cell.get('colspan' , 1))

            current_columns += colspan
        
        max_columns = max(max_columns , current_columns)
    
    return max_columns

def fancy_print(grid: List[List[str]]) -> None:
    """ 
    Printing the grid in a fancy way.
    Args:
        grid: 2D List representing the table grid.
    """

    for row in grid:
        print(" | ".join([cell if cell is not None else "" for cell in row]))
    print("\n")

def extract_table_with_grid(table_content: Tag) -> TableData:
    """
    Robustly extracts table data from a <table> element using a grid based algorithm.
    
    Args:
        table_content: A BeautifulSoup Tag object representing a <table> element.
    
    Returns:
        A dictionary with 'headers' and 'rows':
        {
            "headers": ['Header1', 'Header2', ...],
            "rows": [['cell1', 'cell2', ...], ...]
        }
    
    Grid Algorithm:
        - Builds a 2D grid to handle rowspan/colspan
        - Cells with spans are duplicated across the spanned area
        - Ensures consistent column count across all rows
    
    Header Detection Strategy:
        1. If <thead> exists: Last row in <thead> are treated as header rows
        2. Otherwise: If first data row contains only <th> tags, treat as header
        3. Otherwise: Empty headers list
    
    Notes:
        - Handles both <th> and <td> cells in data rows (e.g., row headers)
        - Skips empty rows from malformed HTML
        - Multi-level headers: Only the last header row is captured
        - Will be ignoring <tfoot> rows i.e. excluding completely.
    """

    # Finding all semantic sections
    thead = table_content.find('thead')
    tbody = table_content.find('tbody')
    tfoot = table_content.find('tfoot')

    # Rows by section
    thead_rows = []
    tbody_rows = []

    if thead:
        thead_rows = thead.find_all('tr' , recursive= False)
    if tbody:
        tbody_rows = tbody.find_all('tr' , recursive= False)

    # Finding orphan rows (direct children of <table>)
    all_direct_trs = table_content.find_all('tr', recursive=False)

    # Building the set of all rows in semantic sections (thead , tfoot , tbody)
    section_rows = set(thead_rows)
    if tbody_rows:
        section_rows.update(tbody_rows)
    if tfoot:
        section_rows.update(tfoot.find_all('tr', recursive=False))
    
    # Orphan rows = direct <tr> children NOT in any section
    orphan_rows = [tr for tr in all_direct_trs if tr not in section_rows]
    
    if orphan_rows:
        logger.warning(f"Found {len(orphan_rows)} orphan <tr> tag(s), adding to data rows")
    
    # Add orphan rows to tbody_rows (treat as data)
    tbody_rows.extend(orphan_rows)

    # Calculating the number of rows and number of columns
    all_rows = thead_rows + tbody_rows
    num_rows = len(all_rows)
    num_cols = calculate_max_columns(table_content)

    logger.debug(f"num_rows= {num_rows} , num_cols= {num_cols}")

    # Handle empty table
    if num_rows == 0 or num_cols == 0:
        return {"headers": [], "rows": []}
    
    if num_rows < 2 or num_cols < 2:
        logger.debug(f"Skipping layout table (rows={num_rows}, cols={num_cols})")
        return {"headers": [], "rows": []}

    grid = [[None for i in range(num_cols)] for j in range(num_rows)]
    occupied = {} # Basically identifies which cells are already occupied during the filling becoz of rowspan and colspan. Stores as (row_index , col_index)

    # Grid Filling
    for row_index, tr in enumerate(all_rows):
        col_index = 0

        cells = tr.find_all(['td' , 'th'], recursive=False)
        logger.debug(f"Row {row_index} has {len(cells)} cells")

        for cell in cells:

            # Skips over all the occupied cells. 
            while occupied.get((row_index , col_index)):
                col_index += 1

            # Safety check
            if col_index >= num_cols:
                break

            rowspan = int(cell.get('rowspan' , 1))
            colspan = int(cell.get('colspan' , 1))
            cell_content = cell.get_text(strip= True)

            # Uncomment for very detailed debugging:
            logger.debug(f"Cell '{cell_content}' at ({row_index},{col_index}) with rowspan={rowspan}, colspan={colspan}")

            for r in range(rowspan):
                for c in range(colspan):
                    target_row = row_index + r 
                    target_col = col_index + c

                    if target_row < num_rows and target_col < num_cols:
                        grid[target_row][target_col] = cell_content
                        occupied[(target_row , target_col)] = True
            
            col_index += colspan

            if col_index >= num_cols:
                break
        
    
    # Fancy printing the grid.
    fancy_print(grid)

    # Trying to get the headers for the table.
    headers = []
    rows = []

    thead_row_count = len(thead_rows)

    if thead_row_count > 0:
        # For now, use the LAST row of thead as headers 
        # May change the approach, like maybe flattening all the rows into single row or so.
       headers = grid[thead_row_count - 1]
       rows = grid[thead_row_count:]

       logger.debug(f"Extracted {len(headers)} headers from row {thead_row_count - 1}")
    else: # Fallback 
        # Checking if first row is all <th>
        if tbody_rows:
            first_row_cells = tbody_rows[0].find_all(['td', 'th'], recursive=False)
            if first_row_cells and all(c.name == 'th' for c in first_row_cells):
                headers = grid[0]
                rows = grid[1:]
            else:
                headers = []
                rows = grid
        else:
            headers = []
            rows = grid

    # Cleaning up: Removing None values and replacing them with empty string i.e., ('')
    headers = [h if h is not None else '' for h in headers]
    rows = [[cell if cell is not None else '' for cell in row] for row in rows]

    if headers:
        if len(headers) != num_cols:
            logger.warning(f"Header count ({len(headers)}) != column count ({num_cols})")
    
    for i, row in enumerate(rows):
        if len(row) != num_cols:
            logger.warning(f"Row {i} has {len(row)} cells, expected {num_cols}")


    return {"headers": headers, "rows": rows}

# Example testing
if __name__ == "__main__":
    # Configure logging level (optional)
    # set_log_level("DEBUG")    # Show all debug information
    # set_log_level("INFO")     # Show informational messages
    # set_log_level("WARNING")  # Show only warnings and errors (default)
    # set_log_level("ERROR")    # Show only errors
    
    # Test with a sample HTML file or URL
    # URL like "https://example.com"
    # source = "https://web.stanford.edu/class/archive/cs/cs224n/cs224n.1246/project.html" 
    source = "test_span.html" 
    
    try:
        results = parse_tables(source , extract_to_csv= False, use_grid= True)
        
        print(f"Found {len(results)} table(s)\n")
        
        for i, table in enumerate(results, 1):
            print(f"   Table {i}:")
            print(f"   Headers: {table['headers']}")
            print(f"   Number of rows: {len(table['rows'])}")
            
            if len(table['rows']) == 0:
                continue

            print(f"   Number of cols: {len(table['rows'][0])}")

            if len(table['rows'][0]) == 0:
                continue

            # Pretty print first few rows
            if table['rows']:
                print(f"\n   First 4 rows:")
                for j, row in enumerate(table['rows'][:4], 1):
                    print(f"   {j}. {row}")
            print("-" * 60)
            
    except Exception as e:
        print(f" Error: {e}")