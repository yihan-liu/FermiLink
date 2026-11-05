"""Synthetic checks for M4 prescribed operating pressure and absolute RC."""
import numpy as np
import pytest
from scipy.linalg import expm

from ppg_forward.models import m4_line


def _manual_transfer(frequencies, params, q, resistance_scale=1.0):
    """Independent matrix-exponential solution with a fixed reference bed C."""
    p = {**m4_line.DEFAULT_PARAMS, **params}
    rho = m4_line.RHO_KG_M3
    c0 = p["wave_speed_m_s"]
    area0 = np.pi*m4_line.INLET_RADIUS_M**2
    rb0 = p["terminal_resistance_ratio"]*rho*c0/area0
    cb0 = p["bed_tau_s"]/rb0
    c = c0*np.sqrt(q)
    dx = m4_line.LENGTH_M/m4_line.N_SEGMENTS
    result = []
    for f in frequencies:
        w = 2*np.pi*f
        matrix = np.eye(2, dtype=complex)
        for i in range(m4_line.N_SEGMENTS):
            rref = m4_line.INLET_RADIUS_M*(
                1+(p["taper_ratio"]-1)*(i+.5)/m4_line.N_SEGMENTS)
            area = np.pi*(rref*q)**2
            resistance = 8*np.pi*m4_line.VISCOSITY_PA_S/area**2
            inertance = rho/area
            compliance = area/(rho*c**2)
            generator = np.array([[0, resistance+1j*w*inertance],
                                  [1j*w*compliance, 0]], dtype=complex)
            matrix = matrix @ expm(dx*generator)
        admittance = 1/(resistance_scale*rb0)+1j*w*cb0
        result.append(1/(matrix[0, 0]+matrix[0, 1]*admittance))
    return np.array(result)


def test_reference_pressure_preserves_default_and_fitted_parameters():
    frequencies = np.r_[0., np.arange(1, 6)*1.25]
    for params in ({}, {"wave_speed_m_s": 5.2, "taper_ratio": .45,
                       "terminal_resistance_ratio": 3.5, "bed_tau_s": .08}):
        operating = {**params, "operating_map_mmHg": 90.,
                     "reference_map_mmHg": 90., "resistance_scale": 1.}
        np.testing.assert_array_equal(
            m4_line.transfer_function(frequencies, params),
            m4_line.transfer_function(frequencies, operating))
        art = 90+20*np.sin(2*np.pi*1.25*np.arange(1500)/50)
        np.testing.assert_array_equal(
            m4_line.predict(art, params), m4_line.predict(art, operating))
    assert m4_line.PARAM_NAMES == ("wave_speed_m_s", "taper_ratio",
                                  "terminal_resistance_ratio", "bed_tau_s")


def test_analytic_pressure_factor_geometry_and_wave_speed():
    c0 = 5.
    q = 1.15
    delta = (q-1)*2*m4_line.RHO_KG_M3*c0**2/133.322387415
    params = {"wave_speed_m_s": c0, "reference_map_mmHg": 80.,
              "operating_map_mmHg": 80.+delta}
    merged = {**m4_line.DEFAULT_PARAMS, **params}
    assert m4_line._operating_scales(merged) == pytest.approx((q, 1.))
    frequencies = np.arange(1, 6)*1.2
    np.testing.assert_allclose(
        m4_line.transfer_function(frequencies, params),
        _manual_transfer(frequencies, params, q), rtol=2e-13, atol=1e-14)
    near_reference = {**params, "operating_map_mmHg": 80.+1e-5}
    np.testing.assert_allclose(
        m4_line.transfer_function(frequencies, near_reference),
        m4_line.transfer_function(frequencies, {"wave_speed_m_s": c0}),
        rtol=1e-6, atol=1e-8)


def test_pressure_change_holds_absolute_reference_resistance_and_capacitance():
    params = {"wave_speed_m_s": 6., "reference_map_mmHg": 80.,
              "operating_map_mmHg": 115.}
    q = 1+35*133.322387415/(2*m4_line.RHO_KG_M3*6.**2)
    frequencies = np.array([0., .05, .3])
    actual = m4_line.transfer_function(frequencies, params)
    np.testing.assert_allclose(
        actual, _manual_transfer(frequencies, params, q),
        rtol=2e-13, atol=1e-14)
    radii = m4_line.INLET_RADIUS_M*(
        1+(.6-1)*(np.arange(m4_line.N_SEGMENTS)+.5)/m4_line.N_SEGMENTS)*q
    rline = np.sum(8*m4_line.VISCOSITY_PA_S/(np.pi*radii**4)
                   *m4_line.LENGTH_M/m4_line.N_SEGMENTS)
    inferred_rbed = rline/(1/actual[0].real-1)
    rb0 = 8*m4_line.RHO_KG_M3*6./(np.pi*m4_line.INLET_RADIUS_M**2)
    assert inferred_rbed == pytest.approx(rb0, rel=2e-13)


def test_path_a_scales_load_against_manual_low_frequency_transfer():
    scale = 1.7
    params = {"reference_map_mmHg": 85., "operating_map_mmHg": 105.,
              "resistance_scale": scale}
    q = 1+20*133.322387415/(2*m4_line.RHO_KG_M3*8.**2)
    frequencies = np.array([0., .05, .3])
    np.testing.assert_allclose(
        m4_line.transfer_function(frequencies, params),
        _manual_transfer(frequencies, params, q, scale),
        rtol=2e-13, atol=1e-14)


def test_prediction_uses_operating_fractional_compliance(monkeypatch):
    monkeypatch.setattr(m4_line, "transfer_function",
                        lambda frequencies, params: np.ones(len(frequencies), complex))
    params = {"reference_map_mmHg": 80., "operating_map_mmHg": 110.}
    q = 1+30*133.322387415/(2*m4_line.RHO_KG_M3*8.**2)
    art = 110+20*np.sin(2*np.pi*1.2*np.arange(1500)/50)
    expected = (art-art[0])*133.322387415/(m4_line.RHO_KG_M3*8.**2*q)
    np.testing.assert_allclose(m4_line.predict(art, params), expected,
                               rtol=1e-12, atol=1e-14)


def test_pressure_mode_has_finite_five_harmonics_and_prediction():
    params = {"reference_map_mmHg": 85., "operating_map_mmHg": 105.,
              "resistance_scale": 1.4}
    f = np.arange(1, 6)*1.25
    assert np.isfinite(m4_line.transfer_function(f, params)).all()
    t = np.arange(1500)/50
    art = 105+sum(10/k*np.sin(2*np.pi*k*1.25*t) for k in range(1, 6))
    predicted = m4_line.predict(art, params)
    assert predicted.shape == art.shape and np.isfinite(predicted).all()


@pytest.mark.parametrize("params, message", [
    ({"operating_map_mmHg": 100.}, "provided together"),
    ({"reference_map_mmHg": 80.}, "provided together"),
    ({"operating_map_mmHg": -1000., "reference_map_mmHg": 80.}, "positive finite q"),
    ({"resistance_scale": 0.}, "resistance_scale"),
    ({"resistance_scale": -1.}, "resistance_scale"),
])
def test_invalid_operating_inputs(params, message):
    with pytest.raises(ValueError, match=message):
        m4_line.transfer_function(np.array([0., 1.]), params)
