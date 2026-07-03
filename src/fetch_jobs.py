"""
Adzuna Jobs API fetcher.

Iterates country x query x page(1..20), fetches JSON pages, and saves each
page as a raw JSON file. Designed to be safely re-run: if a page file already
exists on disk, it is skipped (resume after hitting the daily API quota).

Usage:
    python src/fetch_jobs.py

Requires ADZUNA_APP_ID and ADZUNA_APP_KEY in a .env file at project root.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# ---- Config -----------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

COUNTRIES = ["it", "de", "nl", "fr", "es", "gb"]
QUERIES = ["data analyst", "business analyst"]
MAX_PAGES = 20
RESULTS_PER_PAGE = 50
CATEGORY = "it-jobs"

REQUEST_TIMEOUT = 30  # seconds
BASE_SLEEP = 2.5  # seconds between successful calls
MAX_RETRIES = 3
RETRY_BASE_BACKOFF = 5  # seconds; doubles each retry

BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


# ---- Helpers -----------------------------------------------------------

def slugify(text: str) -> str:
    """'data analyst' -> 'data_analyst'"""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def raw_file_path(country: str, query: str, page: int) -> Path:
    return RAW_DIR / f"{country}_{slugify(query)}_p{page}.json"


def fetch_page(app_id: str, app_key: str, country: str, query: str, page: int):
    """
    Calls the Adzuna API for one page. Retries on HTTP 429/5xx with
    exponential backoff, up to MAX_RETRIES times. Returns parsed JSON dict
    on success, or None if all retries are exhausted.
    """
    url = BASE_URL.format(country=country, page=page)
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "what": query,
        "results_per_page": RESULTS_PER_PAGE,
        "category": CATEGORY,
        "content-type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as e:
            print(f"    [warn] network error on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES:
                return None
            time.sleep(RETRY_BASE_BACKOFF * (2 ** (attempt - 1)))
            continue

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 429 or 500 <= resp.status_code < 600:
            wait = RETRY_BASE_BACKOFF * (2 ** (attempt - 1))
            print(f"    [warn] HTTP {resp.status_code} on attempt {attempt}/{MAX_RETRIES}, "
                  f"sleeping {wait}s before retry")
            if attempt == MAX_RETRIES:
                print(f"    [error] giving up on {country}/{query}/page {page} "
                      f"after {MAX_RETRIES} attempts")
                return None
            time.sleep(wait)
            continue

        # Non-retryable error (e.g. 400, 401, 403) — log and bail immediately.
        print(f"    [error] HTTP {resp.status_code} (non-retryable): {resp.text[:300]}")
        return None

    return None


# ---- Main ----------------------------------------------------------------

def main():
    load_dotenv(PROJECT_ROOT / ".env")
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("ERROR: ADZUNA_APP_ID / ADZUNA_APP_KEY not found. "
              "Copy .env.example to .env and fill in your keys.")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    total_downloaded = 0
    total_skipped = 0

    for country in COUNTRIES:
        for query in QUERIES:
            print(f"\n=== {country} | '{query}' ===")
            for page in range(1, MAX_PAGES + 1):
                out_path = raw_file_path(country, query, page)

                if out_path.exists():
                    print(f"  page {page}: already exists, skipping (resume)")
                    total_skipped += 1
                    continue

                data = fetch_page(app_id, app_key, country, query, page)

                if data is None:
                    print(f"  page {page}: failed after retries, stopping "
                          f"this country/query pair")
                    break

                results = data.get("results", [])
                count = data.get("count")  # Adzuna's total-hits estimate

                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                total_downloaded += 1
                print(f"  page {page}: {len(results)} results "
                      f"(source total estimate: {count}) -> {out_path.name} "
                      f"| total downloaded so far: {total_downloaded}")

                if len(results) < RESULTS_PER_PAGE:
                    print(f"  page {page}: last page reached "
                          f"({len(results)} < {RESULTS_PER_PAGE}), moving to next query")
                    break

                time.sleep(BASE_SLEEP)

    print(f"\n=== DONE ===")
    print(f"Pages downloaded this run: {total_downloaded}")
    print(f"Pages skipped (already on disk): {total_skipped}")
    print(f"Raw files total in {RAW_DIR}: "
          f"{len(list(RAW_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
