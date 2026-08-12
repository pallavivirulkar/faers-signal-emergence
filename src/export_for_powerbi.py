"""
export_for_powerbi.py
-----------------------
Dumps the three project tables to CSV in data/exports/ for import into
Power BI Desktop (Week 3 of the project plan). Also writes a wide
`prr_by_quarter.csv` pivot that's convenient for the PRR-over-time line
chart with a PRR=2 reference line.

Run:
    python src/export_for_powerbi.py --db data/faers.db
"""

import argparse
import sqlite3
import csv
import os


def export_table(conn, table: str, out_path: str) -> None:
    cur = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)
    print(f"  {table} -> {out_path} ({len(rows)} rows)")


def export_pivot(conn, out_path: str) -> None:
    rows = conn.execute(
        """
        SELECT reaction, quarter, prr, meets_signal_criteria, insufficient_data
        FROM signal_scores
        ORDER BY reaction, quarter
        """
    ).fetchall()
    with open(out_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["reaction", "quarter", "prr", "meets_signal_criteria", "insufficient_data", "signal_threshold"])
        for reaction, quarter, prr, meets, insufficient in rows:
            writer.writerow([reaction, quarter, prr, meets, insufficient, 2.0])
    print(f"  prr_by_quarter -> {out_path} ({len(rows)} rows)")


def run(db_path: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    conn = sqlite3.connect(db_path)
    print("Exporting Power BI-ready CSVs:")
    export_table(conn, "quarterly_counts", os.path.join(out_dir, "quarterly_counts.csv"))
    export_table(conn, "signal_scores", os.path.join(out_dir, "signal_scores.csv"))
    export_table(conn, "trend_classification", os.path.join(out_dir, "trend_classification.csv"))
    export_pivot(conn, os.path.join(out_dir, "prr_by_quarter.csv"))
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/faers.db")
    parser.add_argument("--out", default="data/exports")
    args = parser.parse_args()
    run(args.db, args.out)
