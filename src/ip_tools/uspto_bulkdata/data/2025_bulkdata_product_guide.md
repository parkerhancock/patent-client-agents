# 2025 USPTO Bulk Data Product Guide

This note summarizes the two official references that outline every USPTO bulk-data offering. Use it whenever you need to identify the right product identifier before calling `bulkdata.search_products` or `bulkdata.get_product`.

## Source documents (bundled in this repo)
- [2025 Bulk Data Product Chart (PDF)](2025BulkDataProductChart.pdf)
  - One-page visual grid (last updated 30 Jul 2024) showing each dataset’s frequency (daily/weekly/monthly/one-time), coverage window, default formats (ASCII, SGML, XML, TIFF, PDF, JSON), and whether it ships file-wrapper, bibliographic, image, or text content.
- [2025 Bulk Data Product Descriptions (XLSX)](2025BulkDataProductDescriptions.xlsx)
  - 353-row catalog with the columns `Product Title`, `Product Code`, `Type/Acronym`, `Schedule`, `Coverage`, `Format`, `Filesize (Compressed)`, `URL`, and `Location`.
  - Filter by `Product Code` or `Schedule` to locate everything from Patent Official Gazettes to Cooperative Patent Classification extracts.

## Patent File Wrapper quick reference
| Product | Identifier | Update cadence | Coverage | Format | Notes |
| --- | --- | --- | --- | --- | --- |
| Patent File Wrapper (Bulk Datasets) – Weekly backfile | `PTFWPRE` | Weekly bundles in 10-year slices | 2001–present (rolling) | JSON | Use `include_files=true` to list `2001-2010`, `2011-2020`, `2021-2025` archives. Access via `https://api.uspto.gov/api/v1/datasets/products/PTFWPRE` |
| Patent File Wrapper (Bulk Datasets) – Daily delta | `PTFWPRD` | Daily delta drops | Rolling 7-day window | JSON | Ideal for incremental ingestion. Files named `patent-filewrapper-delta-json-YYYYMMDD.zip`. |

Example `curl` calls (replace `<API_KEY>`):
```bash
curl -H "x-api-key: <API_KEY>" \
     "https://api.uspto.gov/api/v1/datasets/products/PTFWPRE?includeFiles=true"

curl -H "x-api-key: <API_KEY>" \
     "https://api.uspto.gov/api/v1/datasets/products/files/PTFWPRD/patent-filewrapper-delta-json-20251110.zip" \
     -o patent-filewrapper-delta-json-20251110.zip
```

## Other patent-centric highlights from the chart
- **Patent Grant data**
  - Multi-page PDF images: coverage 1790–present, weekly drops plus complete backfile; formats PDF/TIFF, 30 MB+ per issue.
  - Full text with embedded images: 1970–present, available in SGML/XML + TIFF.
  - Red Book XML 2.5 (Grant + Application): backfiles 2001–present with weekly “frontfiles”.
- **Patent Application data**
  - Application text (PGPub XML) from 2001 onward; application images from 1976 onward.
  - Assignment text datasets spanning 2001–present.
- **Classification/CPC**
  - Cooperative Patent Classification (CPC) text and concordance datasets, refreshed weekly.
- **Trademark/PTAB**
  - Trademark Official Gazette, TTAB datasets, and other trademark bulk archives with similar cadence indicators.

For detailed pricing (usually $0 for online download), hosting location (USPTO vs. Data.gov), and data-size estimates, open the Excel file and filter to the product of interest. The PDF chart is the fastest way to visualize which formats and cadences exist for a given content type.

