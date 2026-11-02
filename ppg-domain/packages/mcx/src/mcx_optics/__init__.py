"""Real MCX optical transport and absorption-only photon reweighting."""
import argparse
import datetime
import functools
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

__version__ = '0.1.0'


def _backend():
    import pmcx
    return pmcx


def doctor():
    try:
        p = _backend()
        if not hasattr(p, 'run'):
            raise RuntimeError('PMCX CUDA extension unavailable')
        gpu = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,uuid', '--format=csv,noheader'], text=True).strip().splitlines()
        return {'backend': 'PMCX CUDA', 'version': importlib.metadata.version('pmcx'),
                'gpu': gpu, 'available': bool(gpu)}
    except Exception as e:
        return {'backend': 'PMCX CUDA', 'available': False, 'error': str(e)}


def _config(cfg):
    geom = cfg['geometry']
    shape = geom['shape_voxels']
    unit = float(geom['voxel_mm'])
    if (len(shape) != 3 or any(not isinstance(v, int) or v <= 0 for v in shape)
            or not np.isfinite(unit) or unit <= 0):
        raise ValueError('shape must contain three positive integers and voxel_mm must be finite and positive')
    nphoton = cfg['nphoton']
    maxdet = cfg.get('maxdetphoton', nphoton)
    if any(not isinstance(v, int) or isinstance(v, bool) or v <= 0 for v in (nphoton, maxdet)):
        raise ValueError('nphoton and maxdetphoton must be positive integers')
    time_window = float(cfg['time_window_s'])
    detector = cfg['detector']
    radius = float(detector['radius_voxels'])
    if not np.isfinite(time_window) or time_window <= 0 or not np.isfinite(radius) or radius <= 0:
        raise ValueError('time window and detector radius must be finite and positive')
    for name, vector in [('source position', cfg['source']['position_voxels']),
                         ('source direction', cfg['source']['direction']),
                         ('detector position', detector['position_voxels'])]:
        a = np.asarray(vector, dtype=float)
        if a.shape != (3,) or not np.all(np.isfinite(a)):
            raise ValueError(f'{name} must have three finite coordinates')
        if name.endswith('position') and (np.any(a < 0) or np.any(a >= shape)):
            raise ValueError(f'{name} must lie within the volume')
        if name == 'source direction' and np.linalg.norm(a) == 0:
            raise ValueError('source direction must be nonzero')
    vol = np.zeros(shape, dtype=np.uint8)
    for layer in geom['layers']:
        if (not all(isinstance(layer[k], int) for k in ('z_start', 'z_end', 'label'))
                or not 0 <= layer['z_start'] < layer['z_end'] <= shape[2]
                or not 1 <= layer['label'] <= 255):
            raise ValueError('invalid layer bounds or label')
        vol[:, :, layer['z_start']:layer['z_end']] = layer['label']
    vessel = geom.get('vessel')
    if vessel:
        x, y, z = np.indices(shape)
        cy, cz = vessel['center_yz_voxels']
        if (not np.all(np.isfinite([cy, cz, vessel['radius_voxels']]))
                or vessel['radius_voxels'] <= 0 or not isinstance(vessel['label'], int)
                or not 1 <= vessel['label'] <= 255):
            raise ValueError('invalid vessel center, radius or label')
        mask = ((y-cy)**2 + (z-cz)**2 <= vessel['radius_voxels']**2)
        vol[mask] = vessel['label']
    props = np.asarray(cfg['optical_properties'], dtype=float)
    if props.ndim != 2 or props.shape[1] != 4 or not np.all(np.isfinite(props)) or vol.max() >= len(props):
        raise ValueError('invalid voxel size, optical properties or material labels')
    if np.any(props[:, :2] < 0) or np.any(props[:, 2] < 0) or np.any(props[:, 2] > 1) or np.any(props[:, 3] <= 0):
        raise ValueError('invalid optical properties [mua, mus, g, n]')
    d = cfg['detector']
    return {'vol': vol, 'prop': props, 'unitinmm': unit,
            'nphoton': nphoton, 'seed': int(cfg['seed']),
            'srcpos': cfg['source']['position_voxels'], 'srcdir': cfg['source']['direction'],
            'detpos': [[*d['position_voxels'], d['radius_voxels']]],
            'tstart': 0, 'tend': time_window, 'tstep': time_window,
            'issrcfrom0': 1, 'gpuid': cfg.get('gpuid', 1), 'autopilot': 1,
            'issaveseed': 1, 'issavedet': 1, 'savedetflag': 'dspw',
            'maxdetphoton': maxdet}


def _create(output):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    return out


def _manifest(out, cfg, kind, extra):
    content = json.dumps(cfg, indent=2, sort_keys=True, allow_nan=False)
    (out/'config.json').write_text(content+'\n')
    outputs = extra.get('outputs', [])
    hashes = {name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in outputs}
    record = {'run_id': out.name, 'type': kind, 'status': 'completed',
              'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'package_version': __version__, 'backend': 'PMCX CUDA', 'data_origin': 'simulated',
              'source_reference_commit': '49ec9f155107b7b54dece66d24e3c77a208cf2e8',
              'execution_class': 'real_mcx' if kind != 'absorption_reweight' else 'postprocessing_real_mcx',
              'backend_version': importlib.metadata.version('pmcx'),
              'config_sha256': hashlib.sha256(content.encode()).hexdigest(),
              'config': 'config.json', 'output_sha256': hashes, **extra}
    (out/'manifest.json').write_text(json.dumps(record, indent=2, default=str, allow_nan=False)+'\n')
    return record


def _record_failure(func):
    @functools.wraps(func)
    def wrapped(cfg, output):
        out = Path(output).resolve()
        existed = out.exists()
        try:
            return func(cfg, output)
        except Exception as exc:
            if not existed and out.is_dir():
                record = {'run_id': out.name, 'type': func.__name__, 'status': 'failed',
                          'timestamp_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          'data_origin': 'simulated', 'error': f'{type(exc).__name__}: {exc}'}
                (out/'manifest.json').write_text(json.dumps(record, indent=2)+'\n')
            raise
    return wrapped


def _reading(paths, w0, mua, n):
    if (not isinstance(n, (int, np.integer)) or n <= 0 or paths.ndim != 2
            or w0.shape != (paths.shape[0],) or not np.all(np.isfinite(paths))
            or not np.all(np.isfinite(w0)) or np.any(paths < 0) or np.any(w0 < 0)):
        raise ValueError('invalid detected paths, initial weights or launched photon count')
    weights = w0 * np.exp(-paths @ np.asarray(mua))
    mean = weights.sum() / n
    se = np.sqrt(max((np.square(weights).sum()/n - mean**2)/n, 0))
    if not np.isfinite(mean) or not np.isfinite(se):
        raise ValueError('nonfinite detector result')
    return float(mean), float(se)


@_record_failure
def run_simulation(cfg, output):
    """Run MCX and save detected per-medium path lengths (mm), initial weights and seeds."""
    out = _create(output)
    c = _config(cfg)
    c['flog'] = str(out/'mcx.log')
    r = _backend().mcxlab(c)
    det = r['detp']
    paths = np.asarray(det['ppath'], dtype=float) * c['unitinmm']
    w0 = np.asarray(det.get('w0', np.ones(len(paths))), dtype=float).reshape(-1)
    if len(w0) != len(paths):
        raise ValueError('unexpected initial weight dimensions')
    if len(paths) >= c['maxdetphoton']:
        raise RuntimeError('detected photon buffer may be truncated; increase maxdetphoton')
    np.savez_compressed(out/'detected.npz', paths_mm=paths, w0=w0,
                        detid=np.asarray(det['detid']), raw=np.asarray(det['data']),
                        seeds=np.asarray(r['seeds']))
    value, se = _reading(paths, w0, c['prop'][1:, 0], c['nphoton'])
    result = {'collected_fraction': value, 'standard_error': se,
              'detected_count': len(paths), 'launched_count': c['nphoton'],
              'detector_area_mm2': float(np.pi*(c['detpos'][0][3]*c['unitinmm'])**2)}
    result['reflectance_per_mm2'] = value/result['detector_area_mm2']
    if not all(np.isfinite(v) for v in result.values()) or result['detector_area_mm2'] <= 0:
        raise ValueError('nonfinite detector result or invalid detector area')
    (out/'reading.json').write_text(json.dumps(result, indent=2)+'\n')
    _manifest(out, cfg, 'simulation', {'seed': cfg['seed'], 'device': cfg.get('gpuid', 1),
             'outputs': ['detected.npz', 'reading.json', 'mcx.log'], 'units': {'path': 'mm', 'mua': '1/mm', 'time': 's'},
             'time_window_s': cfg['time_window_s'], 'parent_run_id': None,
             'assumptions': cfg.get('assumptions', []), 'parameter_source': cfg.get('parameter_source')})
    return result


@_record_failure
def reweight(cfg, output):
    """Reweight baseline run by new absorption coefficients, fixed geometry and mus/g/n."""
    out = _create(output)
    base = Path(cfg['baseline']).resolve()
    baseline = json.loads((base/'config.json').read_text())
    d = np.load(base/'detected.npz')
    n = baseline['nphoton']
    results = []
    if not cfg['cases']:
        raise ValueError('at least one absorption case is required')
    for case in cfg['cases']:
        mua = case['mua_per_mm']
        a = np.asarray(mua, dtype=float)
        if a.shape != (d['paths_mm'].shape[1],) or not np.all(np.isfinite(a)) or np.any(a < 0):
            raise ValueError('mua must provide one nonnegative value per medium')
        value, se = _reading(d['paths_mm'], d['w0'], mua, n)
        results.append({'name': case['name'], 'mua_per_mm': mua,
                        'collected_fraction': value, 'standard_error': se})
    (out/'readings.json').write_text(json.dumps(results, indent=2)+'\n')
    (out/'mcx.log').write_text('Post-processing saved real MCX detected photons; no new MCX launch.\n')
    _manifest(out, cfg, 'absorption_reweight', {'parent_run_id': base.name,
              'device': baseline.get('gpuid', 1), 'seed': baseline['seed'],
              'units': {'mua': '1/mm', 'collected_fraction': '1', 'standard_error': '1'},
              'input_detected_sha256': hashlib.sha256((base/'detected.npz').read_bytes()).hexdigest(),
              'outputs': ['readings.json', 'mcx.log'],
              'assumptions': ['fixed geometry, scattering, anisotropy, refractive index, source, detector, boundaries and TOF window']})
    return results


@_record_failure
def sensitivity(cfg, output):
    """Replay baseline photon seeds to calculate MCX spatial absorption Jacobian."""
    out = _create(output)
    base = Path(cfg['baseline']).resolve()
    baseline = json.loads((base/'config.json').read_text())
    d = np.load(base/'detected.npz')
    c = _config(baseline)
    c.update(seed=d['seeds'], detphotons=d['raw'], outputtype='jacobian',
             issavedet=0, flog=str(out/'mcx.log'))
    result = _backend().mcxlab(c)
    jacobian = np.asarray(result['flux'])
    if not np.all(np.isfinite(jacobian)):
        raise ValueError('nonfinite replay Jacobian')
    np.save(out/'jacobian.npy', jacobian)
    _manifest(out, cfg, 'photon_replay_jacobian', {'parent_run_id': base.name,
              'device': baseline.get('gpuid', 1), 'seed': baseline['seed'],
              'units': {'jacobian': 'mm', 'mua': '1/mm'},
              'input_detected_sha256': hashlib.sha256((base/'detected.npz').read_bytes()).hexdigest(),
              'outputs': ['jacobian.npy', 'mcx.log'],
              'normalization': 'MCX default Rytov: J = -d ln(collected_fraction) / d mua_voxel; units mm, voxelwise, at baseline',
              'working_point': str(base/'config.json')})
    return {'jacobian_shape': list(result['flux'].shape)}


def main():
    parser = argparse.ArgumentParser(prog='mcx')
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('doctor'); d.add_argument('--json', action='store_true')
    for name in ('simulate', 'reweight', 'sensitivity'):
        s = sub.add_parser(name); s.add_argument('--config', required=True); s.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'doctor':
            result = doctor()
            print(json.dumps(result, indent=2, default=str))
            return 0 if result['available'] else 1
        cfg = json.loads(Path(args.config).read_text())
        result = {'simulate': run_simulation, 'reweight': reweight, 'sensitivity': sensitivity}[args.command](cfg, args.output)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as e:
        print(f'{type(e).__name__}: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
