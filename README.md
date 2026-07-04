# EU Data Analyst Job Market Analysis

## Question

What skills, cities, and segments pay off for an entry-level data analyst looking for work in the EU right now? This project pulls real job postings, extracts salary and skill data where available, and reports what the numbers show.

## Data

Source: [Adzuna Jobs API](https://developer.adzuna.com/). Collected July 3, 2026. 3,744 postings after deduplication, across 6 countries (GB, FR, DE, NL, IT, ES) using 2 search queries ("data analyst", "business analyst").

## Method

Python (requests) → PostgreSQL 16 → SQL for aggregation and skill extraction → Power BI for the interactive dashboard. Full pipeline and dashboard live in this repo; this README and the Excel one-pager summarize the findings for anyone who won't open Power BI.

## Findings

- **GB dominates the sample: 52% of postings, 1,962 of 3,744.** Adzuna's coverage is UK-centric. Cross-country comparisons in this dataset are directional, not representative of true EU-wide volume.
- **Salary medians where coverage is usable:** DE €68,000, GB €57,664, FR €43,500. GB and FR have workable salary coverage (100% and 57.7% respectively); DE, NL, ES, IT have far fewer salary-tagged postings and should be read as indicative only.
- **Junior discount in GB:** junior-tagged postings median €40,365 vs €57,664 for all GB postings, a 30% gap, based on 328 junior-tagged GB postings.
- **Skill premiums are associations, not causal effects.** Postings mentioning Azure show a €18,867 higher median salary than postings without it; SQL shows +€3,071. Both numbers come from a small, truncated sample (see limitations).
- **Only 8.6% of postings (323 of 3,744) have any extracted skill mention at all.** Adzuna truncates job descriptions to roughly 500 characters. Most tool and skill mentions that would appear later in a full listing never reach the API response. This is a limit of the data source, not the extraction logic.

## Recommendation

Based on demand volume and the (limited but directional) premium data, a junior candidate targeting these markets gets the most return from:

1. **SQL**: highest raw demand in the extracted skill sample (116 mentions, the most of any skill) and a measurable, if modest, premium (+€3,071 median).
2. **Power BI**: second-highest demand (100 mentions) and directly relevant to the BI/reporting analyst roles this search targeted.

Azure shows the largest premium (+€18,867) but on a much smaller base (57 mentions). It's a platform skill: worth adding after SQL and Power BI are solid, not instead of them.

## Limitations

- Job descriptions truncated to ~500 characters by the Adzuna API; skill extraction only sees the first fraction of most listings.
- `salary_is_predicted` is true for roughly half of GB postings. That flag marks Adzuna's own salary estimate, not always an employer-stated figure.
- Single-period snapshot (July 2026), not a time series. No trend claims are possible from this data alone.
- Strong UK bias in Adzuna's postings inventory; absolute counts by country reflect Adzuna's coverage, not real labor market size.
- Italy has only 5 salary-tagged postings out of 111. The €32,750 IT median above is not a reliable market figure.

## Structure

```
eu-data-jobs-market-analysis/
├── dashboard/              # Power BI dashboard (.pbix) + screenshots + source CSVs
├── excel/                  # eu_da_market_onepager.xlsx
├── src/                    # make_onepager.py and pipeline scripts
└── README.md
```

## Reproduce

```bash
git clone <repo-url>
cd eu-data-jobs-market-analysis
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 src/make_onepager.py   # regenerates excel/eu_da_market_onepager.xlsx from dashboard/*.csv
```

## Attribution

Job data from Adzuna API.
