# FAERS Signal Emergence: Semaglutide — Findings Memo

**Author:** Pallavi Virulkar · **Date:** August 11, 2026
**Data:** openFDA / FDA FAERS, live-pulled, 2022 Q1 – 2025 Q4 (16 quarters) · **Drug:** semaglutide (Ozempic/Wegovy/Rybelsus)

## Problem

Raw adverse-event counts don't mean much on their own - a widely used drug racks up more reports than a rare one simply from volume. Disproportionality analysis (PRR/ROR) corrects for that by comparing how often a reaction is reported for a given drug against how often it's reported in the background, across all drugs. This project pulls four years of real FAERS data via openFDA, computes PRR/ROR/chi-square per quarter for five tracked reactions, and classifies each one's trajectory as emerging, declining, or stable - turning a snapshot into something closer to an early-warning signal.

## Method

The full 16-quarter window (2022 Q1 - 2025 Q4) was pulled live from openFDA for semaglutide across five reactions, picked to mix a stability baseline, a long-recognized drug-class signal, and two reactions with real, checkable regulatory histories (rationale for each in `docs/methodology.md`). PRR, ROR, chi-square, and 95% CI were computed per drug/reaction/quarter cell (80 cells total); a cell is flagged a candidate signal at `PRR ≥ 2, chi-sq ≥ 4, a ≥ 3`. Trend was classified via linear regression of PRR against quarter index, requiring at least 3 usable quarters.

## Findings

**Impaired gastric emptying is the strongest, most unambiguous signal in this dataset, and it's still climbing.** This is the MedDRA term underlying most of the "gastroparesis" concern around GLP-1 drugs. PRR opens at an already-elevated 18.97 in 2022 Q1, and by 2025 it's routinely sitting between 55 and 145 - the single highest reading is 145.45 in 2025 Q1. Every one of the 15 computable quarters clears the signal threshold, and the regression is unambiguous: slope +6.15, p = 0.003. This reaction is formally classified **emerging**, and honestly the label undersells it a little - it was never really weak to begin with, and it's gotten dramatically stronger.

**Pancreatitis is elevated in every quarter but reliably declining.** PRR starts at 9.84 in 2022 Q1 and works its way down to 2.17 by 2025 Q4 - still crossing the signal threshold the whole way, but the direction is consistent and statistically clear (slope -0.39, p = 0.0001). Pancreatitis has been watched in the GLP-1 class since exenatide's approval two decades ago; this reads as a persistent, well-known, but not worsening signal.

**Suicidal ideation tells a real story about a signal that rose, peaked, and faded - matching what regulators actually found.** PRR bounces around in 2022 (as low as 1.07), climbs through 2023 (peaking at 9.71 in Q4 2023), stays moderately elevated through most of 2024, then drops off in 2025 - falling *below* 1.0 in Q3 2025 (0.53), meaning by late 2025 semaglutide reports of suicidal ideation were actually *underrepresented* relative to background. This timeline lines up closely with what really happened: case reports out of Iceland prompted an EMA review starting mid-2023, the EMA concluded in April 2024 that the evidence (including large EHR-based studies) didn't support a causal link, and the FDA's own 2026 review - a meta-analysis of 91 trials covering over 100,000 patients plus a 2.2M-patient cohort study - found no increased risk and asked for the warning to be removed from labels entirely. The FAERS signal was real in the sense that people really were reporting it more; it just didn't hold up as a genuine drug effect once it was properly studied. That gap between "elevated in spontaneous reports" and "confirmed under epidemiological review" is arguably the most useful thing this project demonstrates.

**Optic ischaemic neuropathy (NAION) doesn't show up at all until mid-2024 - and then it's enormous.** For 2022 through early 2024, `a_count` is 0 every single quarter (correctly stored as insufficient data, not estimated as zero-risk). Then in 2024 Q2 it appears with a_count=3 and PRR=20.9, and from there it basically never comes back down: 28.5, 85.4, 113.1, 81.7, 29.4, 134.7 through the rest of 2024 and 2025, peaking at 134.74 in the final quarter of the dataset. The regression labels this "stable" rather than "emerging," which looks odd until you check why: only 7 of the 16 quarters have enough data to regress on (the rest are the zero-report early quarters, correctly excluded), and a slope of 12+ on 7 points doesn't clear the p<0.05 bar even though the visual trend is obvious. This is a real limitation of a fairly short, mostly-empty-then-suddenly-active series, not a wrong answer. And critically, the real-world timeline matches: the EMA opened a formal safety review into semaglutide and NAION in January 2025 - right in the middle of this reaction's climb - and that review concluded with a label update recommending NAION be listed as a very rare side effect.

**Nausea is exactly the flat, elevated baseline you'd expect from a labeled, well-known side effect.** PRR moves in a 3-7 range across all 16 quarters with no real trend (slope -0.06, p = 0.27) and by far the largest sample sizes of anything tracked - useful mainly as confirmation the pipeline produces sane numbers when nothing unusual is happening.

## External validation (Week 2, Day 4 requirement)

Two of the five tracked reactions have real, checkable regulatory outcomes, and both are consistent with the direction this data shows:

- **Suicidal ideation** - FAERS reporting rose sharply through 2023, matching the period regulators were actively investigating it. EMA (Apr 2024) and FDA (2026) both concluded no causal link and asked for the warning to be removed. This dataset shows the signal fading right alongside that timeline, down to below-background by late 2025.
- **NAION (optic ischaemic neuropathy)** - absent from FAERS reporting until mid-2024, then rising fast through exactly the window the EMA opened its formal review (Jan 2025) and later added a label warning. Unlike suicidal ideation, this one held up.

Having one signal that panned out and one that didn't, both traceable to real regulatory decisions, is a genuinely useful pair of case studies for what PRR can and can't tell you on its own.

## Limitations

FAERS contains duplicate case reports (no deduplication was applied); PRR measures disproportionate reporting, not incidence or causation; and 2025 Q3 shows a clear reporting-volume anomaly (drug_total roughly 2-4x every neighboring quarter, likely a backlog of reports processed together rather than a real usage spike) that's worth keeping in mind when reading that specific quarter's numbers. Full detail in `docs/methodology.md` §6.

## What I'd do with more time

Add a second drug in the same class (tirzepatide is the obvious candidate) to see whether impaired gastric emptying and NAION show the same pattern class-wide or are specific to semaglutide. I'd also dig into why 2025 Q3 looks like a reporting-volume outlier - worth checking whether that's an openFDA indexing artifact or a real FAERS submission-batch effect. And now that the full series is in, it'd be worth re-running the trend classifier with a shorter minimum-quarter threshold for NAION specifically, since the standard 3-quarter rule works fine for the other four reactions but slightly understates how strong this particular signal already is.
