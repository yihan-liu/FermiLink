"""Round-3 within-case slopes and autocorrelation-preserving MAP controls."""
import warnings

import numpy as np
import pandas as pd
from statsmodels.regression.mixed_linear_model import MixedLM


def _number(value):
    return float(value) if np.isfinite(value) else None


def _case_id(value):
    return value.item() if isinstance(value, np.generic) else value


def _design(d):
    values = d[["map_mmHg", "hr_bpm", "timestamp_s"]].to_numpy(dtype=float)
    centered = values - values.mean(axis=0)
    return np.column_stack((np.ones(len(d)), centered / [10., 10., 3600.]))


def _ols(x, y):
    if len(y) <= x.shape[1] or np.linalg.matrix_rank(x) < x.shape[1]:
        return None
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return beta, y - x @ beta


def _bartlett_hac(x, residual, timestamps, bandwidth_s):
    """Unadjusted OLS sandwich using actual seconds, including gaps."""
    scores = x * residual[:, None]
    distance = np.abs(timestamps[:, None] - timestamps[None, :])
    weight = np.maximum(0., 1. - distance / bandwidth_s)
    bread = np.linalg.inv(x.T @ x)
    return bread @ (scores.T @ weight @ scores) @ bread


def _run_slices(timestamps):
    boundaries = np.r_[0, np.flatnonzero(~np.isclose(
        np.diff(timestamps), 120., atol=1e-8, rtol=0)) + 1, len(timestamps)]
    return [slice(int(a), int(b)) for a, b in zip(boundaries[:-1], boundaries[1:])]


def _shift_residuals(residual, timestamps, min_shift_s, rng):
    """Circularly shift each 120 s run; both circular directions meet the minimum."""
    minimum = int(np.ceil(min_shift_s / 120.))
    runs = _run_slices(timestamps)
    short = sum((run.stop - run.start) < 2 * minimum for run in runs)
    if short:
        return None, len(runs), []
    shifted = residual.copy()
    offsets = []
    for run in runs:
        n = run.stop - run.start
        offset = int(rng.integers(minimum, n - minimum + 1))
        shifted[run] = np.roll(residual[run], offset)
        offsets.append(offset)
    return shifted, len(runs), offsets


def _variance(x, y):
    full = _ols(x, y)
    if full is None:
        return None
    reduced = x[:, [0, 3]]
    residual_time = y - reduced @ np.linalg.lstsq(reduced, y, rcond=None)[0]
    sse_time = float(residual_time @ residual_time)
    sse_full = float(full[1] @ full[1])
    return dict(sse_time=sse_time, sse_time_map_hr=sse_full,
                explained_fraction=_number(1. - sse_full / sse_time) if sse_time > 0 else None)


def decompose_feature(df, feature, *, hac_bandwidth_s, shuffle_min_shift_s,
                      n_shuffles, seed):
    """Fit case-centered MAP/HR/time effects; all bandwidths are explicit.

    MAP/HR designs use units of 10 mmHg/10 bpm and time uses hours.
    Reported slopes and HAC SEs use mmHg/bpm. Main per-case slopes are
    unshrunk OLS; mixed-model conditional slopes are reported separately.
    Q4 retains shiftable continuous runs and refits MAP background and observed
    slopes on that fixed subset. Control shifts use those identical rows.
    """
    if not np.isfinite(hac_bandwidth_s) or hac_bandwidth_s <= 0:
        raise ValueError("hac_bandwidth_s must be explicitly positive")
    if not np.isfinite(shuffle_min_shift_s) or shuffle_min_shift_s <= 0:
        raise ValueError("shuffle_min_shift_s must be explicitly positive")
    if not isinstance(n_shuffles, (int, np.integer)) or n_shuffles < 1:
        raise ValueError("n_shuffles must be a positive integer")
    columns = ["caseid", "timestamp_s", "map_mmHg", "hr_bpm", feature]
    data = df.loc[:, columns].copy()
    data["_input_row"] = np.arange(len(data))
    finite = np.isfinite(data[columns[1:]].to_numpy(dtype=float)).all(axis=1) & data.caseid.notna()
    data = data.loc[finite].sort_values(["caseid", "timestamp_s"])
    output = dict(feature=feature, coverage=dict(input_windows=len(df),
        finite_windows=len(data), excluded_nonfinite_windows=int((~finite).sum()),
        input_cases=int(df.caseid.nunique()), finite_cases=int(data.caseid.nunique())),
        design="within-case centered MAP/10, HR/10, time_hours; intercept",
        hac=dict(bandwidth_s=float(hac_bandwidth_s), kernel="Bartlett actual timestamp distance",
                 finite_sample_correction=False), per_case=[])
    groups = []
    pooled_full = pooled_time = 0.
    variance_cases = []
    for cid, d in data.groupby("caseid", sort=True):
        x, y = _design(d), d[feature].to_numpy(dtype=float)
        times = d.timestamp_s.to_numpy(dtype=float)
        fitted = _ols(x, y)
        row = dict(caseid=_case_id(cid), n_windows=len(d), defined=fitted is not None)
        if fitted is None:
            row["reason"] = "insufficient_residual_df_or_rank_deficient_design"
        else:
            beta, residual = fitted
            covariance = _bartlett_hac(x, residual, times, float(hac_bandwidth_s))
            se = np.sqrt(np.maximum(0., np.diag(covariance)))
            row.update(intercept=_number(beta[0]), map_slope_per_mmhg=_number(beta[1]/10),
                map_slope_se_per_mmhg=_number(se[1]/10),
                hr_slope_per_bpm=_number(beta[2]/10), hr_slope_se_per_bpm=_number(se[2]/10),
                time_slope_per_hour=_number(beta[3]), time_slope_se_per_hour=_number(se[3]))
            variance = _variance(x, y)
            variance_cases.append(dict(caseid=_case_id(cid), **variance))
            pooled_full += variance["sse_time_map_hr"]
            pooled_time += variance["sse_time"]
        groups.append((cid, d, x, y, times, fitted))
        output["per_case"].append(row)
    finite_caseids = set(data.caseid)
    for cid in df.caseid.dropna().unique():
        if cid not in finite_caseids:
            output["per_case"].append(dict(caseid=_case_id(cid), n_windows=0,
                defined=False, reason="no_finite_windows"))
    output["variance_explained"] = dict(per_case=variance_cases,
        pooled=dict(sse_time=pooled_time, sse_time_map_hr=pooled_full,
                    explained_fraction=_number(1. - pooled_full/pooled_time) if pooled_time > 0 else None),
        interpretation="descriptive added MAP/HR fit beyond case-specific intercept and time",
        estimable_cases=len(variance_cases))

    mixed = dict(defined=False, converged=False, warnings=[], conditional_case_slopes=[])
    output["mixed_model"] = mixed
    if len(groups) < 2:
        mixed["reason"] = "requires_at_least_two_cases"
    else:
        x = np.concatenate([g[2] for g in groups])
        y = np.concatenate([g[3] for g in groups])
        labels = np.concatenate([np.full(len(g[1]), i) for i, g in enumerate(groups)])
        if np.linalg.matrix_rank(x) < x.shape[1]:
            mixed["reason"] = "rank_deficient_fixed_design"
        else:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    result = MixedLM(y, x, groups=labels, exog_re=x[:, :3]).fit(
                        method="lbfgs", reml=True, disp=False)
                    mixed.update(defined=True, converged=bool(result.converged),
                        method="REML MixedLM lbfgs; random intercept and MAP/HR slopes",
                        fixed_effects=dict(intercept=_number(result.fe_params[0]),
                            map_slope_per_mmhg=_number(result.fe_params[1]/10),
                            hr_slope_per_bpm=_number(result.fe_params[2]/10),
                            time_slope_per_hour=_number(result.fe_params[3])),
                        fixed_effect_se=dict(intercept=_number(result.bse_fe[0]),
                            map_slope_per_mmhg=_number(result.bse_fe[1]/10),
                            hr_slope_per_bpm=_number(result.bse_fe[2]/10),
                            time_slope_per_hour=_number(result.bse_fe[3])))
                    if not result.converged:
                        mixed["reason"] = "optimizer_did_not_converge"
                    try:
                        effects = result.random_effects
                        mixed["conditional_case_slopes"] = [dict(caseid=_case_id(g[0]),
                            map_slope_per_mmhg=_number((result.fe_params[1] + np.asarray(effects[i])[1])/10),
                            hr_slope_per_bpm=_number((result.fe_params[2] + np.asarray(effects[i])[2])/10))
                            for i, g in enumerate(groups)]
                    except (ValueError, np.linalg.LinAlgError) as exc:
                        mixed["conditional_slopes_reason"] = str(exc)
                except (ValueError, np.linalg.LinAlgError) as exc:
                    mixed["reason"] = str(exc)
                mixed["warnings"] = [str(w.message) for w in caught]

    rng = np.random.default_rng(seed)
    shuffled, matched, observed, rejected, q4_cases = [], [], [], [], []
    total_runs = short_runs = retained_windows = 0
    for cid, d, x, y, times, fitted in groups:
        runs = _run_slices(times)
        minimum = int(np.ceil(shuffle_min_shift_s/120.))
        keep_runs = [(i, run) for i, run in enumerate(runs)
                     if run.stop-run.start >= 2*minimum]
        total_runs += len(runs)
        short_runs += len(runs)-len(keep_runs)
        indices = np.concatenate([np.arange(run.start, run.stop) for _, run in keep_runs]) if keep_runs else np.array([], dtype=int)
        subset = d.iloc[indices]
        retained_windows += len(subset)
        run_ids = [run_id for run_id, run in keep_runs for _ in range(run.stop-run.start)]
        detail = dict(caseid=_case_id(cid), main_windows=len(d), subset_windows=len(subset),
            subset_input_rows=subset["_input_row"].astype(int).tolist(),
            subset_timestamps_s=subset.timestamp_s.astype(float).tolist(),
            subset_run_ids=run_ids, defined=False, shifts=[])
        q4_cases.append(detail)
        if subset.empty:
            detail["reason"] = "no_shiftable_contiguous_runs"
            rejected.append(dict(caseid=_case_id(cid), reason=detail["reason"]))
            continue
        subset_x = _design(subset)
        subset_y = subset[feature].to_numpy(dtype=float)
        subset_times = subset.timestamp_s.to_numpy(dtype=float)
        observed_fit = _ols(subset_x, subset_y)
        if observed_fit is None:
            detail["reason"] = "insufficient_residual_df_or_rank_deficient_subset"
            rejected.append(dict(caseid=_case_id(cid), reason=detail["reason"]))
            continue
        detail["observed_map_slope_per_mmhg"] = float(observed_fit[0][1]/10.)
        background = subset_x[:, [0, 2, 3]]
        map_values = subset.map_mmHg.to_numpy(dtype=float)
        map_fitted = background @ np.linalg.lstsq(background, map_values, rcond=None)[0]
        map_residual = map_values - map_fitted
        slopes = []
        for iteration in range(n_shuffles):
            shifted, _, offsets = _shift_residuals(map_residual, subset_times, shuffle_min_shift_s, rng)
            shifted_map = map_fitted + shifted
            shuffled_x = subset_x.copy()
            shuffled_x[:, 1] = (shifted_map-shifted_map.mean())/10.
            fit = _ols(shuffled_x, subset_y)
            slope = float(fit[0][1]/10.) if fit is not None else None
            slopes.append(slope)
            detail["shifts"].append(dict(iteration=iteration,
                offsets=[dict(run_id=run_id, samples=offset, seconds=120*offset)
                         for (run_id, _), offset in zip(keep_runs, offsets)],
                map_slope_per_mmhg=slope,
                defined=fit is not None))
        if any(slope is None for slope in slopes):
            detail["reason"] = "rank_deficient_shuffled_design"
            rejected.append(dict(caseid=_case_id(cid), reason=detail["reason"]))
            continue
        detail["defined"] = True
        shuffled.append(slopes)
        matched.append(_case_id(cid))
        observed.append(detail["observed_map_slope_per_mmhg"])
    q4 = dict(defined=bool(matched), n_shuffles=int(n_shuffles), seed=_case_id(seed),
        min_shift_s=float(shuffle_min_shift_s), grid_s=120,
        method="MAP residual after subset HR/time regression; circular shift within each retained continuous run",
        interpretation="conditional association diagnostic on shiftable runs; approximate stationarity required",
        total_runs=total_runs, short_runs=short_runs, retained_windows=retained_windows,
        finite_windows=len(data), cases=q4_cases, matched_caseids=matched,
        matched_cases=len(matched), excluded_cases=rejected)
    if matched:
        array = np.asarray(shuffled)
        q4.update(observed_median_map_slope_per_mmhg=float(np.median(observed)),
            observed_negative_fraction=float(np.mean(np.asarray(observed) < 0)),
            median_map_slope_per_mmhg=np.median(array, axis=0).tolist(),
            negative_fraction=np.mean(array < 0, axis=0).tolist())
    else:
        q4["reason"] = "no_estimable_cases_with_shiftable_runs"
    output["q4"] = q4
    return output
