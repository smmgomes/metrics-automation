# Instagram Metrics Automation (ETL → Google Sheets)

A lightweight ETL pipeline that pulls post level Instagram metrics via the Instagram Graph API, transforms the data into time based reporting buckets, and loads the results into Google Sheets.
The ETL is triggered by a custom Google Apps Script button, allowing non-technical team members to refresh analytics with a single click.
The backend is hosted on Render.com using Flask and Gunicorn.

---

## Project Overview

This project automates Instagram analytics reporting by connecting Instagram data directly to Google Sheets.

The workflow is:
1. A team member clicks a button in Google Sheets.
2. Google Apps Script sends a POST request to the backend.
3. The backend runs the ETL process.
4. Metrics are written and updated in Google Sheets.

No one needs to run scripts locally or touch code after setup.

---

## Features

### One-Click ETL
- Triggered via a Google Apps Script button inside Google Sheets
- Sends an HTTP POST request to the backend API

### Extract (Instagram Graph API)
Pulls data from the Instagram Graph API (v24.0), including:
- Account follower count
- Media data:
  - Media ID
  - Permalink
  - Caption
  - Timestamp
- Post insights:
  - likes
  - comments
  - shares
  - follows
  - reach
  - total_interactions
  - views

Only posts from the last 40 days are fetched to stay within API limits.

### Transform
- Converts timestamps to date-level granularity
- Removes emojis from captions using `demoji`
- Shortens captions to the first five words
- Cleans formatting (removes commas and line breaks)
- Categorizes posts based on age:
  - Week 1: 7–13 days old
  - Week 2: 14–24 days old
  - Month: 30–40 days old
- Ignores posts outside these windows

### Load (Google Sheets)
- Uses a Google service account for authentication
- Writes data using batch updates for performance
- Preserves older metrics while adding new ones
- Stores historical follower counts
- Prevents duplicate runs on the same day

---

## Architecture

Google Sheets
- Hosts the reporting dashboard
- Contains a Google Apps Script button

Google Apps Script
- Uses Custom Buttons to excecute scripts

Render.com
- Hosts the Flask API
- Runs the ETL pipeline

Python Backend
- Handles extraction, transformation, and loading

---

## Tech Stack and Tools Used

### Platforms and Services
- Instagram Graph API
- Google Sheets API
- Google Apps Script
- Render.com

### Backend and Language
- Python
- Flask
- Gunicorn

### Google Sheets Integration
- gspread
- google-auth
- google-auth-oauthlib

### Utilities and Supporting Libraries
- requests
- python-dotenv
- demoji

---

## Dependencies (`requirements.txt`)
demoji@1.1.0
Flask@3.1.2
google-auth@2.41.1
google-auth-oauthlib@1.2.3
gspread@6.2.1
gunicorn@23.0.0
oauthlib@3.3.1
python-dotenv@1.2.1
requests@2.32.5
requests-oauthlib@2.0.0

---

## File Descriptions

### app.py
Flask application that exposes HTTP endpoints.

Endpoints:
- POST /run-etl  
  Triggers the ETL process and updates the Google Sheet

- POST /clear-sheet  
  Clears the data range in the Google Sheet

Uses:
- Flask for routing
- Gunicorn in production
- PORT environment variable (defaults to 5000 locally)

---

### instagram.py
Handles extraction and transformation of Instagram data.

Environment variables:
- ACCESS_TOKEN
- USER_ID

Responsibilities:
- Calls the Instagram Graph API
- Fetches follower count
- Retrieves recent media
- Fetches post insights
- Normalizes timestamps
- Cleans and shortens captions
- Returns structured post data

---

### sheets.py
Handles all Google Sheets operations.

Environment variables:
- GOOGLE_CREDS_JSON
- WORKSHEET_ID
- WORKSHEET_NAME

Configuration:
- OFFSET = 5 (data starts at row 5)
- ROW_MAX = 120

Responsibilities:
- Authenticates using a Google service account
- Reads existing sheet values
- Writes metrics using batch updates
- Preserves historical data
- Prevents duplicate daily runs
- Archives older posts no longer returned by the API

---

## Google Sheet Layout

Columns:
- A: Media ID
- B: Date
- C: Title (hyperlinked caption)

Metrics (7 columns each):
- Week 1 (D–J)
- Week 2 (K–Q)
- Month (R–X)

Metric order:
1. Likes
2. Comments
3. Shares
4. Follows
5. Reach
6. Total Interactions
7. Views

Additional columns:
- Y: Follower history
- Z: Last run date

---

## Environment Variables

Example `.env` file:

```
ACCESS_TOKEN=your_instagram_access_token
USER_ID=your_instagram_user_id

GOOGLE_CREDS_JSON={"type":"service_account", "...":"..."}
WORKSHEET_ID=your_google_sheet_id
WORKSHEET_NAME=your_sheet_tab_name
```

Notes:
- GOOGLE_CREDS_JSON must be valid JSON text
- The Google Sheet must be shared with the service account email

---

## Running Locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

API endpoints:
- http://localhost:5000/run-etl
- http://localhost:5000/clear-sheet

---

## Deployment (Render.com)

Typical setup:
- Build command: pip install -r requirements.txt
- Start command: gunicorn app:app
- Environment variables configured in the Render dashboard

---

## Google Apps Script Trigger (High-Level)

- A custom button is added to Google Sheets
- Clicking the button sends a POST request to:
  - /run-etl to refresh metrics
  - /clear-sheet to reset data
- This enables a no-code workflow for analytics updates

---

## Summary

This project provides a fully automated Instagram analytics pipeline that:
- Requires only one click to run
- Uses official APIs
- Writes structured, time-bucketed metrics
- Maintains historical data
- Is production-ready and cloud-hosted

It eliminates manual reporting while remaining accessible to non-technical users.