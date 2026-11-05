"""Synthetic same-photon absorption reweighting checks; no MCX backend."""
import numpy as np
from mcx_optics.linear import (photon_weights, photon_log_weights,
    absorption_jacobian, log_absorption_response, select_sine_excursion,
    sine_ac_dc, volume_scattering, weight_coverage)


def test_shared_photon_log_jacobian_and_acdc():
    paths = np.array([[2., 3.], [4., 1.], [1., 5.]])
    initial = np.array([1., .6, .8])
    mua = np.array([.2, .1])
    weights = photon_weights(paths, initial, mua)
    assert np.allclose(weights, initial*np.exp(-paths@mua))
    jac = absorption_jacobian(paths, weights, 100)
    eps = 1e-5
    plus = np.sum(photon_weights(paths, initial, mua+[eps, 0]))/100
    minus = np.sum(photon_weights(paths, initial, mua-[eps, 0]))/100
    assert np.isclose((plus-minus)/(2*eps), jac['intensity_gradient_mm'][0], rtol=1e-8)
    normalized = weights/weights.sum()
    centered = paths-normalized@paths
    assert np.allclose(jac['log_intensity_hessian_mm2'], (centered.T*normalized)@centered)
    # A single path has exactly linear ln intensity, even when raw I underflows.
    response = log_absorption_response([[1000.]], [-1200.], [.7])
    assert response['log_intensity_change'] == -700.
    assert response['log_intensity_second_to_linear'] == 0.
    assert response['log_intensity_remainder_to_linear'] == 0.
    mixed = log_absorption_response(paths, photon_log_weights(paths, initial, mua), [.01, -.002])
    x = paths@np.array([.01, -.002])
    expected = np.log(normalized@np.exp(-x))
    assert np.isclose(mixed['log_intensity_change'], expected, atol=1e-15)
    assert weight_coverage(np.log(weights))['detected_weight_ess'] <= len(weights)
    q = np.array([2., 4., 7.])
    pulse = select_sine_excursion(q, weights, .01, .03)
    assert pulse['target_attainable']
    assert abs(pulse['achieved_ac_dc']-.03) < 1e-10
    phase = np.linspace(0, 2*np.pi, 100000, endpoint=False)
    signal = weights@np.exp(-pulse['fraction_excursion_amplitude']*q[:, None]*np.sin(phase))
    assert np.isclose(np.ptp(signal)/signal.mean(), .03, atol=1e-10)
    unavailable = select_sine_excursion([.01], [1.], .01, .05)
    assert not unavailable['target_attainable']
    # Stable Bessel and sinh evaluation also covers large optical excursions.
    assert np.isfinite(sine_ac_dc([2000.], [1.], 1.))
    assert np.allclose(volume_scattering(.1, 6., .9, 92.29, .985), [14.629, .9085])
