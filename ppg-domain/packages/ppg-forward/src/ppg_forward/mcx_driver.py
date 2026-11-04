"""Prepare or execute synthetic fixed-scatter P7 and scatter sensitivity studies.

Preparation never imports PMCX or launches a solver. Actual experiment stages
are invoked by the FermiLink loop with execution=run, not by development tests.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

from ppg_forward.optics_linear import (photon_log_weights, normalized_weights,
    logsumexp, absorption_jacobian, log_absorption_response, volume_scattering,
    select_sine_excursion, sine_ac_dc, weight_coverage)

CANONICAL = Path('/data/liuyihan/FermiLink/ppg-domain/packages/peripheral-ppg/ppg_examples/engineering_example.json')
RUNTIME = '/data/liuyihan/FermiLink/ppg-domain/.runtime/mcx/venv/bin/python'
HB_SOURCE = 'https://omlc.org/spectra/hemoglobin/summary.html'
EXTINCTION = {660: (319.6, 3226.56), 940: (1214., 693.44)}
SCATTER_SOURCE = 'https://pmc.ncbi.nlm.nih.gov/articles/PMC3953607/'
BLOOD_SCATTER = {660: (92.29, .9850), 940: (56.84, .9768)}
T9_975 = 2.2621571627409915


def now():
    return datetime.now(timezone.utc).isoformat()


def dump(path, content):
    Path(path).write_text(json.dumps(content, indent=2, allow_nan=False)+'\n')


def blood_absorption(wavelength, saturation):
    oxy, deoxy = EXTINCTION[wavelength]
    return 2.303*150/64500/10*(saturation*oxy+(1-saturation)*deoxy)


def clone(value):
    return json.loads(json.dumps(value))


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


def prepare(config, out):
    study = config.get('study', 'log-p7')
    if study not in ('log-p7', 'scattering'):
        raise ValueError('study must be log-p7 or scattering')
    nphoton = int(config.get('nphoton', 100000000))
    seeds = int(config.get('seeds', 10))
    gpus = config.get('gpuid', [1, 2])
    if nphoton <= 0 or seeds != 10 or not 1 <= len(gpus) <= 2:
        raise ValueError('study requires positive photons, 10 seeds and one or two GPUs')
    canonical_path = Path(config.get('canonical_config', CANONICAL)).resolve()
    canonical = json.loads(canonical_path.read_text())
    grid = config.get('grid', {})
    fractions = grid.get('baseline_fractions', [.01, .055, .10])
    saturations = grid.get('saturations', [.90, .95, 1.])
    targets = grid.get('target_ac_dc', [.01, .03, .05])
    source_fraction = float(config.get('source_fraction', 0.))
    if (not fractions or not saturations or not targets
            or any(not .01 <= f <= .10 for f in fractions)
            or any(not .90 <= s <= 1 for s in saturations)
            or any(not 0 < a <= .05 for a in targets)
            or not 0 <= source_fraction <= 1):
        raise ValueError('grid outside the declared engineering domain')
    out.mkdir(parents=True, exist_ok=False)
    dump(out/'canonical_config.json', canonical)
    dump(out/'study_config.json', config)
    jobs = []
    for wave in canonical['wavelengths']:
        wl = wave['wavelength_nm']
        if wl not in (660, 940):
            continue
        for saturation in ([.98] if study == 'scattering' else saturations):
            fraction = .10 if study == 'scattering' else source_fraction
            name = f'{wl}nm-s{saturation:.4f}'
            cfg = clone(wave['mcx_config'])
            blood = blood_absorption(wl, saturation)
            label = wave['mixture_label']
            matrix = wave['mua_matrix_per_mm']
            if blood < matrix:
                raise ValueError(f'negative absorption contrast at {wl}nm/S={saturation}')
            cfg['optical_properties'][label][0] = matrix+fraction*(blood-matrix)
            job = {'name': name, 'study': study, 'wavelength_nm': wl,
                'source_fraction': fraction, 'saturation': saturation,
                'blood_absorption_per_mm': blood, 'matrix_absorption_per_mm': matrix,
                'mixture_label': label, 'config': cfg, 'seed_count': seeds,
                'seed_start': int(config.get('seed_start', 202611040))}
            if study == 'log-p7':
                # Fixed S defines explicit vessel absorption, held fixed over f/pulse.
                cfg['optical_properties'][3][0] = blood
                job.update(baseline_fractions=fractions, target_ac_dc=targets)
            else:
                # Only label2 mus and g change. Explicit vessel label3 is canonical.
                matrix_mus, matrix_g = cfg['optical_properties'][label][1:3]
                blood_mus, blood_g = BLOOD_SCATTER[wl]
                cfg['optical_properties'][label][1:3] = volume_scattering(
                    fraction, matrix_mus, matrix_g, blood_mus, blood_g)
                job.update(matrix_mus_per_mm=matrix_mus, matrix_g=matrix_g,
                    blood_mus_per_mm=blood_mus, blood_g=blood_g,
                    direct_multipliers=[1.5, 2.0])
            cfg.update(nphoton=nphoton, maxdetphoton=max(2000000, nphoton//10))
            (out/name).mkdir()
            dump(out/name/'input.json', job)
            jobs.append(name)
    calls = len(jobs)*seeds*(5 if study == 'scattering' else 1)
    manifest = {'study': study, 'status': 'prepared', 'prepared_utc': now(),
        'actual_start_utc': None, 'actual_end_utc': None, 'solver_executed': False,
        'inputs': {'canonical_config': str(canonical_path), 'data_origin': 'synthetic_only',
            'hb_spectra_source': HB_SOURCE, 'hb_g_per_litre': 150,
            'extinction_cm_inverse_per_molar': EXTINCTION,
            'nphoton_per_direct_run': nphoton, 'seed_count': seeds, 'jobs': jobs,
            'gpu_ids': gpus, 'pmcx_python': config.get('runtime_python', RUNTIME),
            'solver_calls': calls, 'total_launched_photons': calls*nphoton},
        'notes': ['SNUADC PLETH has no DC; pulse targets are engineering detector AC/DC.',
            'No measured raw PLETH AC/DC calibration is claimed.',
            'Seed-level estimates and logs retained; detected-photon arrays not retained.']}
    if study == 'log-p7':
        manifest['inputs'].update(grid={'baseline_fractions': fractions,
            'saturations': saturations, 'target_ac_dc': targets}, source_fraction=source_fraction,
            pulse_definition='f=f0+a*sin(theta); a solved per wavelength and photon estimate from exact intensity peak-to-peak / cycle mean',
            source_reuse='one fixed-scatter photon batch per wavelength/saturation/seed for all f and pulses',
            grid_status=config.get('grid_status', 'scientist_reviewed_finite_grid'))
        manifest['notes'] += ['Natural-log intensity second/linear criterion <0.01.',
            'Finite grid only; no continuous-domain bound or coverage pass is inferred from ESS.']
    else:
        manifest['inputs'].update(blood_scatter_source=SCATTER_SOURCE,
            blood_scatter_column='Original KK/PY theory, oxygenated Hct45%',
            blood_scatter_coefficients=BLOOD_SCATTER,
            mixture_law='volume mixing of mus and g separately in label2 only',
            pairing='same seed B/A/T; independent seeds across repetitions',
            vessel_label3='canonical coefficients unchanged in all arms',
            share='mean(log T-log A)/mean(log T-log B); undefined when total 95% t9 CI contains zero')
    dump(out/'study.json', manifest)
    return manifest


def mcx_read(config, log):
    import mcx_optics
    import pmcx
    c = mcx_optics._config(config)
    c.update(flog=str(log), issaveseed=0, issave2pt=0)
    result = pmcx.mcxlab(c)
    det = result['detp']
    paths = np.asarray(det['ppath'], dtype=float)*c['unitinmm']
    if len(paths) >= c['maxdetphoton']:
        raise RuntimeError('detected photon buffer may be truncated')
    w0 = np.asarray(det.get('w0', np.ones(len(paths))), dtype=float).reshape(-1)
    lw = photon_log_weights(paths, w0, np.asarray(config['optical_properties'])[1:, 0])
    log_intensity = logsumexp(lw)-math.log(config['nphoton'])
    reading = {'intensity': float(np.exp(log_intensity)), 'log_intensity': log_intensity,
        'seed': config['seed'], 'nphoton': config['nphoton'],
        'initial_weights_included': True, 'initial_weight_sum': float(w0.sum()),
        'detector_buffer_truncated': False, **weight_coverage(lw)}
    return paths, lw, reading


def p7_batch(job, samples):
    """Choose one physical excursion per condition from pooled seed intensities.

    Each sample has q=L_mix*absorption_contrast and original source log weights.
    Equal launched counts make concatenated photon weights the intensity pool.
    Every seed is then evaluated at the SAME selected physical excursion.
    """
    all_q = np.concatenate([q for q, lw in samples])
    all_source_lw = np.concatenate([lw for q, lw in samples])
    result = [[] for sample in samples]
    for fraction in job['baseline_fractions']:
        pool_lw = all_source_lw-(fraction-job['source_fraction'])*all_q
        pool_weights = normalized_weights(pool_lw)
        for target in job['target_ac_dc']:
            pulse = select_sine_excursion(all_q, pool_weights, fraction, target)
            for index, (q, source_lw) in enumerate(samples):
                lw = source_lw-(fraction-job['source_fraction'])*q
                weights = normalized_weights(lw)
                amplitude = pulse['fraction_excursion_amplitude']
                endpoints = []
                if pulse['target_attainable']:
                    for sign in (-1, 1):
                        endpoint_lw = lw-sign*amplitude*q
                        endpoints.append({'sign': sign,
                            **log_absorption_response(q[:, None], lw, [sign*amplitude]),
                            'weight_coverage': weight_coverage(endpoint_lw),
                            'maximum_log_reweight_from_source': float(np.max(-(fraction+sign*amplitude-job['source_fraction'])*q))})
                result[index].append({'baseline_fraction': fraction, **pulse,
                    'pooled_achieved_ac_dc': pulse['achieved_ac_dc'],
                    'achieved_ac_dc': sine_ac_dc(q, weights, amplitude),
                    'excursion_selection': 'common physical excursion from pooled seed intensities',
                    'baseline_coverage': weight_coverage(lw), 'endpoints': endpoints})
    return result


def worker(out, gpu):
    out = Path(out).resolve()
    job = json.loads((out/'input.json').read_text())
    result = {'name': job['name'], 'started_utc': now(), 'backend': 'PMCX CUDA',
        'backend_version': importlib.metadata.version('pmcx'), 'seeds': []}
    cfg = clone(job['config'])
    cfg['gpuid'] = gpu
    label = job['mixture_label']
    contrast = job['blood_absorption_per_mm']-job['matrix_absorption_per_mm']
    samples = []
    for index in range(job['seed_count']):
        cfg['seed'] = job['seed_start']+index
        paths, lw, base = mcx_read(cfg, out/f'mcx-B-{index:02d}.log')
        jacobian = absorption_jacobian(paths, normalized_weights(lw), 1)
        # Covariance and mean paths do not depend on normalization of weights.
        row = {'seed_index': index, 'baseline': base,
            'mean_path_mm': plain(jacobian['mean_path_mm']),
            'log_intensity_hessian_mm2': plain(jacobian['log_intensity_hessian_mm2'])}
        if job['study'] == 'log-p7':
            samples.append((paths[:, label-1]*contrast, lw))
        else:
            row['paired'] = []
            for multiplier in job['direct_multipliers']:
                target = job['source_fraction']*multiplier
                arm_a = clone(cfg)
                arm_a['optical_properties'][label][0] = job['matrix_absorption_per_mm']+target*contrast
                _, _, a = mcx_read(arm_a, out/f'mcx-A-{multiplier:.1f}-{index:02d}.log')
                arm_t = clone(arm_a)
                arm_t['optical_properties'][label][1:3] = volume_scattering(target,
                    job['matrix_mus_per_mm'], job['matrix_g'], job['blood_mus_per_mm'], job['blood_g'])
                _, _, t = mcx_read(arm_t, out/f'mcx-T-{multiplier:.1f}-{index:02d}.log')
                row['paired'].append({'multiplier': multiplier, 'A': a, 'T': t,
                    'absorption_log_increment': a['log_intensity']-base['log_intensity'],
                    'total_log_increment': t['log_intensity']-base['log_intensity'],
                    'scatter_log_increment': t['log_intensity']-a['log_intensity']})
        result['seeds'].append(row)
        dump(out/'results.partial.json', result)
    if job['study'] == 'log-p7':
        for row, cells in zip(result['seeds'], p7_batch(job, samples)):
            row['pulsatile'] = cells
    result['completed_utc'] = now()
    dump(out/'results.json', result)
    (out/'results.partial.json').unlink()


def mean_se(values):
    v = np.asarray(values, dtype=float)
    return [float(v.mean()), float(v.std(ddof=1)/math.sqrt(len(v)))]


def summarize(out):
    manifest = json.loads((out/'study.json').read_text())
    summary = {'study': manifest['study'], 'conditions': [],
        'interpretation': 'finite engineering grid; no continuous-domain or patient AC/DC claim'}
    all_pointwise_means = []
    all_attainable = True
    for name in manifest['inputs']['jobs']:
        job = json.loads((out/name/'input.json').read_text())
        seeds = json.loads((out/name/'results.json').read_text())['seeds']
        condition = {k: job[k] for k in ('name', 'wavelength_nm', 'saturation')}
        condition['baseline_intensity_mean_se'] = mean_se([s['baseline']['intensity'] for s in seeds])
        if manifest['study'] == 'log-p7':
            condition['pulsatile'] = []
            for i, pulse in enumerate(seeds[0]['pulsatile']):
                rows = [s['pulsatile'][i] for s in seeds]
                covered = all(r['target_attainable'] for r in rows)
                all_attainable &= covered
                cell = {'baseline_fraction': pulse['baseline_fraction'],
                    'target_ac_dc': pulse['target_ac_dc'], 'all_seeds_target_attainable': covered,
                    'attainable_seed_count': sum(r['target_attainable'] for r in rows),
                    'pooled_achieved_ac_dc': pulse['pooled_achieved_ac_dc'],
                    'fraction_excursion_amplitude_mean_se': mean_se([r['fraction_excursion_amplitude'] for r in rows]),
                    'achieved_ac_dc_mean_se': mean_se([r['achieved_ac_dc'] for r in rows]), 'endpoints': []}
                for j, endpoint in enumerate(pulse['endpoints']):
                    estimates = [r['endpoints'][j] for r in rows]
                    e = {'sign': endpoint['sign']}
                    for key in ('log_intensity_second_to_linear', 'log_intensity_remainder_to_linear'):
                        values = [r[key] for r in estimates]
                        e[key+'_mean_se'] = mean_se(values) if all(v is not None for v in values) else None
                    ratio = e['log_intensity_second_to_linear_mean_se']
                    if ratio is not None and covered:
                        all_pointwise_means.append({'ratio': ratio[0], 'condition': name,
                            'baseline_fraction': pulse['baseline_fraction'], 'target_ac_dc': pulse['target_ac_dc'],
                            'sign': endpoint['sign']})
                    e['minimum_detected_weight_ess'] = min(r['weight_coverage']['detected_weight_ess'] for r in estimates)
                    e['maximum_normalized_weight'] = max(r['weight_coverage']['maximum_normalized_weight'] for r in estimates)
                    cell['endpoints'].append(e)
                condition['pulsatile'].append(cell)
        else:
            condition['paired'] = []
            for i, multiplier in enumerate(job['direct_multipliers']):
                cell = {'multiplier': multiplier}
                for key in ('absorption_log_increment', 'total_log_increment', 'scatter_log_increment'):
                    cell[key+'_mean_se'] = mean_se([s['paired'][i][key] for s in seeds])
                numerator, numerator_se = cell['scatter_log_increment_mean_se']
                denominator, denominator_se = cell['total_log_increment_mean_se']
                interval = [denominator-T9_975*denominator_se, denominator+T9_975*denominator_se]
                cell['total_log_increment_95CI'] = interval
                cell['scatter_share_absorption_first'] = None if interval[0] <= 0 <= interval[1] else numerator/denominator
                condition['paired'].append(cell)
        summary['conditions'].append(condition)
    if manifest['study'] == 'log-p7':
        worst = max(all_pointwise_means, key=lambda r: r['ratio']) if all_pointwise_means else None
        summary.update(threshold=.01, maximum_of_pointwise_means=worst,
            all_grid_targets_attainable=all_attainable,
            finite_grid_point_estimates_below_one_percent=(worst['ratio'] < .01) if worst and all_attainable else None,
            ratio_definition='0.5 Var_w(X)/abs(E_w(X)), X=L dot delta_mua',
            uncertainty='pointwise seed mean and SE; maximum of pointwise means is descriptive, without simultaneous confidence guarantee',
            coverage_interpretation='ESS/max weight are reported diagnostics without an invented acceptance threshold',
            boundary_interpretation='pointwise means and SE are descriptive near the 1% boundary; no simultaneous confidence claim')
    else:
        summary['interpretation'] = 'engineering volume-mixture sensitivity; signed share; no threshold or pass/fail'
    dump(out/'summary.json', summary)
    return summary


def run(out):
    manifest = json.loads((out/'study.json').read_text())
    if manifest['status'] != 'prepared':
        raise ValueError('execution requires a fresh prepared study')
    manifest.update(status='running', actual_start_utc=now(), solver_executed=True)
    dump(out/'study.json', manifest)
    jobs = manifest['inputs']['jobs']
    gpu_ids = manifest['inputs']['gpu_ids']
    def gpu_jobs(index):
        for name in jobs[index::len(gpu_ids)]:
            subprocess.run([manifest['inputs']['pmcx_python'], '-B', '-m',
                'ppg_forward.mcx_driver', '--worker', str(out/name), '--worker-gpu', str(gpu_ids[index])],
                check=True, env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])
                    +os.pathsep+os.environ.get('PYTHONPATH', ''),
                    'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    try:
        with ThreadPoolExecutor(max_workers=len(gpu_ids)) as pool:
            list(pool.map(gpu_jobs, range(len(gpu_ids))))
        summarize(out)
        manifest.update(status='complete', actual_end_utc=now())
    except Exception as exc:
        manifest.update(status='failed', actual_end_utc=now(), error=str(exc))
        raise
    finally:
        dump(out/'study.json', manifest)
    return manifest


def run_from_config(config: dict, out: Path) -> dict:
    """Public pipeline API. Create a fresh child; prepare by default."""
    mode = config.get('execution', 'prepare')
    if mode not in ('prepare', 'run'):
        raise ValueError('execution must be prepare or run')
    child_name = config.get('output_name', 'mcx-linear')
    if Path(child_name).name != child_name or child_name in ('.', '..'):
        raise ValueError('output_name must be a child directory name')
    child = Path(out).resolve()/child_name
    manifest = prepare(config, child)
    if mode == 'run':
        manifest = run(child)
    return {'outputs': [str(p) for p in sorted(child.rglob('*')) if p.is_file()],
        'input_files': [str(Path(manifest['inputs']['canonical_config']))],
        'study_status': manifest['status'], 'solver_executed': manifest['solver_executed'],
        'study_directory': str(child), 'raw_files_opened': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', type=Path)
    parser.add_argument('--worker-gpu', type=int)
    args = parser.parse_args()
    if args.worker is None or args.worker_gpu is None:
        parser.error('public execution uses ppg-forward mcx-linear --config FILE --out DIR')
    worker(args.worker, args.worker_gpu)


if __name__ == '__main__':
    main()
