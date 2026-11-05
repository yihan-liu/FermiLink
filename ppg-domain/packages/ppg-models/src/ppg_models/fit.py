"""Case-shared model fitting with positive window-level amplitude profiling.

Optimization uses variance-normalized physical waveform residuals to identify
residual PTT. Foot-aligned ensemble NMSE is reported separately and is the
primary shape endpoint. Uniform declared model priors imply bounded fitting.
"""
from importlib import import_module

import numpy as np
from scipy.optimize import least_squares

from . import catheter
from . import operator as observation
from .waveform_metrics import window_metrics

MODEL_MODULES = {"M0": "m0_empirical", "M1": "m1_transmission",
                 "M2": "m2_nonlinear_pv", "M3": "m3_2r1c", "M4": "m4_line"}
EDGE_S = 2.0


def model_module(name):
    return import_module("ppg_models.models."+MODEL_MODULES[name])


def prepare_art(art, fs_hz, branch, catheter_params=None):
    """Use the identical 15 Hz eighth-power taper in both catheter branches.

    Match catheter.correct's constant padding and FFT length exactly, so the
    only branch difference is the declared inverse catheter response.
    """
    p = dict(catheter_params or {}, fs_hz=fs_hz, regularization_hz=15.)
    if branch == "corrected":
        return catheter.correct(art, p)
    if branch != "uncorrected":
        raise ValueError("branch must be corrected or uncorrected")
    return {"available": True,
            "art": catheter.bandlimit(art, fs_hz=fs_hz, regularization_hz=15.),
            "reason": None, "regularization_hz": 15.}



def profile_amplitude(predicted, observed, mask):
    """Positive nuisance gain and offset; no pressure/amplitude claim follows."""
    x, y = predicted[mask], observed[mask]
    xc, yc = x-x.mean(), y-y.mean()
    denom = np.dot(xc, xc)
    gain = max(float(np.dot(xc, yc)/denom), np.finfo(float).eps) if denom else 1.
    offset = float(y.mean()-gain*x.mean())
    return gain, offset


def _mask(window, operator_params):
    # One fixed support for every candidate: no optimizer-dependent NaN mask.
    fs = window.fs_hz
    t = np.arange(len(window.art))/fs
    max_delay = max(0., float(operator_params.get("device_delay_s", .4))
                    + observation.CASE_PTT_S_BOUNDS[1])
    mask = (t >= EDGE_S+max_delay) & (t < t[-1]-EDGE_S)
    if mask.sum() < fs:
        raise ValueError("Insufficient common interior support after edge/delay crop")
    return mask


def _predict(window, art, module, physiological, ptt_s, operator_params):
    p = dict(physiological, fs_hz=window.fs_hz)
    area = module.predict(art, p)
    op = dict(operator_params, fs_hz=window.fs_hz, ptt_s=ptt_s, gain=1., offset=0.)
    return observation.apply(area, op)


def fit_case(windows, model, operator_params, *, branch="uncorrected",
             catheter_params=None, fixed_physiology=None, initial=None,
             max_nfev=200, _fit_corners=False, fit_fs_hz=50,
             analysis_masks=None, evaluate=True):
    """Fit one case jointly; physiology and PTT shared, gain/offset per window.

    fixed_physiology fixes all model parameters for transfer-to-B, leaving
    residual PTT and profiled window gain/offset as the only adjustable values.
    Windows must belong to one case and match fit_fs_hz (50 or 500 Hz).
    Optional boolean analysis_masks intersect the fixed interior support.
    Predictions always filter each complete continuous window; masks apply
    only to amplitude profiling and residuals. evaluate=False skips the
    foot-aligned ensemble metrics.
    """
    if not windows or len({w.caseid for w in windows}) != 1:
        raise ValueError("Require at least one window from exactly one case")
    if fit_fs_hz not in (50, 500) or any(w.fs_hz != fit_fs_hz for w in windows):
        raise ValueError("All windows must match fit_fs_hz (50 or 500 Hz)")
    module = model_module(model)
    prepared = [prepare_art(w.art, w.fs_hz, branch, catheter_params) for w in windows]
    unavailable = next((p for p in prepared if not p["available"]), None)
    if unavailable is not None:
        return {"available": False, "reason": unavailable["reason"], "model": model,
                "branch": branch, "caseid": int(windows[0].caseid),
                "fit_fs_hz": fit_fs_hz}
    physiological_names = list(module.PARAM_NAMES) if fixed_physiology is None else []
    corner_names = ["lo_hz", "hi_hz"] if _fit_corners else []
    names = physiological_names+corner_names
    corner_bounds = {"lo_hz": (.05, 1.), "hi_hz": (5., 15.)}
    bounds = [module.PARAM_BOUNDS[k] for k in physiological_names]
    bounds += [corner_bounds[k] for k in corner_names]+[observation.CASE_PTT_S_BOUNDS]
    lo, hi = np.array(bounds).T
    start = dict(module.DEFAULT_PARAMS)
    start.update({k: operator_params[k] for k in corner_names})
    start.update(initial or {})
    x0 = np.array([start[k] for k in names]+[start.get("ptt_s", .15)])
    masks = [_mask(w, operator_params) for w in windows]
    if analysis_masks is not None:
        if len(analysis_masks) != len(windows):
            raise ValueError("Require one boolean analysis mask per window")
        for i, (w, supplied) in enumerate(zip(windows, analysis_masks)):
            supplied = np.asarray(supplied)
            if supplied.dtype != np.bool_ or supplied.shape != np.shape(w.art):
                raise ValueError("Analysis mask must be boolean and match its window")
            masks[i] &= supplied
            if masks[i].sum() < fit_fs_hz:
                raise ValueError("Insufficient analysis support after fixed interior crop")
    scales = [np.sqrt(np.sum((w.pleth[m]-w.pleth[m].mean())**2))
              for w, m in zip(windows, masks)]
    if any(s <= 0 for s in scales):
        raise ValueError("Flat target cannot support normalized fitting")

    def unpack(x):
        params = (dict(fixed_physiology) if fixed_physiology is not None
                  else dict(zip(physiological_names, x[:len(physiological_names)])))
        op = dict(operator_params)
        op.update(zip(corner_names, x[len(physiological_names):-1]))
        return params, float(x[-1]), op

    def residual(x):
        params, ptt, op = unpack(x)
        rows = []
        for w, a, mask, scale in zip(windows, prepared, masks, scales):
            prediction = _predict(w, a["art"], module, params, ptt, op)
            gain, offset = profile_amplitude(prediction, w.pleth, mask)
            rows.append((gain*prediction[mask]+offset-w.pleth[mask])/scale)
        return np.concatenate(rows)/np.sqrt(len(windows))

    x0 = np.clip(x0, lo+1e-9, hi-1e-9)
    best_start = x0
    best_loss = float(np.sum(residual(x0)**2))
    # Fixed PTT seeds escape the flat residual when positive gain clips at zero.
    n_ptt = int(np.ceil((hi[-1]-lo[-1])*windows[0].fs_hz))+1
    for ptt in np.linspace(lo[-1], hi[-1], n_ptt):
        candidate = x0.copy()
        candidate[-1] = np.clip(ptt, lo[-1]+1e-9, hi[-1]-1e-9)
        loss = float(np.sum(residual(candidate)**2))
        if loss < best_loss:
            best_start, best_loss = candidate, loss

    result = least_squares(residual, best_start,
                           bounds=(lo, hi), x_scale="jac", max_nfev=max_nfev,
                           ftol=1e-7, xtol=1e-7, gtol=1e-7)
    physiological, ptt, fitted_operator = unpack(result.x)
    fit = {"available": True, "model": model, "branch": branch,
           "caseid": int(windows[0].caseid),
           "physiology": {k: float(v) for k, v in physiological.items()},
           "ptt_s": ptt, "success": bool(result.success),
           "message": result.message, "nfev": int(result.nfev),
           "waveform_nmse": float(np.sum(result.fun**2)),
           "objective": "equal-window variance-normalized physical waveform residual",
           "priors": module.PARAM_PRIORS,
           "operator": {k: float(v) if isinstance(v, np.floating) else v
                        for k, v in fitted_operator.items()},
           "catheter_params": dict(catheter_params) if catheter_params else None,
           "fit_fs_hz": fit_fs_hz,
           "window_refs": [{"caseid": int(w.caseid), "start_s": float(w.start_s),
                            "end_s": float(w.end_s)} for w in windows],
           "fixed_physiology": fixed_physiology is not None,
           "bound_hits": {key: bool(abs(value-low) <= 1e-4*(high-low) or
                                    abs(value-high) <= 1e-4*(high-low))
                          for key, value, low, high in
                          zip(names+["ptt_s"], result.x, lo, hi)}}
    if evaluate:
        fit["windows"] = evaluate_case(windows, fit, fitted_operator,
                                      catheter_params=catheter_params)
    return fit


def evaluate_case(windows, fit, operator_params=None, *, catheter_params=None):
    """Evaluate fixed case physiology/PTT, at native 500 Hz for final features."""
    operator_params = fit["operator"] if operator_params is None else operator_params
    catheter_params = fit.get("catheter_params") if catheter_params is None else catheter_params
    module = model_module(fit["model"])
    rows = []
    for w in windows:
        prep = prepare_art(w.art, w.fs_hz, fit["branch"], catheter_params)
        if not prep["available"]:
            rows.append({"defined": False, "reason": prep["reason"]})
            continue
        pred = _predict(w, prep["art"], module, fit["physiology"], fit["ptt_s"],
                        operator_params)
        mask = _mask(w, operator_params)
        gain, offset = profile_amplitude(pred, w.pleth, mask)
        crop = np.flatnonzero(mask)
        a, b = crop[0], crop[-1]+1
        metric = window_metrics(w.pleth[a:b], (gain*pred+offset)[a:b], w.fs_hz)
        metric.update(caseid=int(w.caseid), start_s=float(w.start_s),
                      end_s=float(w.end_s), gain=gain, offset=offset,
                      map_mmHg=float(np.mean(w.art[mask])),
                      analysis_start_s=float(w.start_s+a/w.fs_hz),
                      analysis_end_s=float(w.start_s+b/w.fs_hz))
        rows.append(metric)
    return rows


def window_diagnostics(windows, model, operator_params, **kwargs):
    """Separate physiological fits for stability/MAP reporting, never primary."""
    return [fit_case([w], model, operator_params, **kwargs) for w in windows]
