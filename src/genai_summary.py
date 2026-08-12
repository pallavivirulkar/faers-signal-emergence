"""
genai_summary.py
------------------
The one bounded GenAI touch in this project: takes computed PRR/ROR/trend
numbers (real, already-validated statistics - this script does no
computation of its own) and asks Claude for a 3-sentence plain-language
summary for a non-technical stakeholder.

No RAG, no agents, no tool use by the model - one prompt, real numbers as
grounding, calling the Anthropic Messages API directly.

Usage:
    export ANTHROPIC_API_KEY=your_key_here
    python src/genai_summary.py --db data/faers.db --reaction "SUICIDAL IDEATION"

If ANTHROPIC_API_KEY is not set, the script prints the exact prompt it
would have sent (a "dry run") instead of fabricating a response - per the
project rule that nothing here is invented, only real fetched/computed
data is used.
"""

import argparse
import os
import sqlite3


def build_prompt(drug: str, reaction: str, prr: float, ci_lower: float, ci_upper: float, trend: str) -> str:
    return (
        f"Given this drug safety signal data:\n"
        f"Drug: {drug}, Reaction: {reaction}, Current PRR: {prr:.2f} "
        f"(95% CI: {ci_lower:.2f}-{ci_upper:.2f}), Trend: {trend}\n\n"
        f"Write a 3-sentence plain-language summary for a non-technical stakeholder. "
        f"Do not use statistical jargon. Do not claim the drug causes the reaction - "
        f"a PRR is a disproportionality signal, not proof of causation."
    )


def get_latest_signal(db_path: str, drug: str, reaction: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT prr, ci_lower, ci_upper FROM signal_scores
        WHERE drug=? AND reaction=? AND insufficient_data=0
        ORDER BY quarter DESC LIMIT 1
        """,
        (drug, reaction),
    ).fetchone()
    trend_row = conn.execute(
        "SELECT trend FROM trend_classification WHERE drug=? AND reaction=?",
        (drug, reaction),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    prr, ci_lower, ci_upper = row
    trend = trend_row[0] if trend_row else "unknown"
    return {"prr": prr, "ci_lower": ci_lower, "ci_upper": ci_upper, "trend": trend}


def summarize(db_path: str, drug: str, reaction: str) -> str:
    signal = get_latest_signal(db_path, drug, reaction)
    if signal is None:
        return f"No computed signal available for {drug} / {reaction} (insufficient data)."

    prompt = build_prompt(drug, reaction, signal["prr"], signal["ci_lower"], signal["ci_upper"], signal["trend"])

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (
            "[DRY RUN - no ANTHROPIC_API_KEY set. Prompt that would be sent:]\n\n"
            + prompt
            + "\n\n[Set ANTHROPIC_API_KEY and re-run to get a real generated summary.]"
        )

    try:
        import anthropic
    except ImportError:
        return "anthropic package not installed. Run: pip install anthropic"

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/faers.db")
    parser.add_argument("--drug", default="semaglutide")
    parser.add_argument("--reaction", required=True)
    args = parser.parse_args()

    print(summarize(args.db, args.drug, args.reaction))
