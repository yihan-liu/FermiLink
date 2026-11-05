"""Synthetic checks for native common-foot Round-3 harmonic descriptors."""
import numpy as np
import pytest

from ppg_forward import tf_harmonics


def _signals(feet, h):
    t = np.arange(int(np.ceil(feet[-1] * 500)) + 2) / 500
    beat = np.clip(np.searchsorted(feet, t, side="right") - 1, 0, len(feet) - 2)
    u = (t - feet[beat]) / np.diff(feet)[beat]
    a = np.array([14., 7., 4., 2., 1.]) * np.exp(
        1j * np.array([.3, -.2, .8, -1., .6]))
    basis = np.exp(2j * np.pi * u[:, None] * np.arange(1, 6))
    return 85 + (basis * a).real.sum(axis=1), 300 + (basis * a * h).real.sum(axis=1)


def _expected_features(h, rr):
    residual = np.angle(h / abs(h) * (np.conj(h[0]) / abs(h[0])) ** np.arange(1, 6))
    result = {}
    for k in range(2, 6):
        result[f"gainratio_k{k}"] = abs(h[k - 1]) / abs(h[0])
        result[f"phase_k{k}"] = residual[k - 1]
    for j, delta in enumerate(np.angle(np.exp(1j * np.diff(residual)))):
        result[f"groupdelay_k{j + 1}_k{j + 2}_s"] = -delta * rr / (2 * np.pi)
    return result


def test_stationary_analytic_transfer_and_native_coefficients():
    rr = .8
    feet = .0131 + np.arange(9) * rr
    f = np.arange(1, 6) / rr
    h = 2.3 * np.exp(-2j * np.pi * f * .037) / (1 + 2j * np.pi * f * .045)
    art, pleth = _signals(feet, h)
    result = tf_harmonics.compute_tf_harmonics(art, pleth, foot_times=feet)
    assert result["defined"] and result["n_beats"] == 8
    assert result["hr_bpm"] == pytest.approx(75)
    np.testing.assert_allclose(result["H"], h, atol=2e-4)
    for key, expected in _expected_features(h, rr).items():
        tolerance = .0005 if key.startswith("groupdelay") else .0005
        assert result["features"][key] == pytest.approx(expected, abs=tolerance)
    np.testing.assert_allclose(result["H"], result["pleth_coefficients"].mean(axis=0)
                               / result["art_coefficients"].mean(axis=0))
    for half, indices in (("odd", slice(None, None, 2)), ("even", slice(1, None, 2))):
        assert result[half]["n_beats"] == 4
        np.testing.assert_allclose(result[half]["H"],
                                   result["pleth_coefficients"][indices].mean(axis=0)
                                   / result["art_coefficients"][indices].mean(axis=0))
    assert result["phase_grid"][0] == 0 and result["phase_grid"][-1] == 1
    assert result["art_phase_mean"].shape == (501,)
    assert "phase_k1" not in result["features"]


def test_positive_gain_and_offset_leave_features_invariant():
    feet = .012 + np.arange(8) * .8
    h = np.array([1.4, 1.1, .9, .7, .5]) * np.exp(-1j * np.array([.1, .5, .4, 1., .8]))
    art, pleth = _signals(feet, h)
    original = tf_harmonics.compute_tf_harmonics(art, pleth, foot_times=feet)
    changed = tf_harmonics.compute_tf_harmonics(art + 112, 4.2 * pleth + 713,
                                               foot_times=feet)
    np.testing.assert_allclose(changed["H"], 4.2 * original["H"], atol=1e-11)
    np.testing.assert_allclose(list(changed["features"].values()),
                               list(original["features"].values()), atol=1e-11)


def test_variable_rr_retains_full_phase_beats_and_known_phase_harmonics():
    # Phase-locked waveforms across variable RR are not one stationary LTI input.
    rr = np.array([.73, .911, .843, .767, .952, .801, .883])
    feet = .0131 + np.r_[0, np.cumsum(rr)]
    h = np.array([1.5, 1.2, .9, .7, .4]) * np.exp(1j * np.array([-.2, -.3, -.1, .4, .6]))
    art, pleth = _signals(feet, h)
    result = tf_harmonics.compute_tf_harmonics(art, pleth, foot_times=feet)
    np.testing.assert_allclose(result["beat_rr_s"], rr)
    np.testing.assert_allclose(result["H"], h, atol=4e-4)
    np.testing.assert_allclose(result["frequencies_hz"], np.arange(1, 6) / rr.mean())
    assert result["hr_bpm"] == pytest.approx(60 / rr.mean())
    for key, expected in _expected_features(h, rr.mean()).items():
        assert result["features"][key] == pytest.approx(expected, abs=.0005)
    assert result["art_coefficients"].shape == (7, 5)


def test_common_delay_removed_and_group_delay_principal_branch():
    rr = .8
    feet = np.arange(8) * rr
    h = 2. * np.exp(-2j * np.pi * np.arange(1, 6) / rr * .067)
    art, pleth = _signals(feet, h)
    result = tf_harmonics.compute_tf_harmonics(art, pleth, foot_times=feet)
    for key, value in result["features"].items():
        assert value == pytest.approx(1. if key.startswith("gainratio") else 0., abs=1e-10)
    h = np.exp(1j * np.array([0., 2.9, -2.9, 2.7, -2.7]))
    art, pleth = _signals(feet, h)
    result = tf_harmonics.compute_tf_harmonics(art, pleth, foot_times=feet)
    for key, expected in _expected_features(h, rr).items():
        assert result["features"][key] == pytest.approx(expected, abs=1e-10)
    assert result["residual_phase_unwrapped_rad"][2] > np.pi


def test_default_detection_uses_art_only_and_complete_shared_beats(monkeypatch):
    feet = np.arange(8) * .8
    art, pleth = _signals(feet, np.ones(5, complex))
    calls = []
    def detect(signal, fs_hz):
        calls.append((signal, fs_hz))
        return np.r_[-.8, feet, feet[-1] + .8]
    monkeypatch.setattr(tf_harmonics.metrics, "feet", detect)
    result = tf_harmonics.compute_tf_harmonics(art, pleth)
    assert len(calls) == 1 and calls[0][0] is art and calls[0][1] == 500
    assert result["n_beats"] == 7
    np.testing.assert_allclose(result["beat_feet_s"], np.column_stack((feet[:-1], feet[1:])))


def test_material_input_rules_and_absent_harmonics():
    feet = np.arange(6) * .8
    t = np.arange(2001) / 500
    art = 85 + np.cos(2 * np.pi * t / .8)
    result = tf_harmonics.compute_tf_harmonics(art, art, foot_times=feet)
    assert result["art_harmonic_present"].tolist() == [True, False, False, False, False]
    assert np.isnan(result["H"][1:]).all()
    assert np.isnan(result["features"]["gainratio_k2"])
    flat = tf_harmonics.compute_tf_harmonics(np.full_like(t, 85.), art, foot_times=feet)
    assert not flat["art_harmonic_present"].any()
    assert np.isnan(flat["H"]).all()
    assert all(np.isnan(value) for value in flat["features"].values())
    assert not tf_harmonics.compute_tf_harmonics(art, art, foot_times=[0., .8])["defined"]
    with pytest.raises(ValueError, match="native 500"):
        tf_harmonics.compute_tf_harmonics(art, art, fs_hz=50)
    with pytest.raises(ValueError, match="aligned"):
        tf_harmonics.compute_tf_harmonics(art[:-1], art)
    bad = art.copy()
    bad[20] = np.nan
    with pytest.raises(ValueError, match="finite"):
        tf_harmonics.compute_tf_harmonics(art, bad)
    with pytest.raises(ValueError, match="increasing"):
        tf_harmonics.compute_tf_harmonics(art, art, foot_times=[0, .8, .7])
