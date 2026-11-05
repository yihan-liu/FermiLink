"""Synthetic frequency-domain delay checks; no patient data."""
import json

import numpy as np
import pytest
from scipy import signal

from ppg_transfer.delay import (
    fit_delay, fit_equal_weight_delay, freeze_harmonic_weights,
    half_branch_diagnostics,
)


OPERATOR = dict(fs_hz=500, lo_hz=.2, hi_hz=10., order=2, phase="causal",
                sign=1, device_delay_s=.4)


def _transfer(hr, delay=.07, sign=1):
    frequency = np.arange(1, 6)*hr/60.
    sos = signal.butter(2, [.2, 10.], btype="bandpass", fs=500, output="sos")
    _, response = signal.sosfreqz(sos, worN=frequency, fs=500)
    # The filter alone has no harmonic-to-harmonic alias in this test range.
    phase = np.unwrap(np.angle(response)) + (np.pi if sign == -1 else 0.)
    phase += .23 - 2*np.pi*frequency*(.4+delay)
    return frequency, np.abs(response)*np.exp(1j*phase), phase


def test_operator_guided_raw_phase_slope_across_hr_and_5ms_effect():
    weights = np.array([1., 2., 4.])
    naive_errors = []
    for hr in (50, 75, 100, 120):
        for sign in (1, -1):
            frequency, h, truth_phase = _transfer(hr, sign=sign)
            operator = dict(OPERATOR, sign=sign)
            result = fit_delay(h, frequency, operator, weights)
            omega = 2*np.pi*frequency[:3]
            x = np.column_stack((np.ones(3), omega))
            expected = np.linalg.lstsq(x*np.sqrt(weights[:, None]),
                truth_phase[:3]*np.sqrt(weights), rcond=None)[0]
            assert result["defined"]
            assert result["tau_s"] == pytest.approx(-expected[1], abs=2.e-6)
            assert np.allclose(result["phase_rad"], truth_phase[:3], atol=2.e-5)
            assert result["h1_phase_delay_s"] == pytest.approx(-truth_phase[0]/omega[0], abs=2.e-6)
            assert result["branch_margin_rad"] > 0
            scaled = fit_delay(17.3*h, frequency, operator, weights)
            assert scaled["tau_s"] == pytest.approx(result["tau_s"], abs=1.e-12)
            _, delayed, _ = _transfer(hr, delay=.075, sign=sign)
            changed = fit_delay(delayed, frequency, operator, weights)
            assert changed["tau_s"]-result["tau_s"] == pytest.approx(.005, abs=1.e-10)
            naive = -np.linalg.lstsq(x, np.unwrap(np.angle(h[:3])), rcond=None)[0][1]
            naive_errors.append(abs(naive-result["tau_s"]))
    assert max(naive_errors) > .4  # direct raw unwrap aliases at high HR


def test_frozen_weights_equal_case_balance_and_zero_variance_undefined():
    records = []
    for cid, differences in ((1, [.2, .4]), (2, [.6])):
        for delta in differences:
            difference = delta*np.array([1., 2., 3.])
            records.append(dict(caseid=cid, odd_phase_rad=difference/2,
                                even_phase_rad=-difference/2))
    result = freeze_harmonic_weights(records)
    expected = .25*np.array([.23, .92, 2.07])
    assert result["defined"]
    assert np.allclose(result["variance"], expected)
    assert np.allclose(result["weights"], 1/expected)
    assert np.allclose(result["odd_even_phase_bias_rad"], [.45, .9, 1.35])
    assert result["coverage"]["case_counts"] == [2, 2, 2]
    assert result["coverage"]["window_counts"] == [3, 3, 3]
    zero = freeze_harmonic_weights([dict(caseid=1, odd_phase_rad=[0., 0., 0.],
                                        even_phase_rad=[0., 0., 0.])])
    assert not zero["defined"] and zero["weights"] == [None, None, None]
    empty = freeze_harmonic_weights([])
    assert not empty["defined"] and empty["variance"] == [None, None, None]
    json.dumps(result, allow_nan=False)


def test_full_halves_use_identical_frozen_weights_and_expose_branch_disagreement():
    frequency, h, _ = _transfer(100)
    weights = [3., 2., 1.]
    perturbation = np.array([.01, -.02, .03, 0., 0.])
    full = fit_delay(h, frequency, OPERATOR, weights)
    odd = fit_delay(h*np.exp(1j*perturbation), frequency, OPERATOR, weights)
    even = fit_delay(h*np.exp(-1j*perturbation), frequency, OPERATOR, weights)
    assert full["weights"] == odd["weights"] == even["weights"] == weights
    diagnostics = half_branch_diagnostics(full, odd, even)
    assert diagnostics["odd_even"]["disagreement_count"] == 0
    odd["phase_rad"][0] += 2*np.pi
    diagnostics = half_branch_diagnostics(full, odd, even)
    assert diagnostics["odd_even"]["disagreement_count"] == 1
    assert diagnostics["odd_even"]["cycle_disagreements"] == [1, 0, 0]
    equal = fit_equal_weight_delay(h, frequency, OPERATOR)
    assert equal["weights"] == [1., 1., 1.]
    assert not fit_delay(h, frequency, OPERATOR, [1., 0., 1.])["defined"]
