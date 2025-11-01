# Website Design Analyzer

A professional, VS Code–friendly Flask app that captures website screenshots, evaluates design quality with a weighted scoring engine (ML/heuristics), exports a PDF report, uploads to Google Drive, and logs results to Google Sheets.

## Features
- Login (demo credentials via `.env`).
- Analyze by URL: headless Chromium (Playwright) full-page screenshot.
- Design evaluation engine:
  - Typography, Color & Contrast, Layout & Structure, Responsive, Accessibility.
  - Weighted 0–100 scoring (configurable in `app/config.py`).
- Recommendations generated from scores.
- PDF report with screenshot + breakdown (`app/services/report.py`).
- Google Drive upload (PyDrive2) & Google Sheets logging (gspread) – optional via env vars.
- Console panel & history view.
- Tailwind CSS (CDN) UI — clean, modern, and responsive.

## Quickstart
1. **Python 3.10+** recommended.
2. Create and configure environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   playwright install chromium
   cp .env.example .env
   # Edit .env (set admin credentials; optionally add Drive/Sheets IDs and service account file path)
   ```
3. Run the app:
   ```bash
   python -m app.app
   # Navigate to http://127.0.0.1:5000
   ```

## Google Cloud setup (optional but recommended)
- Create a **Service Account** with Drive & Sheets access. Download the JSON and set `GOOGLE_APPLICATION_CREDENTIALS=./google-service-account.json` in `.env`.
- Put the service account email as an editor on your Drive folder and Sheets doc.
- Set `DRIVE_PARENT_FOLDER_ID` and `SHEETS_SPREADSHEET_ID` in `.env`.

## Weights & Labels
Tune category weights in `app/config.py` so totals ≈ 1.0. Labels map final score to a quality grade.

## Notes
- The design metrics blend rule-based HTML analysis and basic image statistics — a lightweight ML-style approach.
- For stricter accessibility checks, you can integrate axe-core and Lighthouse via Chrome DevTools Protocol.
- Replace in-memory `HISTORY` with a database for production.

---

© 2025 Website Design Analyzer
