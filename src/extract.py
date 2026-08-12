"""
extract.py
----------
Full openFDA extraction pipeline for the FAERS Signal Emergence project.

Pulls, per quarter, for each tracked reaction:
    a_count        = drug AND reaction AND quarter
    drug_total     = drug AND quarter (any reaction)
    reaction_total = reaction AND quarter (any drug)
    all_total      = quarter (any drug, any reaction) - background rate

...and writes them into quarterly_counts.

Usage:
    export OPENFDA_API_KEY=your_key_here     # optional but strongly recommended
    python src/extract.py --db data/faers.db --start 2022-01-01 --end 2025-12-31

Design notes (read before changing the query logic):
  - Drug filter uses openfda.generic_name, NOT medicinalproduct, because
    generic_name normalizes brand names (Ozempic/Wegovy/Rybelsus) to
    "semaglutide" - using medicinalproduct alone under-counts by ~10x since
    most FAERS reporters use the brand name as-submitted.
  - 'a_count' for ALL tracked reactions in a quarter is fetched in a single
    call via get_reaction_breakdown() (count=reactionmeddrapt.exact) rather
    than one call per reaction - this cuts API calls by ~5x.
  - drug_total / all_total use get_count(), which sums the two `serious`
    buckets instead of paging through raw records - keeps responses small.
  - reaction_total (any drug, this reaction, this quarter) requires
    reactionmeddrapt as a search FILTER (not just a count-by field). Some
    multi-word MedDRA terms are rare enough, combined with a same-quarter
    filter, that they returned zero rows in ad hoc testing against very
    large date-range + term combinations. If a reaction_total query comes
    back empty, this script automatically falls back to the reaction's
    ALL-TIME (any-drug, no date filter) total and flags the row's `source`
    column as 'openfda_alltime_fallback' so downstream analysis can see
    exactly which cells used the approximation. This is a documented
    limitation, not a silent guess - see docs/methodology.md.
"""

import argparse
import datetime as dt
import sqlite3
import sys

from openfda_client import (
    OpenFDAClient,
    build_date_filter,
    build_drug_filter,
    generate_quarter_ranges,
)

DEFAULT_REACTIONS = [
    "NAUSEA",
    "PANCREATITIS",
    "IMPAIRED GASTRIC EMPTYING",
    "SUICIDAL IDEATION",
    "OPTIC ISCHAEMIC NEUROPATHY",
]


def get_reaction_total(client: OpenFDAClient, reaction: str, date_filter: str) -> tuple[int | None, str]:
    """Any-drug, this-reaction, this-quarter total. Falls back to the
    reaction's all-time total (source flagged) if the quarter-scoped query
    returns nothing usable."""
    search = f'patient.reaction.reactionmeddrapt:"{reaction}" AND {date_filter}'
    try:
        total = client.get_count(search)
        if total > 0:
            return total, "openfda_live"
    except Exception:
        pass
    # Fallback: all-time, any-drug total for this reaction (no date filter)
    try:
        fallback = client.get_count(f'patient.reaction.reactionmeddrapt:"{reaction}"')
        return fallback, "openfda_alltime_fallback"
    except Exception:
        return None, "unavailable"


def extract(db_path: str, start: str, end: str, drug: str, reactions: list[str], api_key: str | None):
    client = OpenFDAClient(api_key=api_key)
    conn = sqlite3.connect(db_path)

    drug_filter = build_drug_filter(drug)
    quarters = generate_quarter_ranges(start, end)
    print(f"Extracting {len(quarters)} quarters x {len(reactions)} reactions for {drug} ...")

    for q_start, q_end, label in quarters:
        date_filter = build_date_filter(q_start, q_end)
        print(f"  {label} ({q_start}-{q_end})")

        # 1 call: a_count for every reaction this quarter, for this drug
        breakdown = client.get_reaction_breakdown(f"{drug_filter} AND {date_filter}", limit=500)

        # 1 call: drug_total (this drug, any reaction, this quarter)
        drug_total = client.get_count(f"{drug_filter} AND {date_filter}")

        # 1 call: all_total (any drug, any reaction, this quarter - background)
        all_total = client.get_count(date_filter)

        for reaction in reactions:
            a_count = breakdown.get(reaction, 0)
            reaction_total, source = get_reaction_total(client, reaction, date_filter)

            conn.execute(
                """
                INSERT INTO quarterly_counts
                    (drug, reaction, quarter, a_count, drug_total, reaction_total, all_total, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(drug, reaction, quarter) DO UPDATE SET
                    a_count=excluded.a_count,
                    drug_total=excluded.drug_total,
                    reaction_total=excluded.reaction_total,
                    all_total=excluded.all_total,
                    source=excluded.source,
                    fetched_at=excluded.fetched_at
                """,
                (drug, reaction, label, a_count, drug_total, reaction_total, all_total,
                 source, dt.datetime.utcnow().isoformat()),
            )
            print(f"      {reaction:30s} a={a_count:>6}  drug_total={drug_total:>7}  "
                  f"reaction_total={reaction_total}  ({source})")
        conn.commit()

    conn.close()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/faers.db")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--drug", default="semaglutide")
    parser.add_argument("--reactions", nargs="*", default=DEFAULT_REACTIONS)
    parser.add_argument("--api-key", default=None, help="or set OPENFDA_API_KEY env var")
    args = parser.parse_args()

    extract(args.db, args.start, args.end, args.drug, args.reactions, args.api_key)
