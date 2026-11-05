"""Small synthetic checks for time-aware Round-3 decomposition."""
import json

import numpy as np
import pandas as pd
import pytest

from ppg_forward.tf_statistics import (
    _bartlett_hac, _shift_residuals, decompose_feature,
)


def _data(n_cases=6, n=36):
    rng = np.random.default_rng(72)
    rows = []
    for case in range(n_cases):
        t = np.arange(n) * 120.
        map_values = 80 + 8*rng.normal(size=n)
        hr = 65 + 5*rng.normal(size=n)
        response = (3*case + (.04 + .005*case)*(map_values-map_values.mean())
                    + (-.03 + .002*case)*(hr-hr.mean())
                    + .2*(t-t.mean())/3600 + rng.normal(0, .001, n))
        rows.extend(dict(caseid=case, timestamp_s=timestamp,
            map_mmHg=pressure, hr_bpm=rate, response=value)
            for timestamp, pressure, rate, value in zip(t, map_values, hr, response))
    return pd.DataFrame(rows)


def _decompose(data, **kwargs):
    return decompose_feature(data, "response", hac_bandwidth_s=600.,
        shuffle_min_shift_s=240., n_shuffles=4, seed=11, **kwargs)


def test_known_case_centered_slopes_mixed_smoke_and_json():
    result = _decompose(_data())
    assert result["coverage"]["finite_cases"] == 6
    for row in result["per_case"]:
        assert row["defined"]
        assert abs(row["map_slope_per_mmhg"] - (.04+.005*row["caseid"])) < .001
        assert abs(row["hr_slope_per_bpm"] - (-.03+.002*row["caseid"])) < .001
        assert row["map_slope_se_per_mmhg"] >= 0
    assert result["variance_explained"]["pooled"]["explained_fraction"] > .999
    mixed = result["mixed_model"]
    assert mixed["defined"]
    assert isinstance(mixed["converged"], bool)
    assert isinstance(mixed["warnings"], list)
    assert "fixed_effects" in mixed
    assert len(mixed["conditional_case_slopes"]) == 6
    assert "map_slope_se_per_mmhg" not in mixed["conditional_case_slopes"][0]
    q4 = result["q4"]
    assert q4["matched_cases"] == 6
    assert len(q4["median_map_slope_per_mmhg"]) == 4
    assert len(q4["negative_fraction"]) == 4
    assert all(case["subset_windows"] == case["main_windows"] for case in q4["cases"])
    json.dumps(result, allow_nan=False)


def test_hac_uses_actual_time_gaps_not_row_lags():
    x = np.ones((3, 1))
    residual = np.array([1., 2., 3.])
    actual = _bartlett_hac(x, residual, np.array([0., 120., 1200.]), 300.)
    compressed = _bartlett_hac(x, residual, np.array([0., 120., 240.]), 300.)
    assert actual[0, 0] == pytest.approx((14. + 2*.6*1*2)/9.)
    assert not np.isclose(actual[0, 0], compressed[0, 0])


def test_circular_control_preserves_values_within_runs_and_minimum_shift():
    values = np.arange(16, dtype=float)
    times = np.r_[np.arange(8)*120., 2400.+np.arange(8)*120.]
    shifted, runs, offsets = _shift_residuals(values, times, 240., np.random.default_rng(6))
    assert runs == 2 and len(offsets) == 2
    for start, offset in zip((0, 8), offsets):
        assert 2 <= offset <= 6
        assert np.array_equal(shifted[start:start+8], np.roll(values[start:start+8], offset))
        assert set(shifted[start:start+8]) == set(values[start:start+8])
    assert _shift_residuals(values[:3], times[:3], 240., np.random.default_rng(6))[0] is None


def test_q4_drops_short_runs_and_matches_observed_subset_without_bridging_missing_rows():
    data = _data(n_cases=1, n=24)
    # NaN at 10 removes a grid point; the first 10 samples remain shiftable.
    # The final 3-sample run after the second gap must be excluded from Q4.
    data.loc[10, "response"] = np.nan
    data.loc[21:, "timestamp_s"] += 2400
    result = _decompose(data)
    assert not result["mixed_model"]["defined"]
    assert result["mixed_model"]["reason"] == "requires_at_least_two_cases"
    main = result["per_case"][0]
    case = result["q4"]["cases"][0]
    assert main["n_windows"] == 23 and case["subset_windows"] == 20
    assert result["q4"]["total_runs"] == 3 and result["q4"]["short_runs"] == 1
    assert case["subset_input_rows"] == list(range(10)) + list(range(11, 21))
    assert case["subset_run_ids"] == [0]*10 + [1]*10
    subset = data.iloc[case["subset_input_rows"]]
    matrix = np.column_stack((np.ones(len(subset)), subset.map_mmHg,
                              subset.hr_bpm, subset.timestamp_s/3600))
    expected = np.linalg.lstsq(matrix, subset.response, rcond=None)[0][1]
    assert case["observed_map_slope_per_mmhg"] == pytest.approx(expected)
    for shift in case["shifts"]:
        assert [offset["run_id"] for offset in shift["offsets"]] == [0, 1]
        assert all(offset["seconds"] >= 240 for offset in shift["offsets"])
    json.dumps(result, allow_nan=False)


def test_rank_coverage_and_explicit_parameters():
    data = _data(n_cases=1, n=5)
    data["map_mmHg"] = data.hr_bpm  # fixed design loses rank
    extra = data.iloc[:1].copy()
    extra["caseid"] = 99
    extra["response"] = np.nan
    result = _decompose(pd.concat([data, extra], ignore_index=True))
    assert not result["per_case"][0]["defined"]
    assert result["per_case"][1]["reason"] == "no_finite_windows"
    assert not result["q4"]["defined"]
    for key in ("hac_bandwidth_s", "shuffle_min_shift_s"):
        values = dict(hac_bandwidth_s=600., shuffle_min_shift_s=240., n_shuffles=1, seed=11)
        values[key] = 0
        with pytest.raises(ValueError, match="positive"):
            decompose_feature(data, "response", **values)
