# EU Data Jobs Market Analysis

Analysis of entry-level Data Analyst / Business Analyst job postings across 6 EU
countries (IT, DE, NL, FR, ES, GB), using the Adzuna Jobs API. Goal: identify which
skills, cities, and segments give the best return for a graduate entering the field,
and what the real pay looks like.

Status: scaffold only. Data collection, analysis, and dashboard not yet built.
See `docs/plan.md` for the full project plan and phase breakdown.

## Stack
Python (requests, pandas), PostgreSQL 16, Power BI, Excel.

## Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ADZUNA_APP_ID / ADZUNA_APP_KEY
createdb eu_jobs
```
