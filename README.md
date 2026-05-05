# Job Hunter v2

A hobby project — automated job aggregation dashboard built with FastAPI, MongoDB, and vanilla JS.

Scrapes multiple Indian job boards in parallel, scores results by relevance, filters noise automatically, and presents everything in a clean dark dashboard with applied-job tracking.

---

## Features

- Scrapes **7 job sources**: Indeed, LinkedIn, TimesJobs, Instahyre, Cutshort, Shine, Freshersworld
- **Relevance scoring** — keywords from your target roles and skills drive the score
- **Hard filters** — bond clauses, 2+ year experience requirements, night shifts, overseas roles rejected automatically
- **Real-time progress** via Server-Sent Events (SSE) while hunt runs
- **MongoDB persistence** — jobs accumulate across runs, no data lost
- **Applied tracking** — mark jobs applied, filter by status
- **Stats dashboard** — by source, by location, top skills, score buckets
- **Profile-driven config** — fill your profile once, queries and scoring auto-generate

---

## Quick Start

### Requirements
- Python 3.10+
- MongoDB (local or Atlas free tier)

### Setup

```bash
git clone https://github.com/your-username/job-hunter.git
cd job-hunter

# Windows
setup.bat

# Mac/Linux
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in:

```env
MONGO_URI=mongodb+srv://your-connection-string
MONGO_DB=job_hunter
PORT=8000
```

### Run

```bash
# Windows
run.bat

# Mac/Linux
source venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

---

## First Run

1. Go to the **Profile tab** → fill in your details:
   - Name, email, phone
   - Target roles (e.g. `Java Developer, Full Stack Developer`)
   - Target locations (e.g. `Hyderabad, Remote`)
   - Skills (e.g. `Java, ReactJS, MySQL`)
   - Experience years (`0-1`, `1-2`, etc.)
2. Click **Save Profile** — queries and scoring rebuild automatically from your profile
3. Go to **Config tab** → click **↺ Rebuild from Profile** to sync scoring
4. Click **Run Hunt** in the sidebar

---

## Adding Filters Manually

All filters live in **`app/defaults.py`** and are editable in the **Config tab** in the dashboard.

### Score Threshold
Jobs below this score are hidden. Default: `3`. Raise it to see only high-confidence matches.

### Hard-Reject Roles (`hard_reject_roles`)
Strings that trigger instant rejection regardless of score. Add to the list in `defaults.py`:

```python
"hard_reject_roles": [
    "internship", "night shift", "us shift",        # already included
    "your-custom-reject-term",                       # add yours here
]
```

### Experience Filter (`hard_reject_exp`)
Rejects jobs that mention 2+ year requirements explicitly. Already covers common patterns like:
`"2+ years"`, `"minimum 2 years"`, `"1-3 years"`, etc.

Add patterns as needed:
```python
"hard_reject_exp": [
    "2+ years",
    "minimum 2 years",
    "your-pattern-here",
]
```

### Bond Filter (`hard_reject_bond`)
Rejects jobs with service bond / training fee clauses. Already covers:
`"service bond"`, `"training fee"`, `"2 lakh"`, `"repay"`, etc.

### Blacklist Companies
Add company names to avoid in the **Config tab** → *Blacklist Companies* field (comma-separated),
or directly in `defaults.py`:

```python
"blacklist_companies": [
    "company-name-to-avoid",
]
```

### Score Weights (`score_title`, `score_body`, `score_location`)
Positive numbers boost a job's score. Negative numbers penalise it.

```python
"score_title": {
    "java": 3,      # +3 if "java" in title
    "senior": -4,   # -4 if "senior" in title (auto-generated)
}
"score_body": {
    "spring": 1,    # +1 if "spring" in description
    "angular": -4,  # -4 if "angular" in description
}
```

These are auto-generated from your profile when you click *Rebuild from Profile*. You can also edit them manually in the Config tab JSON view.

---

## Naukri (Optional — Extra Setup Required)

Naukri is **disabled by default** because their job search API blocks automated requests with recaptcha, even with valid session cookies. The workaround requires a one-time browser-based login.

### How to enable Naukri

1. Add your Naukri credentials to `.env`:
   ```env
   NAUKRI_EMAIL=your@email.com
   NAUKRI_PASSWORD=yourpassword
   ```

2. Install Playwright and its browser:
   ```bash
   pip install playwright
   playwright install chromium
   ```

3. Run the login script once:
   ```bash
   python naukri_auth.py
   ```
   A browser window opens. It logs in automatically. Complete any CAPTCHA if it appears. Session is saved to `naukri_session.json` (~30 days valid).

4. In `app/hunter.py`, uncomment the Naukri block (search for `# To enable: run naukri_auth.py`).

5. Re-run the hunt. Re-run `naukri_auth.py` when results from Naukri go to 0.

> `naukri_session.json` is gitignored and never committed.

---

## Project Structure

```
job_hunter_v2/
├── app/
│   ├── main.py          # FastAPI routes
│   ├── hunter.py        # Hunt orchestrator + SSE progress
│   ├── scorer.py        # Relevance scoring + rejection logic
│   ├── defaults.py      # Default profile + config (edit to customise)
│   ├── db.py            # MongoDB connection + indexes
│   ├── models.py        # Pydantic models
│   └── sources/
│       ├── indeed.py        # Indeed RSS feed
│       ├── linkedin.py      # LinkedIn guest API
│       ├── timesjobs.py     # TimesJobs scraper
│       ├── instahyre.py     # Instahyre API
│       ├── cutshort.py      # Cutshort API
│       ├── shine.py         # Shine scraper
│       ├── freshersworld.py # Freshersworld scraper
│       ├── naukri.py        # Naukri (disabled — see above)
│       └── naukri_worker.py # Naukri subprocess worker
├── frontend/
│   └── index.html       # Single-page dashboard (no framework)
├── naukri_auth.py       # One-time Naukri login script
├── requirements.txt
├── setup.bat            # Windows setup
├── run.bat              # Windows run
└── .env.example         # Environment template
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI, uvicorn |
| Database | MongoDB (Motor async driver) |
| Scraping | requests, BeautifulSoup4, feedparser |
| Real-time | Server-Sent Events (SSE) |
| Frontend | Vanilla JS, HTML5, CSS3 |
| Optional | Playwright (Naukri only) |

---

## Notes

- This is a **hobby project** built for personal use. Respect each site's terms of service.
- Job data is stored locally in your own MongoDB. Nothing is shared externally.
- The `.env` file and `naukri_session.json` are gitignored — credentials never leave your machine.
