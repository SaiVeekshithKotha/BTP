- Untill now(*now -> At Jan month's end*) I have implemented the web table extraction, which could identify the **tables which uses table tag**, and could be extracted in the form of csv files.
    - Algorithm Highlevel overview: 
        ```
        Extract table tags -> table dimension calculation -> Grid Based table data extraction -> header identification -> csv exporting.
        ```
    - Some problems still need to be addressed for the above part :
        - Headers identification (Mainly for tables with multi-line headers, and headers with rowspan and colspan).
        - Should properly test the code for various web pages and edge cases.
        - This approach ignores the nested tables, only the outer table is extracted.
        - This approach is also not properly optimised.

- now I am working on the **table detection** part, which could identify the tables in a web page, even if they are not using the table tag.
    - Algorithm Highlevel overview: 
        ```
        Render the web page -> VIPS(Visual Page Segmentation) -> Selecting Candid blocks -> MDR(mining data records) for mining repeated structures -> Row Identification -> Column Identification -> Header Detection -> Table Construction / Extraction -> csv exporting. 
        ```
    - 