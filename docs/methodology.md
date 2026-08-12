# Methodology

## 1. Data source

[openFDA Drug Adverse Event API](https://open.fda.gov/apis/drug/event/how-to-use-the-endpoint/) (`/drug/event.json`), which mirrors FDA FAERS (FDA Adverse Event Reporting System) spontaneous-report data. Counts are pulled server-side via openFDA's `count` parameter rather than downloading raw records, per the project's data strategy.

**Drug filter:** `patient.drug.openfda.generic_name:"semaglutide"`, not `patient.drug.medicinalproduct`. openFDA normalizes brand names (Ozempic, Wegovy, Rybelsus) into a single `generic_name` field; filtering on the raw `medicinalproduct` string alone captures only reports where "SEMAGLUTIDE" was typed verbatim and **under-counts by roughly 10x** (verified: 1,075 vs. 10,674 all-time NAUSEA reports for the two filters respectively). This is a real trap in this dataset worth documenting for anyone extending the project.

## 2. Tracked reactions

Five reactions were selected, deliberately combining both approaches described in the original project brief ("pick 3-5 that look clinically interesting"):

| Reaction | Why it was chosen |
|---|---|
| NAUSEA | High-frequency background GI effect - a stability/sanity-check baseline |
| PANCREATITIS | Classic incretin-class (GLP-1) signal with a long regulatory history |
| IMPAIRED GASTRIC EMPTYING | Real MedDRA term underlying the "gastroparesis" concern raised in 2023-2024 case reports/litigation |
| SUICIDAL IDEATION | Real FAERS-driven regulatory signal: reviewed by EMA (started Jul 2023, concluded Apr 2024, no causal link found) and reviewed again by FDA in 2026, which requested removal of the warning label |
| OPTIC ISCHAEMIC NEUROPATHY | Real MedDRA term for NAION (non-arteritic anterior ischemic optic neuropathy) - EMA opened a formal review in Jan 2025 and recommended a "very rare" label update in mid-2025 |

The last two give this project a genuine external-validation opportunity (Week 2, Day 4): one signal that was investigated and did **not** hold up (suicidal ideation), and one that was investigated and **did** get a label update (NAION) - a realistic contrast most demo projects don't have.

## 3. Disproportionality statistics

Each drug/reaction/quarter cell is a 2x2 contingency table:

| | This reaction | All other reactions |
|---|---|---|
| **This drug** | a | b |
| **All other drugs** | c | d |

- `a` = reports mentioning semaglutide AND the reaction, this quarter
- `b` = `drug_total - a` (semaglutide, some other reaction)
- `c` = `reaction_total - a` (the reaction, some other drug)
- `d` = `all_total - a - b - c` (neither)

**PRR** (Proportional Reporting Ratio) = `(a/(a+b)) / (c/(c+d))`
**ROR** (Reporting Odds Ratio) = `(a*d) / (b*c)`
**Chi-square** (Yates-uncorrected 2x2) = `((ad-bc)^2 * (a+b+c+d)) / ((a+b)(c+d)(a+c)(b+d))`
**95% CI on PRR** = `exp(ln(PRR) ± 1.96 * SE)`, where `SE = sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))`

**Signal criteria** (standard pharmacovigilance thresholds - Evans, Waller & Davis 2001): a cell is flagged as a candidate signal if `PRR >= 2 AND chi_sq >= 4 AND a >= 3`. Cells with degenerate tables (`a=0` or any of `b,c,d <= 0`) are stored as `insufficient_data` rather than silently skipped or coerced to a number - see `signal_stats.compute_prr_ror()`.

## 4. Trend / emergence classification

For each drug/reaction pair, PRR values across quarters (excluding any flagged `insufficient_data`) are regressed against quarter index using `scipy.stats.linregress`. A pair needs **at least 3 usable quarters** to receive a real label; fewer than that is reported as `insufficient_data`.

- `slope > 0.1 and p < 0.05` -> **emerging**
- `slope < -0.1 and p < 0.05` -> **declining**
- otherwise -> **stable**

This threshold is intentionally conservative: with few quarters of data, statistical power to detect a slope is low, so a real early-stage emergence can legitimately classify as "stable" even while the raw PRR is visibly climbing. `OPTIC ISCHAEMIC NEUROPATHY` is the clearest example in this dataset - see the findings memo.

## 5. Data provenance

Every number in `data/faers.db` came from a live call to `api.fda.gov` using `src/extract.py`, run locally with a real `OPENFDA_API_KEY` on 2026-08-11, covering the full 16-quarter window the project was originally scoped for (2022 Q1 - 2025 Q4, all 5 reactions, 80 drug/reaction/quarter cells). Nothing in this database is estimated, interpolated, or fabricated.

An earlier, smaller build of this project (kept around at `data/faers_semaglutide.db` for reference / quick exploration without an API key) only had 4 quarters and, for 2 of the 5 reactions, used an all-time background rate as a stand-in for the same-quarter one - a limitation of the environment that first pipeline was built in, not of the extraction logic itself. Once `extract.py` ran against the real API with a real key, every single cell came back `source='openfda_live'` - the fallback path in the code exists as a safety net (see `extract.py`'s `get_reaction_total()`) but wasn't needed for the real run. Worth knowing if you're comparing old numbers you may have seen against this version: PRR for `IMPAIRED GASTRIC EMPTYING` and `OPTIC ISCHAEMIC NEUROPATHY` came out substantially higher with the correct same-quarter denominator than the earlier approximation suggested - see the findings memo.

A handful of cells (mostly `OPTIC ISCHAEMIC NEUROPATHY` in 2022-2023, where `a_count = 0`) are stored as `insufficient_data` rather than computed, per the degenerate-table rule in `signal_stats.compute_prr_ror()`.

## 6. Known data-quality limitations (apply to any FAERS analysis, not just this one)

- **Duplicate reports.** FAERS is known to contain duplicate submissions of the same case (e.g., initial + follow-up reports, or the same event reported by both a patient and a physician). No deduplication is applied here; counts reflect raw report volume, not unique patients.
- **Reporting bias / stimulated reporting.** A spike in reports for a reaction can reflect media attention or litigation (e.g., NAION coverage, GLP-1 lawsuits) rather than a true change in incidence - PRR measures *disproportionate reporting*, not risk.
- **No causal inference.** PRR/ROR are hypothesis-generating signal-detection tools, not epidemiological risk estimates. A high PRR means "this reaction is reported disproportionately often for this drug relative to background" - it does not mean the drug causes the reaction.
- **Small-count instability.** Early/low-volume quarters can produce large, unstable PRR swings from just 2-3 case reports. The `a >= 3` signal criterion mitigates this but does not eliminate it - always check `a_count` alongside PRR before treating a flagged cell as meaningful.
- **Quarterly reporting isn't smooth.** Real FAERS submission volume varies quarter to quarter for administrative reasons, not just true event rates. This dataset has one clear example: 2025 Q3's `drug_total` (11,814) is roughly 2-4x every neighboring quarter, and every tracked reaction shows an unusually large `a_count` that same quarter (e.g. NAUSEA jumps to 2,018 from ~300 the quarter before and after). That's very likely a reporting/processing backlog hitting the database all at once, not semaglutide usage actually quadrupling for three months - worth flagging rather than reading into it.
