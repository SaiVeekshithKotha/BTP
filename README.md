# Web Table Extraction Methods

This repository contains various methodologies developed for extracting tabular data from web pages, ranging from standard HTML tables to complex, non-semantic visual layouts.

## Directory Overview

* **`method_1/` : Basic Table Parser**
  A robust Python-based HTML table extraction tool designed for standard `<table>` tags. It intelligently parses tables from web pages and local HTML files, using a grid-based algorithm to accurately handle complex structures including `rowspan`, `colspan`, and nested tables.

* **`method_2/` : ARIA Role-Based Table Detection**
  Focuses on modern web applications that prioritize accessibility and semantic markup. This method extracts tabular data from webpages that use ARIA roles (e.g., `role="table"`, `role="row"`, `role="gridcell"`) instead of traditional HTML table elements. It parses the hierarchical structure defined by ARIA relationships to extract cell content while preserving row and column alignments.

* **`method_3/` : Non-Semantic Table Extraction (VIPS + MDR)**
  An advanced approach for extracting tables from modern webpages that use `<div>`, CSS Grid, Flexbox, or component-based frameworks (like React, Vue, Angular) where standard semantic tags are entirely absent. This method utilizes Vision-based Page Segmentation (VIPS) and Mining Data Records (MDR) to identify tables based purely on visual layout, bounding boxes, and computed CSS.

* **`LLM_dataset_analysis/` : LLM Pre-Training Dataset Research**
  A comprehensive but brief high level technical analysis of how modern datasets are engineered to shape model intelligence. This research covers scaling evolution (Chinchilla vs. Overtraining), compositional anatomy (Code/Math as reasoning drivers), filtering yields, and the pivot toward synthetic data. It includes verified case studies on frontier models like Llama 4 Scout, DeepSeek-V3, and Phi-series.
