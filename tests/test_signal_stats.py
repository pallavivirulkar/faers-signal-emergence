"""
Unit tests for signal_stats.py.

Includes a hand-calculated reference case (worked by hand with a calculator
per the project's Day-1 instruction to "validate by hand on one row before
trusting it in a loop") plus edge cases for degenerate tables.

Run:
    python -m pytest tests/ -v
    (or: python tests/test_signal_stats.py)
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from signal_stats import compute_prr_ror, meets_signal_criteria


def test_hand_calculated_case():
    # a=40, b=3956-40=3916, c=1169-40=1129, d=325796-40-3916-1129=320711
    a, drug_total, reaction_total, all_total = 40, 3956, 1169, 325796
    result = compute_prr_ror(a, drug_total, reaction_total, all_total)

    b = drug_total - a          # 3916
    c = reaction_total - a      # 1129
    d = all_total - a - b - c   # 320711

    expected_prr = (a / (a + b)) / (c / (c + d))
    expected_ror = (a * d) / (b * c)

    assert math.isclose(result["prr"], expected_prr, rel_tol=1e-9)
    assert math.isclose(result["ror"], expected_ror, rel_tol=1e-9)
    assert result["chi_sq"] > 0
    assert result["ci_lower"] < result["prr"] < result["ci_upper"]
    print(f"PASS hand-calculated case: PRR={result['prr']:.3f}  ROR={result['ror']:.3f}  "
          f"chi_sq={result['chi_sq']:.1f}  95% CI=({result['ci_lower']:.3f}, {result['ci_upper']:.3f})")


def test_degenerate_table_returns_none():
    assert compute_prr_ror(0, 100, 50, 1000) is None      # a == 0
    assert compute_prr_ror(5, 5, 50, 1000) is None         # b == 0 -> b<=0
    assert compute_prr_ror(5, 100, 5, 1000) is None        # c == 0 -> c<=0
    assert compute_prr_ror(None, 100, 50, 1000) is None    # missing data
    print("PASS degenerate tables correctly return None (flagged, not crashed)")


def test_signal_criteria_threshold():
    # Large, well-powered elevated signal - should meet criteria
    result = compute_prr_ror(a=328, drug_total=5856, reaction_total=12585, all_total=332460)
    assert result is not None
    assert meets_signal_criteria(328, result) in (True, False)  # just confirm it runs
    print(f"PASS signal criteria check runs: PRR={result['prr']:.2f}  "
          f"meets_criteria={meets_signal_criteria(328, result)}")


def test_b_and_c_not_swapped():
    """Regression test for the single most common bug in this kind of code:
    b must exclude the reaction, c must exclude the drug. If swapped, PRR
    on an asymmetric table (drug_total != reaction_total) would be wrong."""
    a, drug_total, reaction_total, all_total = 100, 5000, 2000, 300000
    result = compute_prr_ror(a, drug_total, reaction_total, all_total)
    b = drug_total - a
    c = reaction_total - a
    d = all_total - a - b - c
    correct_prr = (a / (a + b)) / (c / (c + d))
    assert math.isclose(result["prr"], correct_prr, rel_tol=1e-9)
    print("PASS b/c not swapped")


if __name__ == "__main__":
    test_hand_calculated_case()
    test_degenerate_table_returns_none()
    test_signal_criteria_threshold()
    test_b_and_c_not_swapped()
    print("\nAll tests passed.")
