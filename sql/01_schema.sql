-- Schema for eu_jobs database.
-- Run once against the target database, or let transform_jobs.py
-- create tables via pandas.to_sql (replace) — this file documents
-- the intended structure and adds indexes pandas won't create.

CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT PRIMARY KEY,
    title               TEXT,
    company             TEXT,
    country             TEXT,
    city                TEXT,
    created             DATE,
    description         TEXT,
    salary_min          NUMERIC,
    salary_max          NUMERIC,
    salary_is_predicted BOOLEAN,
    contract_time       TEXT,
    url                 TEXT,
    search_query         TEXT,
    salary_mid          NUMERIC,
    salary_eur          NUMERIC,
    is_junior           BOOLEAN,
    is_remote           BOOLEAN
);

CREATE TABLE IF NOT EXISTS job_skills (
    job_id  TEXT REFERENCES jobs(id),
    skill   TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_country ON jobs(country);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill);
