"""
db_schema.py
------------
Creates the SQLite schema for the FAERS signal-emergence project.

Two tables:
  quarterly_counts  - raw 2x2-contingency-table inputs per drug/reaction/quarter
  signal_scores     - PRR/ROR/chi-square/CI + trend classification, derived
                       from quarterly_counts by signal_stats.py / trend_classification.py

Run directly to (re)create an empty database:
    python src/db_schema.py --db data/faers.db
"""

import argparse
import sqlite3


def create_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quarterly_counts (
            drug            TEXT NOT NULL,
            reaction        TEXT NOT NULL,
            quarter         TEXT NOT NULL,   -- 'YYYYQn'
            a_count         INTEGER,         -- reports: this drug + this reaction, this quarter
            drug_total      INTEGER,         -- reports: this drug, any reaction, this quarter
            reaction_total  INTEGER,         -- reports: any drug, this reaction, this quarter
            all_total       INTEGER,         -- reports: any drug, any reaction, this quarter (background)
            source          TEXT DEFAULT 'openfda_live',  -- 'openfda_live' | 'openfda_alltime_fallback'
            fetched_at      TEXT,            -- ISO timestamp the row was pulled
            PRIMARY KEY (drug, reaction, quarter)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_scores (
            drug            TEXT NOT NULL,
            reaction        TEXT NOT NULL,
            quarter         TEXT NOT NULL,
            a_count         INTEGER,
            prr             REAL,
            ror             REAL,
            chi_sq          REAL,
            ci_lower        REAL,
            ci_upper        REAL,
            meets_signal_criteria INTEGER,   -- 1/0: PRR>=2 AND chi_sq>=4 AND a>=3
            insufficient_data     INTEGER,   -- 1/0: flagged rather than computed
            PRIMARY KEY (drug, reaction, quarter),
            FOREIGN KEY (drug, reaction, quarter)
                REFERENCES quarterly_counts(drug, reaction, quarter)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS trend_classification (
            drug         TEXT NOT NULL,
            reaction     TEXT NOT NULL,
            slope        REAL,
            p_value      REAL,
            r_value      REAL,
            n_quarters   INTEGER,
            trend        TEXT,   -- 'emerging' | 'declining' | 'stable' | 'insufficient_data'
            PRIMARY KEY (drug, reaction)
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/faers.db")
    args = parser.parse_args()
    create_schema(args.db)
    print(f"Schema created/verified at {args.db}")
