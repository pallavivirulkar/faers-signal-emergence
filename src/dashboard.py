"""
dashboard.py
-------------
Streamlit dashboard for the FAERS Signal Emergence project. Reads straight
from the SQLite database (data/faers.db by default) - no CSV round-trip
needed, though the CSVs in data/exports/ still exist if you want them for
something else (Excel, a different BI tool, etc).

Run:
    streamlit run src/dashboard.py

By default it reads data/faers.db. To point at a different database:
    FAERS_DB=data/faers_semaglutide.db streamlit run src/dashboard.py
"""

import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DB_PATH = os.environ.get("FAERS_DB", "data/faers.db")

st.set_page_config(page_title="FAERS Signal Emergence — Semaglutide", layout="wide")


@st.cache_data
def load_data(db_path: str):
    conn = sqlite3.connect(db_path)
    signal_scores = pd.read_sql("SELECT * FROM signal_scores ORDER BY reaction, quarter", conn)
    quarterly = pd.read_sql("SELECT * FROM quarterly_counts ORDER BY reaction, quarter", conn)
    trend = pd.read_sql("SELECT * FROM trend_classification", conn)
    conn.close()
    return signal_scores, quarterly, trend


if not os.path.exists(DB_PATH):
    st.error(f"Can't find {DB_PATH}. Run the pipeline first (see README) or set FAERS_DB to point at your database.")
    st.stop()

signal_scores, quarterly, trend = load_data(DB_PATH)

st.title("FAERS Signal Emergence — Semaglutide")
st.caption(
    "Real FDA adverse event data via openFDA, 2022 Q1 – 2025 Q4. "
    "PRR/ROR-based disproportionality analysis — a signal here means "
    "'reported more than expected relative to background,' not proof the drug causes it."
)

reactions = sorted(signal_scores["reaction"].unique())
default_idx = reactions.index("SUICIDAL IDEATION") if "SUICIDAL IDEATION" in reactions else 0
selected = st.selectbox("Reaction", reactions, index=default_idx)

df = signal_scores[signal_scores["reaction"] == selected].sort_values("quarter")
usable = df[df["insufficient_data"] == 0]

trend_row = trend[trend["reaction"] == selected]
trend_label = trend_row["trend"].values[0] if len(trend_row) else "unknown"
slope = trend_row["slope"].values[0] if len(trend_row) else None
p_value = trend_row["p_value"].values[0] if len(trend_row) else None

latest = usable.tail(1)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Current PRR", f"{latest['prr'].values[0]:.2f}" if len(latest) else "n/a")
col2.metric("Trend", trend_label)
col3.metric("Latest quarter case count (a)", int(latest["a_count"].values[0]) if len(latest) else "n/a")
col4.metric("Quarters with usable data", f"{len(usable)} / {len(df)}")

if slope is not None and not pd.isna(p_value):
    st.caption(f"Regression: slope = {slope:.3f}, p = {p_value:.4f} (n = {len(usable)} quarters used)")

# --- PRR over time chart ---
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=usable["quarter"], y=usable["prr"], mode="lines+markers", name="PRR",
    line=dict(color="#5b8def", width=3), marker=dict(size=8),
))
fig.add_hline(y=2, line_dash="dash", line_color="crimson", annotation_text="Signal threshold (PRR = 2)")
fig.update_layout(
    title=f"PRR over time — {selected}",
    xaxis_title="Quarter", yaxis_title="PRR",
    height=420,
)
st.plotly_chart(fig, use_container_width=True)

# --- Narrative callouts on the two externally-validated signals ---
CALLOUTS = {
    "SUICIDAL IDEATION": (
        "**Real-world context:** EMA (Apr 2024) and FDA (2026) both reviewed this and concluded "
        "there wasn't a causal link, and FDA asked for the warning to be removed from GLP-1 labels. "
        "This dataset shows the signal rising through 2023, then fading below background by late 2025 — "
        "consistent with that conclusion."
    ),
    "OPTIC ISCHAEMIC NEUROPATHY": (
        "**Real-world context:** absent from FAERS reporting until mid-2024, then climbing fast right "
        "as the EMA opened a formal NAION safety review in January 2025 — a review that later resulted "
        "in a label update."
    ),
}
if selected in CALLOUTS:
    st.info(CALLOUTS[selected])

with st.expander("Raw quarterly numbers for this reaction"):
    st.dataframe(
        df[["quarter", "a_count", "prr", "ror", "chi_sq", "ci_lower", "ci_upper",
            "meets_signal_criteria", "insufficient_data"]],
        use_container_width=True, hide_index=True,
    )

# --- Overview across all tracked reactions ---
st.subheader("All tracked reactions")
st.dataframe(
    trend[["reaction", "trend", "slope", "p_value", "n_quarters"]].sort_values("trend"),
    use_container_width=True, hide_index=True,
)

st.subheader("PRR over time — all reactions compared")
fig2 = go.Figure()
for r in reactions:
    sub = signal_scores[(signal_scores["reaction"] == r) & (signal_scores["insufficient_data"] == 0)].sort_values("quarter")
    fig2.add_trace(go.Scatter(x=sub["quarter"], y=sub["prr"], mode="lines+markers", name=r))
fig2.add_hline(y=2, line_dash="dash", line_color="crimson", annotation_text="Signal threshold (PRR = 2)")
fig2.update_layout(xaxis_title="Quarter", yaxis_title="PRR", height=480)
st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "Data: openFDA FAERS · Not for clinical decision-making · Duplicate reports, reporting bias, "
    "and small-count instability are not corrected for — see docs/methodology.md."
)
