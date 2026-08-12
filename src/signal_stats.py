"""
signal_stats.py
----------------
Disproportionality analysis: PRR, ROR, chi-square, and 95% CI on the PRR,
computed from a 2x2 contingency table per drug/reaction/quarter.

                        This reaction   All other reactions
    This drug                a                  b
    All other drugs           c                  d

    a = a_count            (drug AND reaction)
    b = drug_total - a      (drug, NOT this reaction)
    c = reaction_total - a  (reaction, NOT this drug)
    d = all_total - a - b - c   (neither)

Signal criteria (standard pharmacovigilance thresholds, e.g. Evans et al.
2001 for PRR-based signal detection):
    PRR >= 2 AND chi_sq >= 4 AND a >= 3

Run:
    python src/signal_stats.py --db data/faers.db
"""

import argparse
import sqlite3

import numpy as np


def compute_prr_ror(a, drug_total, reaction_total, all_total):
    """Returns a dict of prr/ror/chi_sq/ci_lower/ci_upper, or None if the
    2x2 table is degenerate (any cell <= 0) - i.e. not enough data to
    compute a stable estimate this quarter. Callers should store this as
    'insufficient_data' rather than skipping the row silently."""
    if a is None or drug_total is None or reaction_total is None or all_total is None:
        return None

    b = drug_total - a
    c = reaction_total - a
    d = all_total - a - b - c

    if a == 0 or b <= 0 or c <= 0 or d <= 0:
        return None

    prr = (a / (a + b)) / (c / (c + d))
    ror = (a * d) / (b * c)
    chi_sq = ((a * d - b * c) ** 2 * (a + b + c + d)) / ((a + b) * (c + d) * (a + c) * (b + d))

    se_log_prr = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
    ci_lower = float(np.exp(np.log(prr) - 1.96 * se_log_prr))
    ci_upper = float(np.exp(np.log(prr) + 1.96 * se_log_prr))

    return {
        "prr": float(prr),
        "ror": float(ror),
        "chi_sq": float(chi_sq),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }


def meets_signal_criteria(a, result) -> bool:
    if result is None:
        return False
    return result["prr"] >= 2 and result["chi_sq"] >= 4 and a >= 3


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT drug, reaction, quarter, a_count, drug_total, reaction_total, all_total FROM quarterly_counts"
    ).fetchall()

    n_computed, n_flagged = 0, 0
    for drug, reaction, quarter, a, drug_total, reaction_total, all_total in rows:
        result = compute_prr_ror(a, drug_total, reaction_total, all_total)

        if result is None:
            conn.execute(
                """
                INSERT INTO signal_scores (drug, reaction, quarter, a_count, prr, ror, chi_sq,
                    ci_lower, ci_upper, meets_signal_criteria, insufficient_data)
                VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, 0, 1)
                ON CONFLICT(drug, reaction, quarter) DO UPDATE SET
                    a_count=excluded.a_count, prr=NULL, ror=NULL, chi_sq=NULL,
                    ci_lower=NULL, ci_upper=NULL, meets_signal_criteria=0, insufficient_data=1
                """,
                (drug, reaction, quarter, a),
            )
            n_flagged += 1
        else:
            signal = meets_signal_criteria(a, result)
            conn.execute(
                """
                INSERT INTO signal_scores (drug, reaction, quarter, a_count, prr, ror, chi_sq,
                    ci_lower, ci_upper, meets_signal_criteria, insufficient_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(drug, reaction, quarter) DO UPDATE SET
                    a_count=excluded.a_count, prr=excluded.prr, ror=excluded.ror,
                    chi_sq=excluded.chi_sq, ci_lower=excluded.ci_lower, ci_upper=excluded.ci_upper,
                    meets_signal_criteria=excluded.meets_signal_criteria, insufficient_data=0
                """,
                (drug, reaction, quarter, a, result["prr"], result["ror"], result["chi_sq"],
                 result["ci_lower"], result["ci_upper"], int(signal)),
            )
            n_computed += 1

    conn.commit()
    conn.close()
    print(f"signal_scores: {n_computed} computed, {n_flagged} flagged insufficient_data.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/faers.db")
    args = parser.parse_args()
    run(args.db)
