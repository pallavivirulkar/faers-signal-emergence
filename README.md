# FAERS Signal Emergence — Semaglutide

This is a pharmacovigilance project I built around semaglutide (Ozempic/Wegovy/Rybelsus) using real FDA adverse event data from openFDA. The idea: raw adverse event counts don't tell you much on their own, because a popular drug will rack up more reports than a rare one just from volume. So instead I calculate PRR and ROR (basically, "is this reaction reported more often for this drug than you'd expect from background rates") per quarter, and then track how that number moves over time to see whether a signal is actually emerging, holding steady, or fading.

Check `PROJECT_STATUS.md` for the honest, up-to-date state of things — what's done, what's still on you.

## Why it's built this way

`extract.py` hits the openFDA API and pulls counts into SQLite. `signal_stats.py` turns those counts into PRR/ROR/chi-square/confidence intervals for each drug-reaction-quarter combo. `trend_classification.py` runs a linear regression on the PRR series per reaction to label it emerging/declining/stable. From there it's export (CSV for Power BI) and one optional GenAI call that turns a signal's numbers into a plain-English sentence a non-technical person could read.

Nothing fancy — no RAG, no agentic stuff for the GenAI part, just numbers in, one prompt, text out.

## Getting set up

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You'll want a free openFDA key (bumps your limit from 1,000 requests/day to 120,000) — takes about 2 minutes: https://open.fda.gov/apis/authentication

```bash
export OPENFDA_API_KEY=your_key_here
export ANTHROPIC_API_KEY=your_key_here   # only needed if you want genai_summary.py to actually call the model
```

## Running it

`data/faers.db` already has the full real dataset in it — the complete 2022 Q1 through 2025 Q4 window (16 quarters, 5 reactions, 80 drug/reaction/quarter cells), pulled live from openFDA. You can go straight to the stats:

```bash
python src/signal_stats.py --db data/faers.db
python src/trend_classification.py --db data/faers.db
python src/export_for_powerbi.py --db data/faers.db
```

To reproduce it from scratch (needs your own `OPENFDA_API_KEY`, takes 10-15 minutes since openFDA rate-limits requests):

```bash
python src/db_schema.py --db data/faers.db
python src/extract.py --db data/faers.db --start 2022-01-01 --end 2025-12-31
python src/signal_stats.py --db data/faers.db
python src/trend_classification.py --db data/faers.db
python src/export_for_powerbi.py --db data/faers.db
```

There's also a smaller `data/faers_semaglutide.db` sitting around from an earlier pass at this (just 4 quarters) — keeping it as a quick-look reference, but `data/faers.db` is the real, complete dataset and what everything else in this repo is based on.

Launch the dashboard (reaction selector, PRR-over-time chart with a signal-threshold line, KPI cards, narrative callouts on the two externally-validated signals, and an all-reactions comparison view):

```bash
streamlit run src/dashboard.py
```

Opens at `http://localhost:8501`. To point it at a different database: `FAERS_DB=data/faers_semaglutide.db streamlit run src/dashboard.py`.

Get a plain-language summary for any tracked reaction:

```bash
python src/genai_summary.py --db data/faers.db --reaction "OPTIC ISCHAEMIC NEUROPATHY"
```

Tests:

```bash
python -m pytest tests/ -v
```

## What the real data actually shows

Nausea sits at a stable PRR in the 3-7 range across all 16 quarters, with no real trend — exactly what you'd expect from a well-known, already-labeled side effect. Good sanity check that the pipeline isn't producing garbage.

Pancreatitis is elevated the entire time (PRR never drops below 2) but consistently declining — from 9.84 in early 2022 down to 2.17 by the end of 2025. A long-recognized GLP-1-class signal that isn't getting worse.

Impaired gastric emptying — the actual MedDRA term behind most of the "gastroparesis" headlines — turned out to be the strongest signal in the whole dataset once I had the real numbers, not the weak one I thought it was from an earlier partial run. PRR opens already high (almost 19 in 2022 Q1) and by 2025 is regularly sitting between 55 and 145. Every computable quarter clears the signal threshold, and it's still trending up.

Suicidal ideation is the one I'd point to as the most interesting story. PRR climbs through 2023, peaks near 9.7 at the end of that year, then fades through 2024-2025, actually dropping *below* background (PRR 0.53) by Q3 2025. That timeline lines up almost exactly with what really happened — EMA investigated this starting mid-2023 and concluded in April 2024 there wasn't a causal link; FDA reached the same conclusion in 2026 and asked for the warning to be removed from labels. The FAERS signal was real in that people really did report it more — it just didn't hold up once it was properly studied.

Optic ischaemic neuropathy (NAION) doesn't show up at all until mid-2024 — zero reports every quarter before that — and then jumps to PRR values in the 20-135 range and stays there through 2025. The trend classifier still calls this "stable" rather than "emerging" because only 7 of 16 quarters have any data to regress on, which isn't enough to hit statistical significance even though the pattern is obvious looking at the raw numbers. And this lines up with reality too: the EMA opened a formal review into semaglutide and NAION in January 2025, right as this reaction was climbing, and it ended in a label update.

Full writeup: `docs/findings_memo.md`. Methodology, thresholds, and data caveats: `docs/methodology.md`.

## Project layout

```
faers-signal-analysis/
├── README.md
├── PROJECT_STATUS.md
├── requirements.txt
├── progress-tracker.html        open this in a browser, checkbox-driven progress view
├── data/
│   ├── faers.db                 the real, complete dataset (2022 Q1 - 2025 Q4)
│   ├── faers_semaglutide.db     earlier 4-quarter reference build
│   └── exports/                 CSVs for Power BI
├── src/
│   ├── openfda_client.py
│   ├── db_schema.py
│   ├── extract.py
│   ├── seed_real_data.py
│   ├── signal_stats.py
│   ├── trend_classification.py
│   ├── export_for_powerbi.py
│   ├── dashboard.py            streamlit run src/dashboard.py
│   └── genai_summary.py
├── docs/
│   ├── methodology.md
│   └── findings_memo.md
└── tests/
    └── test_signal_stats.py
```

## Stack

Python 3.10+, requests, pandas, numpy, scipy, sqlite3 (stdlib), anthropic (for the GenAI bit), streamlit + plotly (for the dashboard). Data comes from [openFDA](https://open.fda.gov/apis/drug/event/how-to-use-the-endpoint/).

(Originally scoped as a Power BI dashboard — switched to Streamlit since it's plain Python, easier to actually test before shipping, and a deployed Streamlit app is something a recruiter can open in a browser without needing Power BI Desktop installed.)
