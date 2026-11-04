"""One synthetic P7 development smoke; no MCX backend or patient data."""
import json
import numpy as np
import pytest
from ppg_forward.optics_linear import (photon_weights, photon_log_weights,
    absorption_jacobian, log_absorption_response, select_sine_excursion,
    sine_ac_dc, volume_scattering, weight_coverage)
from ppg_forward import mcx_driver as driver


def test_shared_photon_log_jacobian_acdc_and_prepare(tmp_path, monkeypatch):
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
    job = {'source_fraction': 0., 'baseline_fractions': [.01], 'target_ac_dc': [.03]}
    samples = [(q, np.log(weights)), (q*2, np.log(weights*.4))]
    rows = driver.p7_batch(job, samples)
    assert rows[0][0]['fraction_excursion_amplitude'] == rows[1][0]['fraction_excursion_amplitude']
    assert rows[0][0]['achieved_ac_dc'] != rows[1][0]['achieved_ac_dc']
    assert abs(rows[0][0]['pooled_achieved_ac_dc']-.03) < 1e-10
    assert driver.p7_batch(job, [(q*0, np.log(weights))])[0][0]['endpoints'] == []

    # Preparing real canonical geometry is metadata-only. Any solver call fails.
    def forbidden(*args, **kwargs):
        raise AssertionError('development check must not launch MCX')
    monkeypatch.setattr(driver, 'mcx_read', forbidden)
    result = driver.run_from_config({'execution': 'prepare'}, tmp_path)
    assert result['study_status'] == 'prepared' and result['solver_executed'] is False
    root = tmp_path/'mcx-linear'
    study = json.loads((root/'study.json').read_text())
    assert study['inputs']['solver_calls'] == 60 and study['inputs']['source_fraction'] == 0
    assert study['inputs']['grid']['target_ac_dc'] == [.01, .03, .05]
    jobs = [json.loads(p.read_text()) for p in root.glob('*/input.json')]
    assert len(jobs) == 6
    assert all(j['blood_absorption_per_mm'] >= j['matrix_absorption_per_mm'] for j in jobs)
    # Exercise the saved seed-estimate summary at one common a per condition.
    for j in jobs:
        sample = [(q*(1+.01*k), np.log(weights)) for k in range(10)]
        batch = driver.p7_batch(j, sample)
        driver.dump(root/j['name']/'results.json', {'seeds': [
            {'baseline': {'intensity': .001}, 'pulsatile': cells} for cells in batch]})
    summary = driver.summarize(root)
    assert summary['all_grid_targets_attainable']
    assert summary['maximum_of_pointwise_means']['ratio'] >= 0
    assert all(p['fraction_excursion_amplitude_mean_se'][1] < 1e-15
        for c in summary['conditions'] for p in c['pulsatile'])
    with pytest.raises(FileExistsError):
        driver.run_from_config({}, tmp_path)
    scatter = driver.run_from_config({'study': 'scattering', 'output_name': 'scatter'}, tmp_path)
    scatter_root = tmp_path/'scatter'
    assert scatter['study_status'] == 'prepared'
    study = json.loads((scatter_root/'study.json').read_text())
    assert study['inputs']['solver_calls'] == 100
    canonical = json.loads(driver.CANONICAL.read_text())
    for job_path in scatter_root.glob('*/input.json'):
        j = json.loads(job_path.read_text())
        wave = next(w for w in canonical['wavelengths'] if w['wavelength_nm'] == j['wavelength_nm'])
        assert j['config']['optical_properties'][3] == wave['mcx_config']['optical_properties'][3]
        assert np.allclose(j['config']['optical_properties'][2][1:3],
            volume_scattering(.1, j['matrix_mus_per_mm'], j['matrix_g'],
                j['blood_mus_per_mm'], j['blood_g']))

    for jpath in scatter_root.glob('*/input.json'):
        j = json.loads(jpath.read_text())
        seeds = []
        for k in range(10):
            seeds.append({'baseline': {'intensity': .001}, 'paired': [
                {'absorption_log_increment': .8, 'total_log_increment': 1., 'scatter_log_increment': .2},
                {'absorption_log_increment': -.2+(k-4.5)*.1,
                 'total_log_increment': (k-4.5)*.1, 'scatter_log_increment': .2}]})
        driver.dump(jpath.parent/'results.json', {'seeds': seeds})
    report = driver.summarize(scatter_root)
    assert np.isclose(report['conditions'][0]['paired'][0]['scatter_share_absorption_first'], .2)
    assert report['conditions'][0]['paired'][1]['scatter_share_absorption_first'] is None
