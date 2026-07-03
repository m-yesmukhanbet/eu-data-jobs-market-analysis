"""
Transforms raw Adzuna JSON pages into two clean tables:
  - jobs: one row per unique job id
  - job_skills: long-format (job_id, skill) — one row per detected skill

Reads:  data/raw/*.json
Writes: PostgreSQL tables jobs, job_skills (replace)
        data/processed/jobs_clean.csv
        data/processed/job_skills.csv

Usage:
    python src/transform_jobs.py

Requires DATABASE_URL in .env, e.g.:
    DATABASE_URL=postgresql://localhost/eu_jobs
"""

import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ---- Config -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# GBP -> EUR conversion rate. Fixed manually, not fetched live, so results
# are reproducible. Update the date/rate here if you re-run months later.
GBP_TO_EUR_RATE = 1.17
GBP_TO_EUR_RATE_DATE = "2026-07-03"

JUNIOR_PATTERN = re.compile(
    r"\b(junior|intern|graduate|entry|trainee|stage|werkstudent|praktik|stagista|becario)\b",
    re.IGNORECASE,
)

REMOTE_PATTERN = re.compile(
    r"\b(remote|hybrid|smart working|home office|t[ée]l[ée]travail|teletrabajo)\b",
    re.IGNORECASE,
)

# Skill dictionary. Key = canonical skill name written to job_skills.
# Value = compiled regex tested against title + description (lowercased).
# Special cases handled explicitly:
#   - "power bi": space or hyphen between words
#   - "r": must be an isolated single letter, not part of another word
#     (word boundaries alone are not enough — "r" boundary-matches inside
#     things like "R&D" or "Sr." too loosely for our purposes, so we use a
#     tighter pattern requiring the token to be exactly "r").
def _wb(term: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)


SKILL_PATTERNS = {
    "sql": re.compile(
        r"\bsql\b|\bpostgresql\b|\bpostgres\b|\bmysql\b|\bt-sql\b|\btsql\b",
        re.IGNORECASE,
    ),
    "python": _wb("python"),
    "power bi": re.compile(r"\bpower[\s\-]?bi\b", re.IGNORECASE),
    "tableau": _wb("tableau"),
    "excel": _wb("excel"),
    # "r" as a bare single letter is unusable on multilingual text: German
    # "für", Italian articles, etc. produce isolated "r" tokens that have
    # nothing to do with the R programming language. Instead require R to
    # appear either with an explicit qualifier (R programming/language/
    # studio/stats) or directly next to skill-list punctuation like
    # "R," "R/" "(R)" "R." immediately after a skill-separator character,
    # which is how R actually shows up in skill lists ("SQL, Python, R,
    # Tableau"). This trades recall for precision deliberately.
    "r": re.compile(
        r"\bR\s+(programming|language|studio|stats|shiny)\b"
        r"|(?<![a-zA-Z])R(?=\s?[,/)\.])"
        r"|(?<=[,/(])R(?![a-zA-Z])",
    ),
    "sas": _wb("sas"),
    "looker": _wb("looker"),
    "qlik": _wb("qlik"),
    "dax": _wb("dax"),
    "snowflake": _wb("snowflake"),
    "bigquery": re.compile(r"\bbig[\s\-]?query\b", re.IGNORECASE),
    "aws": _wb("aws"),
    "azure": _wb("azure"),
    "gcp": _wb("gcp"),
    "spark": _wb("spark"),
    "pandas": _wb("pandas"),
    "git": _wb("git"),
    "powerpoint": re.compile(r"\bpower[\s\-]?point\b", re.IGNORECASE),
    "vba": _wb("vba"),
    "google sheets": re.compile(r"\bgoogle sheets\b", re.IGNORECASE),
    "matplotlib": _wb("matplotlib"),
    "numpy": _wb("numpy"),
}

LANGUAGE_PATTERNS = {
    "english": _wb("english"),
    "italian": _wb("italian"),
}


# ---- Loading raw data ---------------------------------------------------

def parse_filename(path: Path):
    """
    '{country}_{query_slug}_p{page}.json' -> (country, query_slug)
    e.g. 'it_data_analyst_p3.json' -> ('it', 'data_analyst')
    """
    stem = path.stem  # strips .json
    match = re.match(r"^([a-z]+)_(.+)_p\d+$", stem)
    if not match:
        print(f"  [warn] filename doesn't match expected pattern, skipping: {path.name}")
        return None, None
    return match.group(1), match.group(2)


def load_raw_records():
    records = []
    files = sorted(RAW_DIR.glob("*.json"))
    print(f"Found {len(files)} raw files in {RAW_DIR}")

    for path in files:
        country, query_slug = parse_filename(path)
        if country is None:
            continue

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  [warn] corrupt JSON, skipping: {path.name} ({e})")
            continue

        for r in data.get("results", []):
            r["_country"] = country
            r["_search_query"] = query_slug.replace("_", " ")
            records.append(r)

    print(f"Loaded {len(records)} raw job records (before dedup)")
    return records


# ---- City extraction ------------------------------------------------------

def extract_city(location_field):
    """
    Adzuna 'location.area' is a list like:
    ["UK", "London", "City of London"] (broad -> specific) or sometimes
    just ["UK"] or missing entirely. We take the last element as the most
    specific known place. Falls back to location.display_name, then None.
    """
    if not isinstance(location_field, dict):
        return None

    area = location_field.get("area")
    if isinstance(area, list) and len(area) > 0:
        last = area[-1]
        if isinstance(last, str) and last.strip():
            return last.strip()

    display_name = location_field.get("display_name")
    if isinstance(display_name, str) and display_name.strip():
        return display_name.strip()

    return None


# ---- Skill extraction ------------------------------------------------------

def extract_skills(text: str):
    if not isinstance(text, str) or not text:
        return []
    found = []
    for skill, pattern in {**SKILL_PATTERNS, **LANGUAGE_PATTERNS}.items():
        if pattern.search(text):
            found.append(skill)
    return found


# ---- Main transform ------------------------------------------------------

def build_jobs_dataframe(records):
    rows = []
    for r in records:
        location = r.get("location", {})
        salary_min = r.get("salary_min")
        salary_max = r.get("salary_max")

        rows.append({
            "id": r.get("id"),
            "title": r.get("title", "") or "",
            "company": (r.get("company") or {}).get("display_name"),
            "country": r.get("_country"),
            "city": extract_city(location),
            "created": r.get("created"),
            "description": r.get("description", "") or "",
            "salary_min": salary_min,
            "salary_max": salary_max,
            "salary_is_predicted": bool(int(r.get("salary_is_predicted", 0)))
                if r.get("salary_is_predicted") is not None else None,
            "contract_time": r.get("contract_time"),
            "url": r.get("redirect_url"),
            "search_query": r.get("_search_query"),
        })

    df = pd.DataFrame(rows)

    before = len(df)
    df = df.dropna(subset=["id"])
    df = df.drop_duplicates(subset=["id"], keep="first")
    print(f"Deduplicated: {before} -> {len(df)} rows (removed {before - len(df)})")

    df["created"] = pd.to_datetime(df["created"], errors="coerce").dt.date

    # salary_mid: mean of min/max, NaN if both missing
    df["salary_mid"] = df[["salary_min", "salary_max"]].mean(axis=1, skipna=True)
    df.loc[df["salary_min"].isna() & df["salary_max"].isna(), "salary_mid"] = np.nan

    # salary_eur: convert GBP listings, pass through others as-is
    df["salary_eur"] = np.where(
        df["country"] == "gb",
        df["salary_mid"] * GBP_TO_EUR_RATE,
        df["salary_mid"],
    )

    combined_text = (df["title"].fillna("") + " " + df["description"].fillna(""))
    df["is_junior"] = df["title"].fillna("").apply(lambda t: bool(JUNIOR_PATTERN.search(t)))
    df["is_remote"] = combined_text.apply(lambda t: bool(REMOTE_PATTERN.search(t)))

    return df, combined_text


def build_skills_dataframe(df, combined_text):
    skill_rows = []
    for job_id, text in zip(df["id"], combined_text):
        for skill in extract_skills(text):
            skill_rows.append({"job_id": job_id, "skill": skill})
    return pd.DataFrame(skill_rows, columns=["job_id", "skill"])


def print_sanity_report(df, skills_df):
    print("\n=== SANITY REPORT ===")
    total = len(df)
    print(f"Total jobs: {total}")

    with_salary = df["salary_mid"].notna().sum()
    pct_salary = 100 * with_salary / total if total else 0
    print(f"With salary_mid: {with_salary} ({pct_salary:.1f}%)")

    top5 = skills_df["skill"].value_counts().head(5)
    print("Top 5 skills:")
    for skill, count in top5.items():
        print(f"  {skill}: {count}")

    pct_junior = 100 * df["is_junior"].sum() / total if total else 0
    print(f"Junior-labeled share: {pct_junior:.1f}%")

    pct_remote = 100 * df["is_remote"].sum() / total if total else 0
    print(f"Remote-labeled share: {pct_remote:.1f}%")

    print(f"job_skills rows: {len(skills_df)} (jobs: {total}, ratio: "
          f"{len(skills_df) / total if total else 0:.2f}x)")

    if pct_salary < 20:
        print("\n[STOP] Salary coverage is below 20% — spec says to stop and "
              "discuss before proceeding to analysis.")

    dup_check = df["id"].duplicated().sum()
    print(f"Duplicate ids remaining: {dup_check} (should be 0)")


# ---- Entry point ------------------------------------------------------

def main():
    load_dotenv(PROJECT_ROOT / ".env")
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not found in .env, "
              "e.g. DATABASE_URL=postgresql://localhost/eu_jobs")
        sys.exit(1)

    if not RAW_DIR.exists() or not any(RAW_DIR.glob("*.json")):
        print(f"ERROR: no raw JSON files found in {RAW_DIR}. Run fetch_jobs.py first.")
        sys.exit(1)

    records = load_raw_records()
    if not records:
        print("ERROR: no job records parsed from raw files.")
        sys.exit(1)

    df, combined_text = build_jobs_dataframe(records)
    skills_df = build_skills_dataframe(df, combined_text)

    print_sanity_report(df, skills_df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    jobs_csv_path = PROCESSED_DIR / "jobs_clean.csv"
    skills_csv_path = PROCESSED_DIR / "job_skills.csv"
    df.to_csv(jobs_csv_path, index=False)
    skills_df.to_csv(skills_csv_path, index=False)
    print(f"\nWrote {jobs_csv_path}")
    print(f"Wrote {skills_csv_path}")

    engine = create_engine(db_url)
    df.to_sql("jobs", engine, if_exists="replace", index=False)
    skills_df.to_sql("job_skills", engine, if_exists="replace", index=False)
    print("Loaded tables 'jobs' and 'job_skills' into PostgreSQL (replace).")

    print(f"\nNote: GBP->EUR conversion rate used: {GBP_TO_EUR_RATE} "
          f"(fixed on {GBP_TO_EUR_RATE_DATE}). Record this in the README.")


if __name__ == "__main__":
    main()
