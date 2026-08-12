"""
trend_classification.py
------------------------
Classifies each drug/reaction pair's PRR trajectory across quarters as
'emerging', 'declining', or 'stable' using linear regression of PRR against
quarter index. This is the "signal emergence" half of the project - PRR at
a single point in time tells you the signal is elevated; the slope over
time tells you whether it's getting worse, resolving, or holding steady.

Quarters flagged insufficient_data in signal_scores are excluded from the
regression. A pair needs >=3 usable quarters to receive a real
classification; fewer than that is reported as 'insufficient_data' rather
than a guessed label.

Run:
    python src/trend_classification.py --db data/faers.db
"""

import argparse
import sqlite3

from scipy.stats import linregress

SLOPE_THRESHOLD = 0.1
P_THRESHOLD = 0.05
MIN_QUARTERS = 3


def classify_trend(prr_series: list[float]) -> tuple[str, float, float, float]:
    """Returns (trend_label, slope, p_value, r_value)."""
    if len(prr_series) < MIN_QUARTERS:
        return "insufficient_data", float("nan"), float("nan"), float("nan")

    x = list(range(len(prr_series)))
    slope, intercept, r, p, se = linregress(x, prr_series)

    if slope > SLOPE_THRESHOLD and p < P_THRESHOLD:
        trend = "emerging"
    elif slope < -SLOPE_THRESHOLD and p < P_THRESHOLD:
        trend = "declining"
    else:
        trend = "stable"
    return trend, float(slope), float(p), float(r)


def run(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    pairs = conn.execute(
        "SELECT DISTINCT drug, reaction FROM signal_scores"
    ).fetchall()

    for drug, reaction in pairs:
        rows = conn.execute(
            """
            SELECT quarter, prr FROM signal_scores
            WHERE drug=? AND reaction=? AND insufficient_data=0
            ORDER BY quarter
            """,
            (drug, reaction),
        ).fetchall()

        prr_series = [r[1] for r in rows]
        trend, slope, p, r_val = classify_trend(prr_series)

        conn.execute(
            """
            INSERT INTO trend_classification (drug, reaction, slope, p_value, r_value, n_quarters, trend)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(drug, reaction) DO UPDATE SET
                slope=excluded.slope, p_value=excluded.p_value, r_value=excluded.r_value,
                n_quarters=excluded.n_quarters, trend=excluded.trend
            """,
            (drug, reaction, slope, p, r_val, len(prr_series), trend),
        )
        print(f"{drug:12s} {reaction:28s} n={len(prr_series)}  trend={trend:18s} slope={slope:.3f}")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/faers.db")
    args = parser.parse_args()
    run(args.db)
