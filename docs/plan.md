# Project Plan: EU Data Jobs Market Analysis

## Goal
Which skills, cities, and market segments give an entry-level Data Analyst in the EU
the best return, and what do they actually pay. Client fiction: a university career
center preparing recommendations for analytics graduates.

## Deliverables
- Public GitHub repo: `eu-data-jobs-market-analysis`
- Power BI dashboard (3 pages)
- Excel one-pager for "leadership"
- README with 4-6 quantitative findings and a recommendation

## Data source
Adzuna Jobs API (official, free tier).
Endpoint: `https://api.adzuna.com/v1/api/jobs/{country}/search/{page}`
Params: `app_id`, `app_key`, `what`, `results_per_page=50`, `category=it-jobs`

Countries (6): `it, de, nl, fr, es, gb`
Search phrases (2): `"data analyst"`, `"business analyst"`
Depth: up to 20 pages per country x phrase pair -> ~12,000 postings ceiling before dedup

Free tier limit: ~250 calls/day (conservative). Collection plans for 1-2 days;
script must support resume and sleep between calls.

Fields: id, title, company.display_name, location (area array), created,
description (truncated ~500 chars - documented as a limitation), salary_min,
salary_max, salary_is_predicted, contract_time, redirect_url.

## Repository structure
eu-data-jobs-market-analysis/
├── README.md
├── .env.example          # ADZUNA_APP_ID=, ADZUNA_APP_KEY=
├── .gitignore            # .env, venv/, data/raw/, data/processed/
├── requirements.txt      # requests, pandas, numpy, sqlalchemy, psycopg2-binary, python-dotenv, openpyxl
├── data/{raw,processed}/ (+ .gitkeep)
├── src/
│   ├── fetch_jobs.py
│   └── transform_jobs.py
├── sql/
│   ├── 01_schema.sql
│   └── 02_analysis.sql
├── excel/                # management one-pager
├── dashboard/            # .pbix + screenshots
└── docs/plan.md          # this file

## Phases
- Phase 1 (0.5 day): repo scaffold. DONE.
- Phase 2: Postgres schema + fetch_jobs.py (Adzuna collection with resume/rate limiting)
- Phase 3: transform_jobs.py (clean, dedup, load into Postgres). DONE.
  3744 unique jobs, 73.4% with salary_mid, skill extraction limited by
  Adzuna's ~500-char description truncation (0.14 skills/job avg,
  not the 2x originally hoped for — documented as data source limitation
  in README, not a code defect).
- Phase 4: SQL analysis queries
- Phase 5: Power BI dashboard (3 pages)
- Phase 6: Excel one-pager
- Phase 7: README with findings and recommendation
