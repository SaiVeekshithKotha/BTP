import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import json

# Configure logging
logger = logging.getLogger(__name__)

def set_log_level(level: str = "WARNING") -> None:
    """
    Set the logging level for the ARIA table extractor.
    
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

# Set default log level to WARNING
set_log_level("WARNING")

# ============================================================================
# Configuration and Data Classes
# ============================================================================

class ARIATableConfig:
    """Configuration parameters for ARIA table detection"""
    MIN_ROW_COUNT = 2              # Minimum rows for valid table (including headers)
    MIN_COLUMN_COUNT = 1           # Minimum columns for valid table
    MAX_COLUMN_VARIANCE = 0.3      # Maximum variance in column count across rows (30%)
    WAIT_TIME = 2                  # Seconds to wait for dynamic content
    PAGE_LOAD_TIMEOUT = 10         # Seconds to wait for page load

@dataclass
class BoundingBox:
    """Element position and size information"""
    x: float
    y: float
    width: float
    height: float

@dataclass
class ARIACell:
    """Represents a table cell with ARIA attributes"""
    content: str                           # Text content
    role: str                              # ARIA role (cell, gridcell, columnheader, rowheader)
    colspan: int = 1                       # Number of columns spanned
    rowspan: int = 1                       # Number of rows spanned
    colindex: Optional[int] = None         # Explicit column index (aria-colindex)
    rowindex: Optional[int] = None         # Explicit row index (aria-rowindex)
    aria_label: Optional[str] = None       # aria-label attribute
    bbox: Optional[BoundingBox] = None     # Bounding box for position
    
    def is_header(self) -> bool:
        """Check if this cell is a header"""
        return self.role in ['columnheader', 'rowheader']

@dataclass
class ARIARow:
    """Represents a table row with ARIA attributes"""
    cells: List[ARIACell]
    row_index: int
    is_header: bool = False
    rowgroup_type: Optional[str] = None    # 'thead', 'tbody', 'tfoot', or None
    
    def get_column_count(self) -> int:
        """Get effective column count including colspan"""
        return sum(cell.colspan for cell in self.cells)

@dataclass
class ARIATable:
    """Represents a complete ARIA table"""
    table_id: str
    aria_role: str                         # 'table' or 'grid'
    headers: Dict[str, List[str]]          # {'column_headers': [...], 'row_headers': [...]}
    rows: List[ARIARow]
    metadata: Dict[str, any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert table to dictionary format"""
        return {
            'table_id': self.table_id,
            'aria_role': self.aria_role,
            'headers': self.headers,
            'rows': [
                {
                    'row_index': row.row_index,
                    'is_header': row.is_header,
                    'rowgroup_type': row.rowgroup_type,
                    'cells': [
                        {
                            'content': cell.content,
                            'role': cell.role,
                            'colspan': cell.colspan,
                            'rowspan': cell.rowspan,
                            'colindex': cell.colindex
                        }
                        for cell in row.cells
                    ]
                }
                for row in self.rows
            ],
            'metadata': self.metadata
        }

# ============================================================================
# Phase 0: Page Loading & DOM Access
# ============================================================================

class PageLoader:
    """Handles page loading and DOM extraction with Selenium"""
    
    def __init__(self, config: ARIATableConfig = ARIATableConfig()):
        """
        Initialize the page loader.
        
        Args:
            config: Configuration parameters
        """
        self.config = config
        self.driver = None
    
    def load_page(self, source: str):
        """
        Load a page and return the Selenium driver for DOM access.
        
        Args:
            source: URL or local file path
        
        Returns:
            Selenium WebDriver instance
        """
        logger.info(f"Loading page: {source}")
        
        try:
            # Initialize browser
            self.driver = self._init_browser()
            
            # Load page
            if source.startswith(("http://", "https://")):
                self.driver.get(source)
            else:
                # Local file - convert to absolute path
                abs_path = os.path.abspath(source)
                self.driver.get(f"file://{abs_path}")
            
            # Wait for page to load
            WebDriverWait(self.driver, self.config.PAGE_LOAD_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(self.config.WAIT_TIME)
            
            logger.info("Page loaded successfully")
            
            return self.driver
            
        except Exception as e:
            logger.error(f"Failed to load page: {e}")
            if self.driver:
                self.driver.quit()
            raise
    
    def _init_browser(self) -> webdriver.Chrome:
        """Initialize Chrome WebDriver with automatic driver management"""
        chrome_options = Options()
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Use webdriver-manager to automatically download and manage ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def close(self):
        """Close the browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None

# ============================================================================
# Phase 1: ARIA Role Discovery
# ============================================================================

class ARIARoleDiscovery:
    """Scans DOM for elements with ARIA table roles"""
    
    def __init__(self):
        """Initialize ARIA role discovery"""
        pass
    
    def find_table_containers(self, driver) -> List:
        """
        Find all elements with ARIA table or grid roles.
        
        Args:
            driver: Selenium WebDriver instance
        
        Returns:
            List of WebElements with table/grid roles
        """
        logger.info("Searching for ARIA table containers")
        
        # Find all table and grid elements
        table_selector = '[role="table"], [role="grid"]'
        containers = driver.find_elements(By.CSS_SELECTOR, table_selector)
        
        logger.info(f"Found {len(containers)} ARIA table/grid containers")
        
        return containers
    
    def find_rows(self, container) -> List:
        """
        Find all row elements within a container.
        
        Args:
            container: WebElement with table/grid role
        
        Returns:
            List of WebElements with row role
        """
        rows = container.find_elements(By.CSS_SELECTOR, '[role="row"]')
        logger.debug(f"Found {len(rows)} rows in container")
        return rows
    
    def find_cells(self, row) -> List:
        """
        Find all cell elements within a row.
        
        Args:
            row: WebElement with row role
        
        Returns:
            List of WebElements with cell-related roles
        """
        # Find all types of cells
        cell_selector = '[role="cell"], [role="gridcell"], [role="columnheader"], [role="rowheader"]'
        cells = row.find_elements(By.CSS_SELECTOR, cell_selector)
        return cells
    
    def find_rowgroups(self, container) -> List:
        """
        Find all rowgroup elements within a container.
        
        Args:
            container: WebElement with table/grid role
        
        Returns:
            List of WebElements with rowgroup role
        """
        rowgroups = container.find_elements(By.CSS_SELECTOR, '[role="rowgroup"]')
        logger.debug(f"Found {len(rowgroups)} rowgroups in container")
        return rowgroups

# ============================================================================
# Phase 2: Table Container Identification
# ============================================================================

class TableContainerIdentifier:
    """Validates and identifies valid ARIA table containers"""
    
    def __init__(self, discovery: ARIARoleDiscovery):
        """
        Initialize table container identifier.
        
        Args:
            discovery: ARIARoleDiscovery instance
        """
        self.discovery = discovery
    
    def identify_valid_containers(self, driver) -> List[Tuple[any, str]]:
        """
        Identify valid ARIA table containers.
        
        Args:
            driver: Selenium WebDriver instance
        
        Returns:
            List of tuples (container_element, aria_role)
        """
        logger.info("Identifying valid table containers")
        
        containers = self.discovery.find_table_containers(driver)
        valid_containers = []
        
        for container in containers:
            if self._is_valid_container(container):
                aria_role = container.get_attribute('role')
                valid_containers.append((container, aria_role))
                logger.debug(f"Valid container found with role='{aria_role}'")
            else:
                logger.debug("Container rejected: validation failed")
        
        logger.info(f"Found {len(valid_containers)} valid table containers")
        return valid_containers
    
    def _is_valid_container(self, container) -> bool:
        """
        Validate that a container represents a proper table.
        
        Validation criteria:
        1. Must have at least one row
        2. Rows must contain cells
        
        Args:
            container: WebElement with table/grid role
        
        Returns:
            True if valid, False otherwise
        """
        # Check for rows
        rows = self.discovery.find_rows(container)
        if not rows:
            logger.debug("Container has no rows")
            return False
        
        # Check that at least one row has cells
        has_cells = False
        for row in rows:
            cells = self.discovery.find_cells(row)
            if cells:
                has_cells = True
                break
        
        if not has_cells:
            logger.debug("Container rows have no cells")
            return False
        
        return True

# ============================================================================
# Phase 3: Row Extraction
# ============================================================================

class RowExtractor:
    """Extracts rows from ARIA table containers"""
    
    def __init__(self, discovery: ARIARoleDiscovery):
        """
        Initialize row extractor.
        
        Args:
            discovery: ARIARoleDiscovery instance
        """
        self.discovery = discovery
    
    def extract_rows(self, container) -> List[Tuple[any, int, Optional[str]]]:
        """
        Extract all rows from a container in document order.
        
        Args:
            container: WebElement with table/grid role
        
        Returns:
            List of tuples (row_element, row_index, rowgroup_type)
        """
        logger.debug("Extracting rows from container")
        
        extracted_rows = []
        
        # Check for rowgroups
        rowgroups = self.discovery.find_rowgroups(container)
        
        if rowgroups:
            # Extract rows from rowgroups
            for rowgroup in rowgroups:
                rowgroup_type = self._infer_rowgroup_type(rowgroup)
                rows = self.discovery.find_rows(rowgroup)
                
                for row in rows:
                    row_index = len(extracted_rows)
                    extracted_rows.append((row, row_index, rowgroup_type))
        else:
            # Extract rows directly from container
            rows = self.discovery.find_rows(container)
            for row in rows:
                row_index = len(extracted_rows)
                extracted_rows.append((row, row_index, None))
        
        logger.debug(f"Extracted {len(extracted_rows)} rows")
        return extracted_rows
    
    def _infer_rowgroup_type(self, rowgroup) -> Optional[str]:
        """
        Infer the type of rowgroup (thead, tbody, tfoot).
        
        This is a heuristic since ARIA doesn't explicitly define rowgroup types.
        We check for common class names or position.
        
        Args:
            rowgroup: WebElement with rowgroup role
        
        Returns:
            'thead', 'tbody', 'tfoot', or None
        """
        # Check class names
        class_attr = rowgroup.get_attribute('class') or ''
        class_lower = class_attr.lower()
        
        if 'thead' in class_lower or 'header' in class_lower:
            return 'thead'
        elif 'tfoot' in class_lower or 'footer' in class_lower:
            return 'tfoot'
        elif 'tbody' in class_lower or 'body' in class_lower:
            return 'tbody'
        
        # Default to tbody if can't determine
        return 'tbody'

# ============================================================================
# Phase 4: Cell Extraction & Ordering
# ============================================================================

class CellExtractor:
    """Extracts and orders cells from rows"""
    
    def __init__(self, discovery: ARIARoleDiscovery, driver):
        """
        Initialize cell extractor.
        
        Args:
            discovery: ARIARoleDiscovery instance
            driver: Selenium WebDriver instance
        """
        self.discovery = discovery
        self.driver = driver
    
    def extract_cells(self, row_element) -> List[ARIACell]:
        """
        Extract all cells from a row and order them.
        
        Args:
            row_element: WebElement with row role
        
        Returns:
            List of ARIACell objects in column order
        """
        cell_elements = self.discovery.find_cells(row_element)
        
        cells = []
        for cell_elem in cell_elements:
            cell = self._create_aria_cell(cell_elem)
            cells.append(cell)
        
        # Sort cells by column index
        cells = self._sort_cells(cells)
        
        return cells
    
    def _create_aria_cell(self, cell_element) -> ARIACell:
        """
        Create an ARIACell from a WebElement.
        
        Args:
            cell_element: WebElement with cell-related role
        
        Returns:
            ARIACell object
        """
        # Get role
        role = cell_element.get_attribute('role') or 'cell'
        
        # Get text content
        content = cell_element.text.strip()
        
        # Get aria-label as fallback
        aria_label = cell_element.get_attribute('aria-label')
        if not content and aria_label:
            content = aria_label.strip()
        
        # Get spanning attributes
        colspan = self._parse_int_attr(cell_element, 'aria-colspan', 1)
        rowspan = self._parse_int_attr(cell_element, 'aria-rowspan', 1)
        
        # Get index attributes
        colindex = self._parse_int_attr(cell_element, 'aria-colindex', None)
        rowindex = self._parse_int_attr(cell_element, 'aria-rowindex', None)
        
        # Get bounding box
        bbox = self._get_bounding_box(cell_element)
        
        return ARIACell(
            content=content,
            role=role,
            colspan=colspan,
            rowspan=rowspan,
            colindex=colindex,
            rowindex=rowindex,
            aria_label=aria_label,
            bbox=bbox
        )
    
    def _parse_int_attr(self, element, attr_name: str, default) -> Optional[int]:
        """Parse an integer attribute from an element"""
        value = element.get_attribute(attr_name)
        if value:
            try:
                return int(value)
            except ValueError:
                logger.warning(f"Invalid {attr_name} value: {value}")
        return default
    
    def _get_bounding_box(self, element) -> BoundingBox:
        """Get element bounding box"""
        try:
            rect = self.driver.execute_script(
                "return arguments[0].getBoundingClientRect();",
                element
            )
            return BoundingBox(
                x=rect['x'],
                y=rect['y'],
                width=rect['width'],
                height=rect['height']
            )
        except:
            return BoundingBox(x=0, y=0, width=0, height=0)
    
    def _sort_cells(self, cells: List[ARIACell]) -> List[ARIACell]:
        """
        Sort cells by column position.
        
        Priority:
        1. aria-colindex (if present)
        2. x-coordinate from bounding box
        3. DOM order (original order)
        
        Args:
            cells: List of ARIACell objects
        
        Returns:
            Sorted list of ARIACell objects
        """
        # Create list with sort keys
        cells_with_keys = []
        for i, cell in enumerate(cells):
            # Determine sort key
            if cell.colindex is not None:
                sort_key = (0, cell.colindex)  # Priority 1: explicit colindex
            elif cell.bbox:
                sort_key = (1, cell.bbox.x)     # Priority 2: x-coordinate
            else:
                sort_key = (2, i)               # Priority 3: DOM order
            
            cells_with_keys.append((sort_key, cell))
        
        # Sort by key
        cells_with_keys.sort(key=lambda x: x[0])
        
        # Extract sorted cells
        return [cell for _, cell in cells_with_keys]

# ============================================================================
# Phase 5: Header Detection
# ============================================================================

class HeaderDetector:
    """Detects header cells in ARIA tables"""
    
    def __init__(self):
        """Initialize header detector"""
        pass
    
    def detect_headers(self, rows: List[ARIARow]) -> Dict[str, List[str]]:
        """
        Detect and extract headers from rows.
        
        Args:
            rows: List of ARIARow objects
        
        Returns:
            Dictionary with 'column_headers' and 'row_headers' lists
        """
        column_headers = []
        row_headers = []
        
        # Check first row for column headers
        if rows and rows[0].cells:
            first_row_cells = rows[0].cells
            if all(cell.is_header() for cell in first_row_cells):
                # First row is all headers
                column_headers = [cell.content for cell in first_row_cells]
                rows[0].is_header = True
        
        # Check each row for row headers
        for row in rows:
            for cell in row.cells:
                if cell.role == 'rowheader':
                    row_headers.append(cell.content)
        
        logger.debug(f"Detected {len(column_headers)} column headers, {len(row_headers)} row headers")
        
        return {
            'column_headers': column_headers,
            'row_headers': row_headers
        }
    
    def mark_header_rows(self, rows: List[ARIARow]) -> None:
        """
        Mark rows that contain only header cells.
        
        Args:
            rows: List of ARIARow objects (modified in place)
        """
        for row in rows:
            if row.cells and all(cell.is_header() for cell in row.cells):
                row.is_header = True

# ============================================================================
# Phase 6: Table Validation
# ============================================================================

class TableValidator:
    """Validates extracted ARIA tables"""
    
    def __init__(self, config: ARIATableConfig):
        """
        Initialize table validator.
        
        Args:
            config: Configuration parameters
        """
        self.config = config
    
    def validate_table(self, table: ARIATable) -> bool:
        """
        Validate that an extracted table meets quality criteria.
        
        Validation criteria:
        1. Minimum row count
        2. Minimum column count
        3. Consistent column counts across rows
        4. Contains meaningful content
        
        Args:
            table: ARIATable object
        
        Returns:
            True if valid, False otherwise
        """
        # Check minimum row count
        if len(table.rows) < self.config.MIN_ROW_COUNT:
            logger.debug(f"Table rejected: too few rows ({len(table.rows)})")
            return False
        
        # Check minimum column count
        if table.rows:
            max_cols = max(row.get_column_count() for row in table.rows)
            if max_cols < self.config.MIN_COLUMN_COUNT:
                logger.debug(f"Table rejected: too few columns ({max_cols})")
                return False
        
        # Check column count consistency
        if not self._has_consistent_columns(table.rows):
            logger.debug("Table rejected: inconsistent column counts")
            return False
        
        # Check for content
        if not self._has_content(table.rows):
            logger.debug("Table rejected: no text content")
            return False
        
        logger.debug("Table validated successfully")
        return True
    
    def _has_consistent_columns(self, rows: List[ARIARow]) -> bool:
        """Check if rows have consistent column counts"""
        if not rows:
            return True
        
        col_counts = [row.get_column_count() for row in rows]
        
        # Calculate variance
        mean_cols = sum(col_counts) / len(col_counts)
        if mean_cols == 0:
            return False
        
        variance = sum((c - mean_cols) ** 2 for c in col_counts) / len(col_counts)
        normalized_variance = variance / (mean_cols ** 2)
        
        return normalized_variance <= self.config.MAX_COLUMN_VARIANCE
    
    def _has_content(self, rows: List[ARIARow]) -> bool:
        """Check if table has meaningful text content"""
        total_content = 0
        
        for row in rows:
            for cell in row.cells:
                if cell.content:
                    total_content += len(cell.content)
        
        return total_content > 0

# ============================================================================
# Main Orchestrator
# ============================================================================

class ARIATableExtractor:
    """Main class for extracting tables from ARIA-enabled webpages"""
    
    def __init__(self, config: ARIATableConfig = ARIATableConfig()):
        """
        Initialize ARIA table extractor.
        
        Args:
            config: Configuration parameters
        """
        self.config = config
        self.page_loader = PageLoader(config)
        self.discovery = ARIARoleDiscovery()
        self.container_identifier = TableContainerIdentifier(self.discovery)
        self.row_extractor = RowExtractor(self.discovery)
        self.header_detector = HeaderDetector()
        self.validator = TableValidator(config)
    
    def extract_tables(self, source: str) -> List[ARIATable]:
        """
        Extract all ARIA tables from a webpage.
        
        Args:
            source: URL or local file path
        
        Returns:
            List of validated ARIATable objects
        """
        logger.info(f"Starting ARIA table extraction from: {source}")
        
        try:
            # Phase 0: Load page
            driver = self.page_loader.load_page(source)
            
            # Phase 1 & 2: Discover and identify valid containers
            valid_containers = self.container_identifier.identify_valid_containers(driver)
            
            if not valid_containers:
                logger.info("No valid ARIA table containers found")
                return []
            
            # Extract tables from each container
            tables = []
            for i, (container, aria_role) in enumerate(valid_containers):
                table = self._extract_single_table(container, aria_role, i, driver)
                if table and self.validator.validate_table(table):
                    tables.append(table)
                    logger.info(f"Extracted valid table {i+1}: {len(table.rows)} rows")
                else:
                    logger.debug(f"Table {i+1} rejected during validation")
            
            logger.info(f"Successfully extracted {len(tables)} tables")
            return tables
            
        finally:
            self.page_loader.close()
    
    def _extract_single_table(self, container, aria_role: str, table_index: int, driver) -> Optional[ARIATable]:
        """
        Extract a single table from a container.
        
        Args:
            container: WebElement with table/grid role
            aria_role: The ARIA role ('table' or 'grid')
            table_index: Index of this table
            driver: Selenium WebDriver instance
        
        Returns:
            ARIATable object or None if extraction fails
        """
        try:
            # Phase 3: Extract rows
            row_data = self.row_extractor.extract_rows(container)
            
            if not row_data:
                logger.debug("No rows found in container")
                return None
            
            # Phase 4: Extract cells
            cell_extractor = CellExtractor(self.discovery, driver)
            rows = []
            
            for row_element, row_index, rowgroup_type in row_data:
                cells = cell_extractor.extract_cells(row_element)
                
                if cells:  # Only add rows with cells
                    aria_row = ARIARow(
                        cells=cells,
                        row_index=row_index,
                        rowgroup_type=rowgroup_type
                    )
                    rows.append(aria_row)
            
            if not rows:
                logger.debug("No valid rows with cells found")
                return None
            
            # Phase 5: Detect headers
            self.header_detector.mark_header_rows(rows)
            headers = self.header_detector.detect_headers(rows)
            
            # Create table object
            table = ARIATable(
                table_id=f"table_{table_index}",
                aria_role=aria_role,
                headers=headers,
                rows=rows,
                metadata={
                    'total_rows': len(rows),
                    'total_columns': max(row.get_column_count() for row in rows) if rows else 0,
                    'has_rowgroups': any(row.rowgroup_type is not None for row in rows)
                }
            )
            
            return table
            
        except Exception as e:
            logger.error(f"Error extracting table {table_index}: {e}")
            return None

# ============================================================================
# Utility Functions
# ============================================================================

def extract_tables_to_json(source: str, output_file: Optional[str] = None) -> str:
    """
    Extract ARIA tables and convert to JSON format.
    
    Args:
        source: URL or local file path
        output_file: Optional output file path for JSON
    
    Returns:
        JSON string representation of extracted tables
    """
    extractor = ARIATableExtractor()
    tables = extractor.extract_tables(source)
    
    # Convert to dict format
    tables_dict = [table.to_dict() for table in tables]
    
    # Convert to JSON
    json_output = json.dumps(tables_dict, indent=2)
    
    # Save to file if specified
    if output_file:
        with open(output_file, 'w') as f:
            f.write(json_output)
        logger.info(f"Saved tables to {output_file}")
    
    return json_output

# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Example: Extract tables from a local HTML file
    set_log_level("INFO")
    
    extractor = ARIATableExtractor()
    tables = extractor.extract_tables("test_aria.html")
    
    print(f"\nFound {len(tables)} tables\n")
    
    for i, table in enumerate(tables):
        print(f"Table {i+1} ({table.aria_role}):")
        print(f"  Rows: {len(table.rows)}")
        print(f"  Columns: {table.metadata.get('total_columns', 0)}")
        print(f"  Column Headers: {table.headers.get('column_headers', [])}")
        print()
