Local SEC filing inbox — classroom demo
=========================================
1. Drop actual SEC 8-K / 10-K / 10-Q text or HTML, searchable PDFs, or DOCX documents here.
2. In the app open SEC Alerts & Screening, edit the company watchlist as needed,
   then click "Scan SEC Filings folder". NO internet request is made by this action.
3. Local parsing uses keyword matching by default. Ollama is OPTIONAL.
4. For reliable company matching, add a row for the file in manifest.csv. A manifest
   identifies the filing but is NOT proof of authenticity; verify against the official SEC source.
5. A flagged document is a review task — never automatic compliance approval or rejection.
6. Scan reads up to 20MB per file; image-only scans need OCR (not provided).
7. The DEMO_ file here is a SYNTHETIC educational sample, not an SEC document.
8. The app persists demo alerts in data/app_state.json. Don't store confidential data here.

Manifest fields:
 filename,issuer_name,ticker,cik,form,filing_date,source_url,source_type

SEC filing access: https://www.sec.gov/edgar/search/
