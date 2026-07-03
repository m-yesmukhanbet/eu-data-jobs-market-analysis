-- ============================================================
-- Phase 4: Analysis queries for eu_jobs
-- Run with: psql -U m.yesmukhanbet -d eu_jobs -f sql/02_analysis.sql
-- ============================================================


-- ============================================================
-- Q1. Overview: postings per country, % junior, % remote, % with salary
-- ============================================================
SELECT
    country,
    COUNT(*) AS total_jobs,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_junior) / COUNT(*), 1) AS pct_junior,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_remote) / COUNT(*), 1) AS pct_remote,
    ROUND(100.0 * COUNT(*) FILTER (WHERE salary_mid IS NOT NULL) / COUNT(*), 1) AS pct_with_salary
FROM jobs
GROUP BY country
ORDER BY total_jobs DESC;


-- ============================================================
-- Q2. Skill demand: % of postings mentioning each skill, per country
-- Uses a window function to compute each country's total job count
-- alongside the per-skill count, so the percentage is derived inline.
-- ============================================================
WITH country_totals AS (
    SELECT country, COUNT(*) AS country_job_count
    FROM jobs
    GROUP BY country
),
skill_country_counts AS (
    SELECT
        j.country,
        js.skill,
        COUNT(*) AS skill_job_count
    FROM job_skills js
    JOIN jobs j ON j.id = js.job_id
    GROUP BY j.country, js.skill
)
SELECT
    scc.country,
    scc.skill,
    scc.skill_job_count,
    ct.country_job_count,
    ROUND(100.0 * scc.skill_job_count / ct.country_job_count, 1) AS pct_of_country_postings
FROM skill_country_counts scc
JOIN country_totals ct ON ct.country = scc.country
ORDER BY scc.country, pct_of_country_postings DESC;


-- ============================================================
-- Q3. Salaries: median salary_eur per country, junior vs all,
-- predicted vs non-predicted shown as a separate column.
-- percentile_cont is a window/aggregate function per the phase spec.
-- ============================================================
SELECT
    country,
    -- all postings with a salary
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_eur)
            FILTER (WHERE salary_eur IS NOT NULL))::numeric, 0
    ) AS median_salary_eur_all,
    -- junior postings only
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_eur)
            FILTER (WHERE salary_eur IS NOT NULL AND is_junior))::numeric, 0
    ) AS median_salary_eur_junior,
    -- median restricted to non-predicted (i.e. employer-stated) salaries
    ROUND(
        (PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY salary_eur)
            FILTER (WHERE salary_eur IS NOT NULL AND salary_is_predicted = FALSE))::numeric, 0
    ) AS median_salary_eur_non_predicted,
    COUNT(*) FILTER (WHERE salary_eur IS NOT NULL) AS n_with_salary,
    COUNT(*) FILTER (WHERE salary_eur IS NOT NULL AND salary_is_predicted = FALSE) AS n_non_predicted
FROM jobs
GROUP BY country
ORDER BY median_salary_eur_all DESC NULLS LAST;


-- ============================================================
-- Q4. "Skill premium": median salary of postings WITH a skill vs
-- WITHOUT, restricted to skills with n >= 50 postings.
-- NOTE FOR README: this is an association, not causation — postings
-- requiring a skill may also cluster in higher-paying countries,
-- seniority levels, or company types. Do not present as a causal wage
-- effect of learning the skill.
-- ============================================================
WITH skill_job_ids AS (
    SELECT DISTINCT skill, job_id FROM job_skills
),
skill_counts AS (
    SELECT skill, COUNT(*) AS n
    FROM skill_job_ids
    GROUP BY skill
    HAVING COUNT(*) >= 50
),
with_skill AS (
    SELECT
        sc.skill,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY j.salary_eur) AS median_with_skill,
        COUNT(*) FILTER (WHERE j.salary_eur IS NOT NULL) AS n_with_salary
    FROM skill_counts sc
    JOIN skill_job_ids sji ON sji.skill = sc.skill
    JOIN jobs j ON j.id = sji.job_id
    GROUP BY sc.skill
),
without_skill AS (
    SELECT
        sc.skill,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY j.salary_eur) AS median_without_skill
    FROM skill_counts sc
    JOIN jobs j ON j.id NOT IN (
        SELECT job_id FROM skill_job_ids WHERE skill = sc.skill AND job_id IS NOT NULL
    )
    GROUP BY sc.skill
)
SELECT
    sc.skill,
    sc.n AS n_postings_with_skill,
    ws.n_with_salary,
    ROUND(w.median_with_skill::numeric, 0) AS median_salary_eur_with_skill,
    ROUND(wo.median_without_skill::numeric, 0) AS median_salary_eur_without_skill,
    ROUND((w.median_with_skill - wo.median_without_skill)::numeric, 0) AS diff_eur
FROM skill_counts sc
JOIN with_skill w ON w.skill = sc.skill
JOIN without_skill wo ON wo.skill = sc.skill
JOIN with_skill ws ON ws.skill = sc.skill
ORDER BY diff_eur DESC NULLS LAST;


-- ============================================================
-- Q5. Italy deep dive: cities, skills, top-20 companies by postings,
-- remote share
-- ============================================================

-- Q5a. Top cities in Italy
SELECT
    city,
    COUNT(*) AS total_jobs,
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_remote) / COUNT(*), 1) AS pct_remote
FROM jobs
WHERE country = 'it'
GROUP BY city
ORDER BY total_jobs DESC;

-- Q5b. Skill demand within Italy
SELECT
    js.skill,
    COUNT(*) AS n_postings,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM jobs WHERE country = 'it'), 1) AS pct_of_it_postings
FROM job_skills js
JOIN jobs j ON j.id = js.job_id
WHERE j.country = 'it'
GROUP BY js.skill
ORDER BY n_postings DESC;

-- Q5c. Top 20 companies in Italy by number of postings
SELECT
    company,
    COUNT(*) AS n_postings
FROM jobs
WHERE country = 'it' AND company IS NOT NULL
GROUP BY company
ORDER BY n_postings DESC
LIMIT 20;

-- Q5d. Overall remote share in Italy (single figure for README)
SELECT
    ROUND(100.0 * COUNT(*) FILTER (WHERE is_remote) / COUNT(*), 1) AS pct_remote_italy
FROM jobs
WHERE country = 'it';


-- ============================================================
-- Q6. Contract type: full-time vs part-time share per country
-- ============================================================
SELECT
    country,
    contract_time,
    COUNT(*) AS n_postings,
    ROUND(
        100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY country), 1
    ) AS pct_within_country
FROM jobs
WHERE contract_time IS NOT NULL
GROUP BY country, contract_time
ORDER BY country, pct_within_country DESC;


-- ============================================================
-- Power BI exports
-- Run these \copy commands interactively in psql (not via -f with
-- other statements mixed in a script that isn't psql itself), from
-- the project root so relative paths resolve to dashboard/data/.
-- ============================================================

-- pbi_jobs.csv: flat job-level table for Power BI
\copy (SELECT id, title, company, country, city, created, salary_min, salary_max, salary_is_predicted, salary_mid, salary_eur, contract_time, is_junior, is_remote, search_query FROM jobs) TO 'dashboard/pbi_jobs.csv' WITH CSV HEADER

-- pbi_skills_long.csv: long-format job_id/skill/country for Power BI relationships
\copy (SELECT js.job_id, js.skill, j.country FROM job_skills js JOIN jobs j ON j.id = js.job_id) TO 'dashboard/pbi_skills_long.csv' WITH CSV HEADER

-- pbi_salary_by_skill.csv: precomputed skill premium table (same logic as Q4)
\copy (WITH skill_job_ids AS (SELECT DISTINCT skill, job_id FROM job_skills), skill_counts AS (SELECT skill, COUNT(*) AS n FROM skill_job_ids GROUP BY skill HAVING COUNT(*) >= 50), with_skill AS (SELECT sc.skill, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY j.salary_eur) AS median_with_skill, COUNT(*) FILTER (WHERE j.salary_eur IS NOT NULL) AS n_with_salary FROM skill_counts sc JOIN skill_job_ids sji ON sji.skill = sc.skill JOIN jobs j ON j.id = sji.job_id GROUP BY sc.skill), without_skill AS (SELECT sc.skill, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY j.salary_eur) AS median_without_skill FROM skill_counts sc JOIN jobs j ON j.id NOT IN (SELECT job_id FROM skill_job_ids WHERE skill = sc.skill AND job_id IS NOT NULL) GROUP BY sc.skill) SELECT sc.skill, sc.n AS n_postings_with_skill, ws.n_with_salary, ROUND(w.median_with_skill::numeric, 0) AS median_salary_eur_with_skill, ROUND(wo.median_without_skill::numeric, 0) AS median_salary_eur_without_skill, ROUND((w.median_with_skill - wo.median_without_skill)::numeric, 0) AS diff_eur FROM skill_counts sc JOIN with_skill w ON w.skill = sc.skill JOIN without_skill wo ON wo.skill = sc.skill JOIN with_skill ws ON ws.skill = sc.skill ORDER BY diff_eur DESC NULLS LAST) TO 'dashboard/pbi_salary_by_skill.csv' WITH CSV HEADER
