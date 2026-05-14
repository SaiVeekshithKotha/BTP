import logging
from typing import List, Dict, TypedDict, Optional, Tuple
from dataclasses import dataclass, field
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
import os

# Configure logging
logger = logging.getLogger(__name__)

def set_log_level(level: str = "WARNING") -> None:
    """
    Set the logging level for the VIPS extractor.
    
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

# Type Declarations
class BoundingBox(TypedDict):
    x: float
    y: float
    width: float
    height: float

class RenderedElement(TypedDict):
    tag: str
    text: str
    classes: List[str]
    styles: Dict[str, str]
    bbox: BoundingBox
    children: List['RenderedElement']

# VIPS Configuration Parameters
class VIPSConfig:
    """Configuration parameters for VIPS algorithm"""
    MAX_DEPTH = 5              # Maximum recursion depth
    MIN_BLOCK_WIDTH = 100      # Minimum block width in pixels
    MIN_BLOCK_HEIGHT = 15      # Minimum block height in pixels
    MIN_DOC = 0.95             # Minimum Degree of Coherence to stop partition
    MIN_CHILDREN = 3          # Minimum children count for table candidate
    WHITESPACE_THRESHOLD = 20  # Minimum gap size to be considered whitespace (pixels)
    
@dataclass
class VisualBlock:
    """Represents a visual block in the VIPS tree"""
    bbox: BoundingBox
    elements: List[RenderedElement]
    children: List['VisualBlock'] = field(default_factory=list)
    doc: float = 0.0  # Degree of Coherence
    depth: int = 0
    parent: Optional['VisualBlock'] = None
    
    def add_child(self, child: 'VisualBlock') -> None:
        """Add a child block"""
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)
    
    def is_leaf(self) -> bool:
        """Check if this is a leaf block"""
        return len(self.children) == 0
    
    def get_area(self) -> float:
        """Calculate block area"""
        return self.bbox['width'] * self.bbox['height']

# ============================================================================
# Phase 0: Page Rendering
# ============================================================================

class PageRenderer:
    """Handles page rendering and DOM extraction with Selenium"""
    
    def __init__(self):
        """Initialize the page renderer."""
        self.driver = None
    
    def render_page(self, source: str) -> RenderedElement:
        """
        Render a page and extract DOM with layout information.
        
        Args:
            source: URL or local file path
        
        Returns:
            Root RenderedElement with full tree structure
        """
        logger.info(f"Rendering page: {source}")
        
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
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(2)
            
            logger.info("Page loaded successfully")
            
            # Extract DOM tree
            body = self.driver.find_element(By.TAG_NAME, "body")
            rendered_tree = self._extract_element_data(body)
            
            return rendered_tree
            
        finally:
            if self.driver:
                self.driver.quit()
    
    def _init_browser(self) -> webdriver.Chrome:
        """Initialize Chrome WebDriver with automatic driver management"""
        chrome_options = Options()
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Use webdriver-manager to automatically download and manage the correct ChromeDriver version
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    
    def _extract_element_data(self, element) -> RenderedElement:
        """
        Extract data from a WebElement recursively.
        
        Args:
            element: Selenium WebElement
        
        Returns:
            RenderedElement with all metadata
        """
        # Get basic properties
        tag = element.tag_name.lower()
        text = element.text.strip() if element.text else ""
        classes = element.get_attribute("class").split() if element.get_attribute("class") else []
        
        # Get bounding box
        bbox = self._get_bounding_box(element)
        
        # Get computed styles
        styles = self._get_computed_styles(element)
        
        # Skip non-visual elements
        if tag in ['script', 'style', 'meta', 'link', 'noscript']:
            return None
        
        # Skip hidden elements
        if styles.get('display') == 'none' or styles.get('visibility') == 'hidden':
            return None
        
        # Skip elements with zero size
        if bbox['width'] == 0 or bbox['height'] == 0:
            return None
        
        # Extract children
        children = []
        try:
            child_elements = element.find_elements(By.XPATH, "./*")
            for child in child_elements:
                child_data = self._extract_element_data(child)
                if child_data:
                    children.append(child_data)
        except:
            pass
        
        return RenderedElement(
            tag=tag,
            text=text,
            classes=classes,
            styles=styles,
            bbox=bbox,
            children=children
        )
    
    def _get_bounding_box(self, element) -> BoundingBox:
        """
        Get element bounding box using getBoundingClientRect.
        
        Args:
            element: Selenium WebElement
        
        Returns:
            BoundingBox with position and size
        """
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
    
    def _get_computed_styles(self, element) -> Dict[str, str]:
        """
        Get computed CSS styles for an element.
        
        Args:
            element: Selenium WebElement
        
        Returns:
            Dictionary of CSS properties
        """
        # Key CSS properties for VIPS
        properties = [
            'display', 'position', 'float',
            'background-color', 'border-top-width', 'border-right-width',
            'border-bottom-width', 'border-left-width', 'border-style',
            'font-size', 'font-weight', 'font-family',
            'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
            'padding-top', 'padding-right', 'padding-bottom', 'padding-left'
        ]
        
        styles = {}
        for prop in properties:
            value = self.driver.execute_script(
                f"return window.getComputedStyle(arguments[0]).getPropertyValue('{prop}');",
                element
            )
            styles[prop] = value
        
        return styles

# ============================================================================
# Phase 1: VIPS - Visual Page Segmentation
# ============================================================================

class VIPSSegmenter:
    """Implements VIPS (Vision-based Page Segmentation) algorithm"""
    
    def __init__(self, config: VIPSConfig = VIPSConfig()):
        """
        Initialize VIPS segmenter.
        
        Args:
            config: VIPS configuration parameters
        """
        self.config = config
    
    def segment(self, rendered_root: RenderedElement) -> VisualBlock:
        """
        Segment a rendered page into visual blocks.
        
        Args:
            rendered_root: Root RenderedElement from PageRenderer
        
        Returns:
            Root VisualBlock with hierarchical structure
        """
        logger.info("Starting VIPS segmentation")
        
        # Create root block
        root_block = VisualBlock(
            bbox=rendered_root['bbox'],
            elements=[rendered_root],
            depth=0
        )
        
        # Recursively partition
        self._partition_block(root_block, rendered_root)
        
        logger.info(f"VIPS segmentation complete. Total blocks: {self._count_blocks(root_block)}")
        
        return root_block
    
    def _partition_block(self, block: VisualBlock, element: RenderedElement) -> None:
        """
        Recursively partition a block based on visual separators.
        
        Args:
            block: Current VisualBlock to partition
            element: Corresponding RenderedElement
        """
        # Check stopping criteria
        if self._should_stop_partition(block, element):
            logger.debug(f"Stopping partition at depth {block.depth}: {self._get_stop_reason(block, element)}")
            return
        
        # Try different partition strategies
        separators = []
        
        # 1. Whitespace-based separation
        whitespace_seps = self._detect_whitespace_separators(element)
        separators.extend(whitespace_seps)
        logger.debug(f"Depth {block.depth}: Found {len(whitespace_seps)} whitespace separators")
        
        # 2. Border-based separation
        border_seps = self._detect_border_separators(element)
        separators.extend(border_seps)
        logger.debug(f"Depth {block.depth}: Found {len(border_seps)} border separators")
        
        # 3. Background-based separation
        bg_seps = self._detect_background_separators(element)
        separators.extend(bg_seps)
        logger.debug(f"Depth {block.depth}: Found {len(bg_seps)} background separators")
        
        # 4. Font-based separation
        font_seps = self._detect_font_separators(element)
        separators.extend(font_seps)
        logger.debug(f"Depth {block.depth}: Found {len(font_seps)} font separators")
        
        logger.debug(f"Depth {block.depth}: Element tag='{element['tag']}', "
                    f"children={len(element['children'])}, total_separators={len(separators)}")
        
        # Special case: if we have only one child, partition that child directly
        if len(element['children']) == 1:
            logger.debug(f"Single child at depth {block.depth}, partitioning child directly")
            child_element = element['children'][0]
            # Create a block for the single child
            child_block = VisualBlock(
                bbox=child_element['bbox'],
                elements=[child_element],
                depth=block.depth + 1
            )
            block.add_child(child_block)
            self._partition_block(child_block, child_element)
            return
        
        if not separators:
            logger.debug(f"No separators found at depth {block.depth}")
            return
        
        # Partition by separators
        sub_blocks = self._create_sub_blocks(block, element, separators)
        
        if len(sub_blocks) < 2:  # Need at least 2 children to partition
            logger.debug(f"Too few children ({len(sub_blocks)}) at depth {block.depth}")
            return
        
        # Add children and recurse
        for sub_block, sub_element in sub_blocks:
            block.add_child(sub_block)
            self._partition_block(sub_block, sub_element)
    
    def _should_stop_partition(self, block: VisualBlock, element: RenderedElement) -> bool:
        """
        Determine if we should stop partitioning this block.
        
        Stopping criteria (any of these):
        1. High Degree of Coherence (DoC > threshold)
        2. Block too small (width or height below minimum)
        3. Maximum depth reached
        4. No children elements
        
        Args:
            block: Current VisualBlock
            element: Corresponding RenderedElement
        
        Returns:
            True if should stop, False otherwise
        """
        # Calculate DoC
        doc = self._calculate_doc(element)
        block.doc = doc
        
        # Check criteria
        if doc > self.config.MIN_DOC:
            return True
        
        if block.bbox['width'] < self.config.MIN_BLOCK_WIDTH:
            return True
        
        if block.bbox['height'] < self.config.MIN_BLOCK_HEIGHT:
            return True
        
        if block.depth >= self.config.MAX_DEPTH:
            return True
        
        if not element['children']:
            return True
        
        return False
    
    def _get_stop_reason(self, block: VisualBlock, element: RenderedElement) -> str:
        """Get human-readable reason for stopping partition"""
        if block.doc > self.config.MIN_DOC:
            return f"High DoC ({block.doc:.2f})"
        if block.bbox['width'] < self.config.MIN_BLOCK_WIDTH:
            return f"Width too small ({block.bbox['width']:.0f}px)"
        if block.bbox['height'] < self.config.MIN_BLOCK_HEIGHT:
            return f"Height too small ({block.bbox['height']:.0f}px)"
        if block.depth >= self.config.MAX_DEPTH:
            return f"Max depth reached ({block.depth})"
        if not element['children']:
            return "No children"
        return "Unknown"
    
    def _calculate_doc(self, element: RenderedElement) -> float:
        """
        Calculate Degree of Coherence for an element.
        
        DoC measures visual cohesion based on:
        - Background color consistency
        - Font consistency
        - Border presence
        - Spacing uniformity
        
        Args:
            element: RenderedElement to analyze
        
        Returns:
            DoC value between 0.0 and 1.0
        """
        if not element['children']:
            return 1.0  # Leaf elements are maximally coherent
        
        scores = []
        
        # 1. Background consistency (30% weight)
        bg_score = self._calculate_background_consistency(element)
        scores.append(bg_score * 0.3)
        
        # 2. Font consistency (30% weight)
        font_score = self._calculate_font_consistency(element)
        scores.append(font_score * 0.3)
        
        # 3. Border presence (20% weight)
        border_score = self._calculate_border_score(element)
        scores.append(border_score * 0.2)
        
        # 4. Spacing uniformity (20% weight)
        spacing_score = self._calculate_spacing_uniformity(element)
        scores.append(spacing_score * 0.2)
        
        total_doc = sum(scores)
        
        logger.debug(f"DoC calculation: bg={bg_score:.2f}, font={font_score:.2f}, "
                    f"border={border_score:.2f}, spacing={spacing_score:.2f}, "
                    f"total={total_doc:.2f}, children={len(element['children'])}")
        
        return total_doc
    
    def _calculate_background_consistency(self, element: RenderedElement) -> float:
        """Calculate background color consistency among children"""
        if not element['children']:
            return 1.0
        
        bg_colors = [child['styles'].get('background-color', 'transparent') 
                     for child in element['children']]
        
        # Count most common background
        from collections import Counter
        color_counts = Counter(bg_colors)
        most_common_count = color_counts.most_common(1)[0][1]
        
        return most_common_count / len(bg_colors)
    
    def _calculate_font_consistency(self, element: RenderedElement) -> float:
        """Calculate font consistency among children"""
        if not element['children']:
            return 1.0
        
        font_sizes = [child['styles'].get('font-size', '16px') 
                      for child in element['children']]
        
        from collections import Counter
        size_counts = Counter(font_sizes)
        most_common_count = size_counts.most_common(1)[0][1]
        
        return most_common_count / len(font_sizes)
    
    def _calculate_border_score(self, element: RenderedElement) -> float:
        """Calculate border presence score"""
        styles = element['styles']
        
        # Check if element has visible borders
        border_widths = [
            float(styles.get('border-top-width', '0px').replace('px', '')),
            float(styles.get('border-right-width', '0px').replace('px', '')),
            float(styles.get('border-bottom-width', '0px').replace('px', '')),
            float(styles.get('border-left-width', '0px').replace('px', ''))
        ]
        
        # If has borders, higher coherence (likely a contained unit)
        return 1.0 if any(w > 0 for w in border_widths) else 0.5
    
    def _calculate_spacing_uniformity(self, element: RenderedElement) -> float:
        """Calculate spacing uniformity among children"""
        if len(element['children']) < 2:
            return 1.0
        
        # Calculate gaps between consecutive children
        children = sorted(element['children'], key=lambda e: e['bbox']['y'])
        gaps = []
        
        for i in range(len(children) - 1):
            gap = children[i+1]['bbox']['y'] - (children[i]['bbox']['y'] + children[i]['bbox']['height'])
            gaps.append(gap)
        
        if not gaps:
            return 1.0
        
        # Calculate variance
        mean_gap = sum(gaps) / len(gaps)
        variance = sum((g - mean_gap) ** 2 for g in gaps) / len(gaps)
        
        # Lower variance = higher uniformity
        # Normalize: variance of 0 = score 1.0, variance > 100 = score 0.0
        return max(0.0, 1.0 - (variance / 100))
    
    def _detect_whitespace_separators(self, element: RenderedElement) -> List[Tuple[str, float]]:
        """
        Detect whitespace-based separators (vertical gaps).
        
        Returns:
            List of (type, position) tuples
        """
        if not element['children']:
            return []
        
        separators = []
        children = sorted(element['children'], key=lambda e: e['bbox']['y'])
        
        for i in range(len(children) - 1):
            current_bottom = children[i]['bbox']['y'] + children[i]['bbox']['height']
            next_top = children[i+1]['bbox']['y']
            gap = next_top - current_bottom
            
            if gap >= self.config.WHITESPACE_THRESHOLD:
                separators.append(('whitespace', current_bottom + gap / 2))
        
        return separators
    
    def _detect_border_separators(self, element: RenderedElement) -> List[Tuple[str, float]]:
        """Detect border-based separators"""
        separators = []
        
        for child in element['children']:
            styles = child['styles']
            border_top = float(styles.get('border-top-width', '0px').replace('px', ''))
            border_bottom = float(styles.get('border-bottom-width', '0px').replace('px', ''))
            
            if border_top > 0:
                separators.append(('border', child['bbox']['y']))
            if border_bottom > 0:
                separators.append(('border', child['bbox']['y'] + child['bbox']['height']))
        
        return separators
    
    def _detect_background_separators(self, element: RenderedElement) -> List[Tuple[str, float]]:
        """Detect background color change separators"""
        if not element['children']:
            return []
        
        separators = []
        children = sorted(element['children'], key=lambda e: e['bbox']['y'])
        
        for i in range(len(children) - 1):
            current_bg = children[i]['styles'].get('background-color', 'transparent')
            next_bg = children[i+1]['styles'].get('background-color', 'transparent')
            
            if current_bg != next_bg:
                sep_y = children[i]['bbox']['y'] + children[i]['bbox']['height']
                separators.append(('background', sep_y))
        
        return separators
    
    def _detect_font_separators(self, element: RenderedElement) -> List[Tuple[str, float]]:
        """Detect font size change separators"""
        if not element['children']:
            return []
        
        separators = []
        children = sorted(element['children'], key=lambda e: e['bbox']['y'])
        
        for i in range(len(children) - 1):
            current_font = children[i]['styles'].get('font-size', '16px')
            next_font = children[i+1]['styles'].get('font-size', '16px')
            
            if current_font != next_font:
                sep_y = children[i]['bbox']['y'] + children[i]['bbox']['height']
                separators.append(('font', sep_y))
        
        return separators
    
    def _create_sub_blocks(self, parent_block: VisualBlock, element: RenderedElement, 
                          separators: List[Tuple[str, float]]) -> List[Tuple[VisualBlock, RenderedElement]]:
        """
        Create sub-blocks by partitioning based on separators.
        
        Args:
            parent_block: Parent VisualBlock
            element: Parent RenderedElement
            separators: List of (type, position) separators
        
        Returns:
            List of (VisualBlock, RenderedElement) tuples
        """
        # Sort separators by position
        separators = sorted(separators, key=lambda s: s[1])
        
        # Group children by separator regions
        children = sorted(element['children'], key=lambda e: e['bbox']['y'])
        
        if not children:
            return []
        
        # Simple approach: group children between separators
        sub_blocks = []
        current_group = []
        sep_index = 0
        
        for child in children:
            child_y = child['bbox']['y']
            
            # Check if we've crossed a separator
            crossed = False
            while sep_index < len(separators) and child_y >= separators[sep_index][1]:
                crossed = True
                sep_index += 1
                
            if crossed and current_group:
                # Create block from current group
                sub_block = self._create_block_from_elements(current_group, parent_block)
                sub_blocks.append(sub_block)
                current_group = []
            
            current_group.append(child)
        
        # Add remaining group
        if current_group:
            sub_block = self._create_block_from_elements(current_group, parent_block)
            sub_blocks.append(sub_block)
        
        return sub_blocks
    
    def _create_block_from_elements(self, elements: List[RenderedElement], 
                                   parent: VisualBlock) -> Tuple[VisualBlock, RenderedElement]:
        """Create a VisualBlock from a group of elements"""
        if not elements:
            return None
        
        # Calculate bounding box that encompasses all elements
        min_x = min(e['bbox']['x'] for e in elements)
        min_y = min(e['bbox']['y'] for e in elements)
        max_x = max(e['bbox']['x'] + e['bbox']['width'] for e in elements)
        max_y = max(e['bbox']['y'] + e['bbox']['height'] for e in elements)
        
        bbox = BoundingBox(
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y
        )
        
        # Create a synthetic element representing this group
        group_element = RenderedElement(
            tag='div',
            text='',
            classes=[],
            styles={},
            bbox=bbox,
            children=elements
        )
        
        block = VisualBlock(
            bbox=bbox,
            elements=elements,
            depth=parent.depth + 1
        )
        
        return (block, group_element)
    
    def _count_blocks(self, block: VisualBlock) -> int:
        """Count total number of blocks in tree"""
        count = 1
        for child in block.children:
            count += self._count_blocks(child)
        return count

# ============================================================================
# Phase 2: Candidate Block Selection
# ============================================================================

class CandidateSelector:
    """Selects blocks that are likely to contain tables"""
    
    def __init__(self):
        """Initialize candidate selector with default thresholds"""
        self.min_children = 2          # Minimum number of child blocks
        self.min_text_density = 0.0001   # Minimum text density (chars per pixel)
        self.alignment_threshold = 30   # Max horizontal offset for vertical alignment (pixels)
        self.size_similarity_threshold = 0.4  # Minimum similarity ratio for child sizes
    
    def select_candidates(self, root_block: VisualBlock) -> List[VisualBlock]:
        """
        Select candidate blocks that may contain tables.
        
        Args:
            root_block: Root VisualBlock from VIPS
        
        Returns:
            List of candidate VisualBlocks
        """
        logger.info("Starting candidate block selection")
        
        candidates = []
        self._collect_candidates(root_block, candidates)
        
        logger.info(f"Found {len(candidates)} candidate blocks")
        return candidates
    
    def _collect_candidates(self, block: VisualBlock, candidates: List[VisualBlock]) -> None:
        """
        Recursively collect candidate blocks.
        
        Args:
            block: Current block to evaluate
            candidates: List to accumulate candidates
        """
        logger.debug(f"Evaluating block at depth {block.depth}: {len(block.children)} children, "
                    f"bbox=({block.bbox['width']:.0f}x{block.bbox['height']:.0f})")
        
        # Check if this block is a candidate
        if self._is_candidate(block):
            candidates.append(block)
            logger.debug(f"Candidate found at depth {block.depth}: {len(block.children)} children")
        
        # Recurse into children
        for child in block.children:
            self._collect_candidates(child, candidates)
    
    def _is_candidate(self, block: VisualBlock) -> bool:
        """
        Determine if a block is a table candidate.
        
        Heuristics:
        1. Has many child blocks (≥ min_children)
        2. Children are vertically aligned
        3. Children have similar sizes
        4. High text density
        
        Args:
            block: VisualBlock to evaluate
        
        Returns:
            True if block is a candidate
        """
        # Must have children
        if not block.children:
            return False
        
        # Heuristic 1: Minimum children count
        if len(block.children) < self.min_children:
            logger.debug(f"Block rejected: too few children ({len(block.children)})")
            return False
        
        # Heuristic 2: Vertical alignment
        if not self._are_children_vertically_aligned(block):
            logger.debug("Block rejected: children not vertically aligned")
            return False
        
        # Heuristic 3: Size similarity
        if not self._have_similar_sizes(block):
            logger.debug("Block rejected: children have dissimilar sizes")
            return False
        
        # Heuristic 4: Text density
        if not self._has_sufficient_text_density(block):
            logger.debug("Block rejected: insufficient text density")
            return False
        
        return True
    
    def _are_children_vertically_aligned(self, block: VisualBlock) -> bool:
        """
        Check if children are vertically aligned (similar x-positions).
        
        Args:
            block: Parent VisualBlock
        
        Returns:
            True if children are vertically aligned
        """
        if len(block.children) < 2:
            return True
        
        # Get x-positions of all children
        x_positions = [child.bbox['x'] for child in block.children]
        
        # Calculate variance in x-positions
        mean_x = sum(x_positions) / len(x_positions)
        variance = sum((x - mean_x) ** 2 for x in x_positions) / len(x_positions)
        std_dev = variance ** 0.5
        
        # Children are aligned if standard deviation is small
        return std_dev < self.alignment_threshold
    
    def _have_similar_sizes(self, block: VisualBlock) -> bool:
        """
        Check if children have similar sizes (heights).
        
        Args:
            block: Parent VisualBlock
        
        Returns:
            True if children have similar sizes
        """
        if len(block.children) < 2:
            return True
        
        # Get heights of all children
        heights = [child.bbox['height'] for child in block.children]
        
        # Calculate size similarity
        min_height = min(heights)
        max_height = max(heights)
        
        if max_height == 0:
            return False
        
        # Similarity ratio: min/max should be above threshold
        similarity = min_height / max_height
        
        logger.debug(f"Size similarity check: min_height={min_height:.1f}, max_height={max_height:.1f}, "
                    f"similarity={similarity:.2f}, threshold={self.size_similarity_threshold}")
        
        return similarity >= self.size_similarity_threshold
    
    def _has_sufficient_text_density(self, block: VisualBlock) -> bool:
        """
        Check if block has sufficient text content.
        
        Args:
            block: VisualBlock to evaluate
        
        Returns:
            True if text density is sufficient
        """
        # Calculate total text length
        total_text_length = self._calculate_text_length(block)
        
        # Calculate block area
        area = block.get_area()
        
        if area == 0:
            return False
        
        # Text density = characters per pixel
        density = total_text_length / area
        
        return density >= self.min_text_density
    
    def _calculate_text_length(self, block: VisualBlock) -> int:
        """
        Calculate total text length in a block.
        
        Args:
            block: VisualBlock
        
        Returns:
            Total character count
        """
        total = 0
        
        for element in block.elements:
            total += len(element.get('text', ''))
            # Recursively count children
            total += self._count_text_in_children(element)
        
        return total
    
    def _count_text_in_children(self, element: RenderedElement) -> int:
        """Recursively count text in element children"""
        total = 0
        for child in element.get('children', []):
            total += len(child.get('text', ''))
            total += self._count_text_in_children(child)
        return total

# ============================================================================
# Phase 3: MDR - Mining Data Records
# ============================================================================

class MDRPatternDetector:
    """Detects repeated patterns (data records) in candidate blocks"""
    
    def __init__(self):
        """Initialize MDR pattern detector with default thresholds"""
        self.similarity_threshold = 0.8  # Minimum similarity for pattern matching
        self.min_pattern_count = 3       # Minimum occurrences to be considered a pattern
    
    def detect_patterns(self, candidates: List[VisualBlock]) -> List[Dict]:
        """
        Detect repeated patterns in candidate blocks.
        
        Args:
            candidates: List of candidate VisualBlocks
        
        Returns:
            List of detected patterns with their occurrences
        """
        logger.info(f"Starting MDR pattern detection on {len(candidates)} candidates")
        
        all_patterns = []
        
        for candidate in candidates:
            patterns = self._find_patterns_in_block(candidate)
            if patterns:
                all_patterns.extend(patterns)
        
        logger.info(f"Found {len(all_patterns)} patterns total")
        return all_patterns
    
    def _find_patterns_in_block(self, block: VisualBlock) -> List[Dict]:
        """
        Find repeated patterns within a single block.
        
        Args:
            block: VisualBlock to analyze
        
        Returns:
            List of pattern dictionaries
        """
        if not block.children or len(block.children) < self.min_pattern_count:
            return []
        
        # Compare all pairs of children to find similar structures
        similarity_matrix = self._build_similarity_matrix(block.children)
        
        # Group similar children into patterns
        patterns = self._group_patterns(block.children, similarity_matrix)
        
        # Filter patterns by minimum count
        valid_patterns = [p for p in patterns if len(p['instances']) >= self.min_pattern_count]
        
        if valid_patterns:
            logger.debug(f"Block at depth {block.depth}: found {len(valid_patterns)} valid patterns")
        
        return valid_patterns
    
    def _build_similarity_matrix(self, children: List[VisualBlock]) -> List[List[float]]:
        """
        Build a similarity matrix comparing all pairs of children.
        
        Args:
            children: List of VisualBlocks to compare
        
        Returns:
            2D matrix where matrix[i][j] = similarity(children[i], children[j])
        """
        n = len(children)
        matrix = [[0.0 for _ in range(n)] for _ in range(n)]
        
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    matrix[i][j] = 1.0
                else:
                    similarity = self._calculate_similarity(children[i], children[j])
                    matrix[i][j] = similarity
                    matrix[j][i] = similarity
        
        return matrix
    
    def _calculate_similarity(self, block1: VisualBlock, block2: VisualBlock) -> float:
        """
        Calculate structural similarity between two blocks.
        
        Similarity is based on:
        1. DOM structure similarity (tag sequence)
        2. Number of children
        3. Size similarity
        
        Args:
            block1, block2: VisualBlocks to compare
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        scores = []
        
        # 1. DOM structure similarity (40% weight)
        structure_score = self._compare_dom_structure(block1, block2)
        scores.append(structure_score * 0.4)
        
        # 2. Child count similarity (30% weight)
        child_count_score = self._compare_child_counts(block1, block2)
        scores.append(child_count_score * 0.3)
        
        # 3. Size similarity (30% weight)
        size_score = self._compare_sizes(block1, block2)
        scores.append(size_score * 0.3)
        
        return sum(scores)
    
    def _compare_dom_structure(self, block1: VisualBlock, block2: VisualBlock) -> float:
        """
        Compare DOM structure by comparing tag sequences.
        
        Args:
            block1, block2: VisualBlocks to compare
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Extract tag sequences from elements
        tags1 = self._extract_tag_sequence(block1.elements)
        tags2 = self._extract_tag_sequence(block2.elements)
        
        if not tags1 or not tags2:
            return 0.0
        
        # Calculate edit distance (Levenshtein distance)
        distance = self._levenshtein_distance(tags1, tags2)
        max_len = max(len(tags1), len(tags2))
        
        if max_len == 0:
            return 1.0
        
        # Convert distance to similarity
        similarity = 1.0 - (distance / max_len)
        return max(0.0, similarity)
    
    def _extract_tag_sequence(self, elements: List[RenderedElement]) -> List[str]:
        """
        Extract sequence of HTML tags from elements.
        
        Args:
            elements: List of RenderedElements
        
        Returns:
            List of tag names
        """
        tags = []
        for element in elements:
            tags.append(element.get('tag', 'div'))
            # Recursively add children tags
            tags.extend(self._extract_tag_sequence(element.get('children', [])))
        return tags
    
    def _levenshtein_distance(self, seq1: List[str], seq2: List[str]) -> int:
        """
        Calculate Levenshtein (edit) distance between two sequences.
        
        Args:
            seq1, seq2: Sequences to compare
        
        Returns:
            Edit distance
        """
        m, n = len(seq1), len(seq2)
        
        # Create DP table
        dp = [[0 for _ in range(n + 1)] for _ in range(m + 1)]
        
        # Initialize base cases
        for i in range(m + 1):
            dp[i][0] = i
        for j in range(n + 1):
            dp[0][j] = j
        
        # Fill DP table
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i-1] == seq2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = 1 + min(
                        dp[i-1][j],      # deletion
                        dp[i][j-1],      # insertion
                        dp[i-1][j-1]     # substitution
                    )
        
        return dp[m][n]
    
    def _compare_child_counts(self, block1: VisualBlock, block2: VisualBlock) -> float:
        """
        Compare number of children.
        
        Args:
            block1, block2: VisualBlocks to compare
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        count1 = len(block1.children) if block1.children else 0
        count2 = len(block2.children) if block2.children else 0
        
        if count1 == 0 and count2 == 0:
            return 1.0
        
        max_count = max(count1, count2)
        min_count = min(count1, count2)
        
        return min_count / max_count if max_count > 0 else 0.0
    
    def _compare_sizes(self, block1: VisualBlock, block2: VisualBlock) -> float:
        """
        Compare block sizes (heights).
        
        Args:
            block1, block2: VisualBlocks to compare
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        height1 = block1.bbox['height']
        height2 = block2.bbox['height']
        
        if height1 == 0 and height2 == 0:
            return 1.0
        
        max_height = max(height1, height2)
        min_height = min(height1, height2)
        
        return min_height / max_height if max_height > 0 else 0.0
    
    def _group_patterns(self, children: List[VisualBlock], 
                       similarity_matrix: List[List[float]]) -> List[Dict]:
        """
        Group similar children into patterns using clustering.
        
        Args:
            children: List of VisualBlocks
            similarity_matrix: Pairwise similarity matrix
        
        Returns:
            List of pattern dictionaries with instances
        """
        n = len(children)
        visited = [False] * n
        patterns = []
        
        for i in range(n):
            if visited[i]:
                continue
            
            # Start a new pattern cluster
            cluster = [i]
            visited[i] = True
            
            # Find all similar blocks
            for j in range(i + 1, n):
                if visited[j]:
                    continue
                
                # Check if j is similar to all blocks in cluster
                is_similar = all(
                    similarity_matrix[cluster_idx][j] >= self.similarity_threshold
                    for cluster_idx in cluster
                )
                
                if is_similar:
                    cluster.append(j)
                    visited[j] = True
            
            # Create pattern if cluster has multiple instances
            if len(cluster) >= 2:
                pattern = {
                    'instances': [children[idx] for idx in cluster],
                    'indices': cluster,
                    'count': len(cluster),
                    'representative': children[cluster[0]]  # Use first as representative
                }
                patterns.append(pattern)
        
        return patterns

# ============================================================================
# Phase 4: Row Identification
# ============================================================================

class RowIdentifier:
    """Identifies and extracts rows from detected patterns"""
    
    def __init__(self):
        """Initialize row identifier"""
        pass
    
    def identify_rows(self, patterns: List[Dict]) -> List[Dict]:
        """
        Identify rows from detected patterns.
        
        Args:
            patterns: List of pattern dictionaries from MDR
        
        Returns:
            List of table dictionaries with rows
        """
        logger.info(f"Starting row identification on {len(patterns)} patterns")
        
        tables = []
        
        for pattern in patterns:
            table = self._extract_table_from_pattern(pattern)
            if table:
                tables.append(table)
        
        logger.info(f"Identified {len(tables)} tables with rows")
        return tables
    
    def _extract_table_from_pattern(self, pattern: Dict) -> Dict:
        """
        Extract table structure from a single pattern.
        
        Args:
            pattern: Pattern dictionary with instances
        
        Returns:
            Table dictionary with rows
        """
        instances = pattern['instances']
        
        if not instances:
            return None
        
        # Extract rows from pattern instances
        rows = []
        for instance in instances:
            row_data = self._extract_row_data(instance)
            if row_data:
                rows.append(row_data)
        
        if not rows:
            return None
        
        return {
            'pattern': pattern,
            'rows': rows,
            'row_count': len(rows)
        }
    
    def _extract_row_data(self, block: VisualBlock) -> List[str]:
        """
        Extract text data from a row block.
        
        Args:
            block: VisualBlock representing a row
        
        Returns:
            List of cell text values
        """
        cells = []
        
        # If block has children, treat each child as a cell
        if block.children:
            for child in block.children:
                cell_text = self._extract_text_from_block(child)
                cells.append(cell_text)
        else:
            # If no children, extract from elements
            for element in block.elements:
                cell_text = self._extract_text_from_element(element)
                if cell_text:
                    cells.append(cell_text)
        
        return cells
    
    def _extract_text_from_block(self, block: VisualBlock) -> str:
        """Extract all text from a block"""
        text_parts = []
        
        for element in block.elements:
            text = self._extract_text_from_element(element)
            if text:
                text_parts.append(text)
        
        return ' '.join(text_parts).strip()
    
    def _extract_text_from_element(self, element: RenderedElement) -> str:
        """Recursively extract text from an element and its children"""
        text_parts = []
        
        # Get direct text
        if element.get('text'):
            text_parts.append(element['text'])
        
        # Get children text
        for child in element.get('children', []):
            child_text = self._extract_text_from_element(child)
            if child_text:
                text_parts.append(child_text)
        
        return ' '.join(text_parts).strip()

# ============================================================================
# Phase 5: Column Alignment Detection
# ============================================================================

class ColumnAligner:
    """Detects and aligns columns in table rows"""
    
    def __init__(self):
        """Initialize column aligner"""
        self.alignment_tolerance = 15  # Pixels tolerance for column alignment
    
    def align_columns(self, tables: List[Dict]) -> List[Dict]:
        """
        Detect column boundaries and align cells.
        
        Args:
            tables: List of table dictionaries with rows
        
        Returns:
            List of tables with aligned columns
        """
        logger.info(f"Starting column alignment on {len(tables)} tables")
        
        aligned_tables = []
        
        for table in tables:
            aligned_table = self._align_table_columns(table)
            if aligned_table:
                aligned_tables.append(aligned_table)
        
        logger.info(f"Aligned {len(aligned_tables)} tables")
        return aligned_tables
    
    def _align_table_columns(self, table: Dict) -> Dict:
        """
        Align columns for a single table.
        
        Args:
            table: Table dictionary with rows
        
        Returns:
            Table with aligned columns
        """
        pattern = table['pattern']
        instances = pattern['instances']
        
        if not instances:
            return None
        
        # Detect column boundaries from visual blocks
        column_boundaries = self._detect_column_boundaries(instances)
        
        if not column_boundaries:
            # Fallback: use row data as-is
            return {
                'rows': table['rows'],
                'column_count': len(table['rows'][0]) if table['rows'] else 0,
                'column_boundaries': []
            }
        
        # Align rows to column boundaries
        aligned_rows = self._align_rows_to_columns(instances, column_boundaries)
        
        return {
            'rows': aligned_rows,
            'column_count': len(column_boundaries),
            'column_boundaries': column_boundaries
        }
    
    def _detect_column_boundaries(self, instances: List[VisualBlock]) -> List[float]:
        """
        Detect column boundaries from row instances.
        
        Strategy:
        1. Collect all child x-positions from all instances
        2. Cluster similar x-positions
        3. Return cluster centers as column boundaries
        
        Args:
            instances: List of VisualBlock instances (rows)
        
        Returns:
            List of x-positions representing column boundaries
        """
        # Collect all x-positions from children
        all_x_positions = []
        
        for instance in instances:
            if instance.children and len(instance.children) > 1:
                for child in instance.children:
                    all_x_positions.append(child.bbox['x'])
            elif instance.elements and instance.elements[0].get('children'):
                # Fallback to DOM elements if VIPS didn't partition the row
                for dom_child in instance.elements[0]['children']:
                    all_x_positions.append(dom_child['bbox']['x'])
        
        
        if not all_x_positions:
            return []
        
        # Cluster x-positions
        clusters = self._cluster_positions(all_x_positions)
        
        # Sort clusters by position
        clusters.sort()
        
        return clusters
    
    def _cluster_positions(self, positions: List[float]) -> List[float]:
        """
        Cluster positions that are close together.
        
        Args:
            positions: List of x-positions
        
        Returns:
            List of cluster centers
        """
        if not positions:
            return []
        
        # Sort positions
        sorted_positions = sorted(positions)
        
        # Greedy clustering
        clusters = []
        current_cluster = [sorted_positions[0]]
        
        for pos in sorted_positions[1:]:
            # Check if position is close to current cluster
            cluster_mean = sum(current_cluster) / len(current_cluster)
            
            if abs(pos - cluster_mean) <= self.alignment_tolerance:
                current_cluster.append(pos)
            else:
                # Start new cluster
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [pos]
        
        # Add last cluster
        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))
        
        return clusters
    
    def _align_rows_to_columns(self, instances: List[VisualBlock], 
                               column_boundaries: List[float]) -> List[List[str]]:
        """
        Align row data to detected column boundaries.
        
        Args:
            instances: List of VisualBlock instances (rows)
            column_boundaries: List of column x-positions
        
        Returns:
            List of rows with aligned cells
        """
        aligned_rows = []
        
        for instance in instances:
            row = self._align_single_row(instance, column_boundaries)
            aligned_rows.append(row)
        
        return aligned_rows
    
    def _align_single_row(self, instance: VisualBlock, 
                         column_boundaries: List[float]) -> List[str]:
        """
        Align a single row to column boundaries.
        
        Args:
            instance: VisualBlock representing a row
            column_boundaries: List of column x-positions
        
        Returns:
            List of cell values aligned to columns
        """
        # Initialize cells
        cells = [''] * len(column_boundaries)
        
        # Assign children to columns based on x-position
        if instance.children and len(instance.children) > 1:
            for child in instance.children:
                child_x = child.bbox['x']
                
                # Find closest column
                column_idx = self._find_closest_column(child_x, column_boundaries)
                
                # Extract text
                text = self._extract_text_from_block(child)
                
                # Assign to column (append if already has content)
                if cells[column_idx]:
                    cells[column_idx] += ' ' + text
                else:
                    cells[column_idx] = text
        elif instance.elements and instance.elements[0].get('children'):
            # Fallback to DOM elements
            for dom_child in instance.elements[0]['children']:
                child_x = dom_child['bbox']['x']
                column_idx = self._find_closest_column(child_x, column_boundaries)
                text = self._extract_text_from_element(dom_child)
                if cells[column_idx]:
                    cells[column_idx] += ' ' + text
                else:
                    cells[column_idx] = text
        else:
            # Fallback: extract all text into first column
            text = self._extract_text_from_block(instance)
            cells[0] = text
        
        return cells
    
    def _find_closest_column(self, x_position: float, 
                            column_boundaries: List[float]) -> int:
        """
        Find the closest column boundary to a given x-position.
        
        Args:
            x_position: X-position to match
            column_boundaries: List of column x-positions
        
        Returns:
            Index of closest column
        """
        min_distance = float('inf')
        closest_idx = 0
        
        for idx, boundary in enumerate(column_boundaries):
            distance = abs(x_position - boundary)
            if distance < min_distance:
                min_distance = distance
                closest_idx = idx
        
        return closest_idx
    
    def _extract_text_from_block(self, block: VisualBlock) -> str:
        """Extract all text from a block"""
        text_parts = []
        
        for element in block.elements:
            text = self._extract_text_from_element(element)
            if text:
                text_parts.append(text)
        
        return ' '.join(text_parts).strip()
    
    def _extract_text_from_element(self, element: RenderedElement) -> str:
        """Recursively extract text from an element"""
        text_parts = []
        
        if element.get('text'):
            text_parts.append(element['text'])
        
        for child in element.get('children', []):
            child_text = self._extract_text_from_element(child)
            if child_text:
                text_parts.append(child_text)
        
        return ' '.join(text_parts).strip()

# ============================================================================
# Phase 6: Header Detection
# ============================================================================

class HeaderDetector:
    """Detects header rows in tables"""
    
    def __init__(self):
        """Initialize header detector"""
        self.font_weight_threshold = 600  # Bold text threshold
        self.font_size_ratio = 1.1        # Header font size ratio vs body
    
    def detect_headers(self, tables: List[Dict]) -> List[Dict]:
        """
        Detect header rows in tables.
        
        Args:
            tables: List of table dictionaries with aligned rows
        
        Returns:
            List of tables with headers identified
        """
        logger.info(f"Starting header detection on {len(tables)} tables")
        
        tables_with_headers = []
        
        for table in tables:
            table_with_header = self._detect_table_header(table)
            tables_with_headers.append(table_with_header)
        
        logger.info(f"Header detection complete")
        return tables_with_headers
    
    def _detect_table_header(self, table: Dict) -> Dict:
        """
        Detect header for a single table.
        
        Args:
            table: Table dictionary with rows
        
        Returns:
            Table with headers field populated
        """
        rows = table.get('rows', [])
        
        if not rows:
            return {
                'headers': [],
                'rows': [],
                'column_count': table.get('column_count', 0)
            }
        
        # Try multiple heuristics to detect header
        header_idx = self._find_header_row(table)
        
        if header_idx is not None and header_idx < len(rows):
            # Extract header
            headers = rows[header_idx]
            data_rows = rows[:header_idx] + rows[header_idx + 1:]
            
            logger.debug(f"Header detected at row {header_idx}: {headers}")
        else:
            # No header detected - use first row or generate generic headers
            if self._is_likely_header(rows[0], rows[1:] if len(rows) > 1 else []):
                headers = rows[0]
                data_rows = rows[1:]
                logger.debug(f"First row used as header: {headers}")
            else:
                # Generate generic headers
                headers = [f"Column {i+1}" for i in range(table.get('column_count', len(rows[0])))]
                data_rows = rows
                logger.debug("No header detected, using generic headers")
        
        return {
            'headers': headers,
            'rows': data_rows,
            'column_count': table.get('column_count', len(headers))
        }
    
    def _find_header_row(self, table: Dict) -> int:
        """
        Find the index of the header row.
        
        Uses multiple heuristics:
        1. First row is often the header
        2. Row with different styling (bold, larger font, different background)
        3. Row with non-numeric content when others are numeric
        
        Args:
            table: Table dictionary
        
        Returns:
            Index of header row, or None if not found
        """
        rows = table.get('rows', [])
        
        if not rows:
            return None
        
        # Heuristic 1: First row is most likely header
        # Check if first row looks like a header
        if len(rows) > 1:
            if self._is_likely_header(rows[0], rows[1:]):
                return 0
        
        # Heuristic 2: Check for styling differences (would need visual block info)
        # For now, we'll use the pattern instances if available
        pattern = table.get('pattern')
        if pattern and pattern.get('instances'):
            header_idx = self._detect_header_from_visual_blocks(pattern['instances'])
            if header_idx is not None:
                return header_idx
        
        # Default: assume first row is header if table has multiple rows
        return 0 if len(rows) > 1 else None
    
    def _is_likely_header(self, candidate_row: List[str], data_rows: List[List[str]]) -> bool:
        """
        Determine if a row is likely a header.
        
        Heuristics:
        1. Contains mostly text (not numbers)
        2. Shorter text than data rows
        3. No repeated values
        
        Args:
            candidate_row: Potential header row
            data_rows: Data rows to compare against
        
        Returns:
            True if likely a header
        """
        if not candidate_row or not data_rows:
            return True  # Default to header if can't compare
        
        # Heuristic 1: Headers are usually text, not numbers
        numeric_count = sum(1 for cell in candidate_row if self._is_numeric(cell))
        text_ratio = 1.0 - (numeric_count / len(candidate_row))
        
        # Heuristic 2: Headers are usually shorter
        candidate_avg_len = sum(len(cell) for cell in candidate_row) / len(candidate_row)
        
        if data_rows:
            data_avg_len = sum(
                sum(len(cell) for cell in row) / len(row)
                for row in data_rows if row
            ) / len(data_rows)
            
            is_shorter = candidate_avg_len < data_avg_len * 1.5
        else:
            is_shorter = True
        
        # Heuristic 3: Headers usually don't have repeated values
        has_unique_values = len(set(candidate_row)) == len(candidate_row)
        
        # Combine heuristics
        return text_ratio > 0.5 or (is_shorter and has_unique_values)
    
    def _is_numeric(self, text: str) -> bool:
        """Check if text is numeric"""
        if not text:
            return False
        
        # Remove common formatting
        cleaned = text.replace(',', '').replace('$', '').replace('%', '').strip()
        
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    
    def _detect_header_from_visual_blocks(self, instances: List[VisualBlock]) -> int:
        """
        Detect header from visual block styling.
        
        Args:
            instances: List of VisualBlock instances (rows)
        
        Returns:
            Index of header row, or None
        """
        if not instances:
            return None
        
        # Check first instance for header characteristics
        first_instance = instances[0]
        
        # Look for styling differences
        has_bold = self._has_bold_text(first_instance)
        has_larger_font = self._has_larger_font(first_instance, instances[1:] if len(instances) > 1 else [])
        has_different_bg = self._has_different_background(first_instance, instances[1:] if len(instances) > 1 else [])
        
        # If first row has header characteristics, it's likely a header
        if has_bold or has_larger_font or has_different_bg:
            logger.debug("Header detected by visual styling")
            return 0
        
        return None
    
    def _has_bold_text(self, block: VisualBlock) -> bool:
        """Check if block has bold text"""
        for element in block.elements:
            font_weight = element.get('styles', {}).get('font-weight', '400')
            try:
                weight = int(font_weight) if font_weight.isdigit() else 400
                if weight >= self.font_weight_threshold:
                    return True
            except:
                if font_weight == 'bold':
                    return True
        return False
    
    def _has_larger_font(self, block: VisualBlock, other_blocks: List[VisualBlock]) -> bool:
        """Check if block has larger font than others"""
        if not other_blocks:
            return False
        
        # Get font size of first block
        block_font_size = self._get_font_size(block)
        
        # Get average font size of other blocks
        other_sizes = [self._get_font_size(b) for b in other_blocks[:3]]  # Sample first 3
        avg_other_size = sum(other_sizes) / len(other_sizes) if other_sizes else block_font_size
        
        return block_font_size > avg_other_size * self.font_size_ratio
    
    def _get_font_size(self, block: VisualBlock) -> float:
        """Get font size from block"""
        for element in block.elements:
            font_size_str = element.get('styles', {}).get('font-size', '16px')
            try:
                # Parse font size (e.g., "16px" -> 16.0)
                size = float(font_size_str.replace('px', '').replace('pt', '').strip())
                return size
            except:
                pass
        return 16.0  # Default
    
    def _has_different_background(self, block: VisualBlock, other_blocks: List[VisualBlock]) -> bool:
        """Check if block has different background color"""
        if not other_blocks:
            return False
        
        block_bg = self._get_background_color(block)
        
        # Check if different from majority of other blocks
        other_bgs = [self._get_background_color(b) for b in other_blocks[:3]]
        
        # If block background is different from all others, it might be a header
        return all(block_bg != bg for bg in other_bgs) and block_bg != 'transparent'
    
    def _get_background_color(self, block: VisualBlock) -> str:
        """Get background color from block"""
        for element in block.elements:
            bg_color = element.get('styles', {}).get('background-color', 'transparent')
            if bg_color and bg_color != 'transparent':
                return bg_color
        return 'transparent'

# ============================================================================
# Phase 7: Table Validation
# ============================================================================

class TableValidator:
    """Validates extracted tables for quality and correctness"""
    
    def __init__(self):
        """Initialize table validator"""
        self.min_rows = 2              # Minimum rows (excluding header)
        self.min_columns = 2           # Minimum columns
        self.min_data_density = 0.5    # Minimum ratio of non-empty cells
        self.max_column_variance = 0.3 # Maximum variance in column count across rows
    
    def validate_tables(self, tables: List[Dict]) -> List[Dict]:
        """
        Validate tables and filter out low-quality ones.
        
        Args:
            tables: List of table dictionaries with headers and rows
        
        Returns:
            List of validated tables
        """
        logger.info(f"Starting validation on {len(tables)} tables")
        
        valid_tables = []
        
        for i, table in enumerate(tables):
            if self._is_valid_table(table):
                valid_tables.append(table)
                logger.debug(f"Table {i} passed validation")
            else:
                logger.debug(f"Table {i} failed validation")
        
        logger.info(f"Validation complete: {len(valid_tables)}/{len(tables)} tables passed")
        return valid_tables
    
    def _is_valid_table(self, table: Dict) -> bool:
        """
        Check if a table meets quality criteria.
        
        Validation checks:
        1. Minimum row count
        2. Minimum column count
        3. Data density (non-empty cells)
        4. Column consistency (all rows have similar column count)
        
        Args:
            table: Table dictionary
        
        Returns:
            True if table is valid
        """
        rows = table.get('rows', [])
        headers = table.get('headers', [])
        column_count = table.get('column_count', 0)
        
        # Check 1: Minimum rows
        if len(rows) < self.min_rows:
            logger.debug(f"Failed: Too few rows ({len(rows)} < {self.min_rows})")
            return False
        
        # Check 2: Minimum columns
        if column_count < self.min_columns:
            logger.debug(f"Failed: Too few columns ({column_count} < {self.min_columns})")
            return False
        
        # Check 3: Data density
        data_density = self._calculate_data_density(rows)
        if data_density < self.min_data_density:
            logger.debug(f"Failed: Low data density ({data_density:.2f} < {self.min_data_density})")
            return False
        
        # Check 4: Column consistency
        if not self._has_consistent_columns(rows, column_count):
            logger.debug("Failed: Inconsistent column count across rows")
            return False
        
        return True
    
    def _calculate_data_density(self, rows: List[List[str]]) -> float:
        """
        Calculate the ratio of non-empty cells.
        
        Args:
            rows: List of table rows
        
        Returns:
            Data density ratio (0.0 to 1.0)
        """
        if not rows:
            return 0.0
        
        total_cells = sum(len(row) for row in rows)
        if total_cells == 0:
            return 0.0
        
        non_empty_cells = sum(
            1 for row in rows 
            for cell in row 
            if cell and cell.strip()
        )
        
        return non_empty_cells / total_cells
    
    def _has_consistent_columns(self, rows: List[List[str]], expected_columns: int) -> bool:
        """
        Check if rows have consistent column counts.
        
        Args:
            rows: List of table rows
            expected_columns: Expected number of columns
        
        Returns:
            True if column counts are consistent
        """
        if not rows:
            return True
        
        # Calculate variance in column counts
        column_counts = [len(row) for row in rows]
        
        # Allow some variance (e.g., 30%)
        min_count = min(column_counts)
        max_count = max(column_counts)
        
        if max_count == 0:
            return False
        
        variance = (max_count - min_count) / max_count
        
        return variance <= self.max_column_variance

# ============================================================================
# Phase 8: Table Reconstruction
# ============================================================================

class TableReconstructor:
    """Reconstructs and formats final table output"""
    
    def __init__(self):
        """Initialize table reconstructor"""
        pass
    
    def reconstruct_tables(self, tables: List[Dict]) -> List[Dict]:
        """
        Reconstruct tables into final output format.
        
        Args:
            tables: List of validated table dictionaries
        
        Returns:
            List of reconstructed tables with metadata
        """
        logger.info(f"Starting table reconstruction on {len(tables)} tables")
        
        reconstructed = []
        
        for i, table in enumerate(tables):
            reconstructed_table = self._reconstruct_table(table, i)
            reconstructed.append(reconstructed_table)
        
        logger.info(f"Reconstruction complete: {len(reconstructed)} tables")
        return reconstructed
    
    def _reconstruct_table(self, table: Dict, table_id: int) -> Dict:
        """
        Reconstruct a single table.
        
        Args:
            table: Table dictionary
            table_id: Unique identifier for the table
        
        Returns:
            Reconstructed table with metadata
        """
        headers = table.get('headers', [])
        rows = table.get('rows', [])
        column_count = table.get('column_count', 0)
        
        # Normalize rows to have consistent column count
        normalized_rows = self._normalize_rows(rows, column_count)
        
        # Normalize headers
        normalized_headers = self._normalize_headers(headers, column_count)
        
        # Calculate statistics
        stats = self._calculate_statistics(normalized_rows, normalized_headers)
        
        return {
            'id': table_id,
            'headers': normalized_headers,
            'rows': normalized_rows,
            'metadata': {
                'row_count': len(normalized_rows),
                'column_count': column_count,
                'data_density': stats['data_density'],
                'has_headers': len(normalized_headers) > 0 and any(h for h in normalized_headers)
            }
        }
    
    def _normalize_rows(self, rows: List[List[str]], expected_columns: int) -> List[List[str]]:
        """
        Normalize rows to have consistent column count.
        
        Args:
            rows: List of table rows
            expected_columns: Expected number of columns
        
        Returns:
            Normalized rows
        """
        normalized = []
        
        for row in rows:
            # Pad or trim to expected column count
            if len(row) < expected_columns:
                # Pad with empty strings
                normalized_row = row + [''] * (expected_columns - len(row))
            elif len(row) > expected_columns:
                # Trim excess columns
                normalized_row = row[:expected_columns]
            else:
                normalized_row = row
            
            # Clean cell values
            normalized_row = [self._clean_cell(cell) for cell in normalized_row]
            normalized.append(normalized_row)
        
        return normalized
    
    def _normalize_headers(self, headers: List[str], expected_columns: int) -> List[str]:
        """
        Normalize headers to have consistent column count.
        
        Args:
            headers: List of header values
            expected_columns: Expected number of columns
        
        Returns:
            Normalized headers
        """
        if not headers:
            # Generate generic headers
            return [f"Column {i+1}" for i in range(expected_columns)]
        
        # Pad or trim to expected column count
        if len(headers) < expected_columns:
            normalized = headers + [f"Column {i+1}" for i in range(len(headers), expected_columns)]
        elif len(headers) > expected_columns:
            normalized = headers[:expected_columns]
        else:
            normalized = headers
        
        # Clean header values
        normalized = [self._clean_cell(h) if h else f"Column {i+1}" for i, h in enumerate(normalized)]
        
        return normalized
    
    def _clean_cell(self, cell: str) -> str:
        """
        Clean cell value.
        
        Args:
            cell: Cell value
        
        Returns:
            Cleaned cell value
        """
        if not cell:
            return ''
        
        # Strip whitespace
        cleaned = cell.strip()
        
        # Remove excessive whitespace
        cleaned = ' '.join(cleaned.split())
        
        return cleaned
    
    def _calculate_statistics(self, rows: List[List[str]], headers: List[str]) -> Dict:
        """
        Calculate table statistics.
        
        Args:
            rows: Table rows
            headers: Table headers
        
        Returns:
            Dictionary of statistics
        """
        if not rows:
            return {'data_density': 0.0}
        
        total_cells = sum(len(row) for row in rows)
        non_empty_cells = sum(1 for row in rows for cell in row if cell and cell.strip())
        
        return {
            'data_density': non_empty_cells / total_cells if total_cells > 0 else 0.0
        }

# ============================================================================
# Main API
# ============================================================================

def extract_tables(source: str) -> List[Dict]:
    """
    Extract tables from a webpage (main entry point).
    
    Args:
        source: URL or local file path
    
    Returns:
        List of table dictionaries with 'id', 'headers', 'rows', and 'metadata'
    """
    # Phase 0: Render page
    renderer = PageRenderer()
    rendered_tree = renderer.render_page(source)
    
    # Phase 1: VIPS segmentation
    segmenter = VIPSSegmenter()
    visual_blocks = segmenter.segment(rendered_tree)
    
    # Phase 2: Candidate block selection
    selector = CandidateSelector()
    candidates = selector.select_candidates(visual_blocks)
    
    # Phase 3: MDR pattern detection
    detector = MDRPatternDetector()
    patterns = detector.detect_patterns(candidates)
    
    # Phase 4: Row identification
    row_identifier = RowIdentifier()
    tables = row_identifier.identify_rows(patterns)
    
    # Phase 5: Column alignment
    aligner = ColumnAligner()
    aligned_tables = aligner.align_columns(tables)
    
    # Phase 6: Header detection
    header_detector = HeaderDetector()
    tables_with_headers = header_detector.detect_headers(aligned_tables)
    
    # Phase 7: Table validation
    validator = TableValidator()
    valid_tables = validator.validate_tables(tables_with_headers)
    
    # Phase 8: Table reconstruction
    reconstructor = TableReconstructor()
    final_tables = reconstructor.reconstruct_tables(valid_tables)
    
    logger.info(f"All phases complete! Extracted {len(final_tables)} valid tables")
    
    return final_tables

# Example usage
if __name__ == "__main__":
    # Enable debug logging
    set_log_level("DEBUG")
    
    # Test with a local file
    source = "test_vips.html"
    
    try:
        tables = extract_tables(source)
        print(f"\n{'='*60}")
        print(f"Extracted {len(tables)} valid table(s)")
        print(f"{'='*60}\n")
        
        for table in tables:
            print(f"Table {table['id']}:")
            print(f"  Headers: {table['headers']}")
            print(f"  Rows: {table['metadata']['row_count']}")
            print(f"  Columns: {table['metadata']['column_count']}")
            print(f"  Data Density: {table['metadata']['data_density']:.2%}")
            print(f"  Has Headers: {table['metadata']['has_headers']}")
            print(f"\n  Data:")
            for j, row in enumerate(table['rows'][:5]):  # Show first 5 rows
                print(f"    Row {j+1}: {row}")
            if len(table['rows']) > 5:
                print(f"    ... and {len(table['rows']) - 5} more rows")
            print()
        
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
