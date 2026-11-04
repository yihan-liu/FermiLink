"""Round-2 explicit-list segment reading and Train-only scan selection.

The packet reader skips opaque transport bytes outside the listed window.
Only ART/PLETH samples inside that window become NumPy values.
"""
from dataclasses import dataclass, field
import gzip
import json
from pathlib import Path
import struct

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy.signal import resample_poly

def good_mask(d):
    g = (d.art_nan <= 0.05) & (d.ple_nan <= 0.05)
    for c in ["sbp", "dbp", "hr", "ibi_cv", "hr_ple", "ple_amp", "ple_clip", "ple_p95", "art_max"]:
        if c not in d:
            return pd.Series(False, index=d.index)
    g &= (d.dbp > 20) & (d.sbp < 250) & (d.art_max < 300) & (d.sbp - d.dbp >= 15)
    g &= d.hr.between(30, 180) & (d.ibi_cv < 0.3)
    g &= (d.ple_floor == 0) & (d.ple_clip < 0.1) & (d.ple_amp > 3) & (d.ple_p95 < 200)
    g &= (abs(d.hr_ple - d.hr) / d.hr < 0.1)
    return g.fillna(False)



RAW = Path("/data/liuyihan/database/VitalDB_raw/vital_dev")
EVENT_POLICY = "owner-20261104-drugpump-rate-nibp"
TRACKS = ("SNUADC/ART", "SNUADC/PLETH")
_DTYPES = {1: "<f4", 2: "<f8", 3: "i1", 4: "u1", 5: "<i2", 6: "<u2", 7: "<i4", 8: "<u4"}


@dataclass
class WindowAuthorization:
    windows: pd.DataFrame
    split_path: Path
    scan_dir: Path
    raw_dir: Path = RAW
    allow_splits: tuple = ("train",)
    event_policy: str | None = None
    recorded_events: dict = field(default_factory=dict)
    explicit_caseids: tuple = ()


@dataclass
class WindowData:
    time_s: np.ndarray
    art: np.ndarray
    pleth: np.ndarray
    fs_hz: float
    caseid: int
    start_s: float
    end_s: float


def allowed_cases(split_path, allow_splits=("train",)):
    """Validation is available only through explicit split opt-in."""
    allow_splits = tuple(str(v).lower() for v in allow_splits)
    if not allow_splits or set(allow_splits) - {"train", "validation"}:
        raise PermissionError("Only Train and explicit Validation are allowed")
    d = pd.read_csv(split_path)
    return d.loc[d.split.astype(str).str.lower().isin(allow_splits)
                 & (d.source_dir == "vital_dev"), "caseid"].astype(int).tolist()


def train_cases(split_path):
    return allowed_cases(split_path)


def _raw_path(caseid, raw_dir):
    supplied = Path(raw_dir)
    raw_dir = supplied.resolve()
    if "dev_reserve" in supplied.parts or "vital" in supplied.parts or raw_dir != RAW.resolve():
        raise PermissionError("Only explicit vital_dev source paths are allowed")
    path = raw_dir / f"{int(caseid):04d}.vital"
    resolved = path.resolve()
    if resolved.parent != raw_dir or "vital" in resolved.parts:
        raise PermissionError("Raw path escapes vital_dev")
    return path


def _skip(stream, size):
    """Discard compressed transport bytes without constructing sample values."""
    while size:
        chunk = stream.read(min(size, 65536))
        if not chunk:
            raise EOFError("Truncated VitalDB packet")
        size -= len(chunk)


def _string(buf, pos):
    size = struct.unpack_from("<I", buf, pos)[0]
    pos += 4
    return buf[pos:pos + size].decode("utf-8", "ignore"), pos + size


def _track(buf, devices):
    tid, kind, fmt = struct.unpack_from("<HBB", buf)
    name, pos = _string(buf, 4)
    _, pos = _string(buf, pos)
    # display min/max/color, sample rate, gain, offset, monitor type, device id
    rate = struct.unpack_from("<f", buf, pos + 12)[0]
    gain, offset = struct.unpack_from("<dd", buf, pos + 16)
    did = struct.unpack_from("<I", buf, pos + 33)[0] if len(buf) >= pos + 37 else 0
    full = devices.get(did, "") + "/" + name if did in devices else name
    return tid, (full, kind, fmt, rate, gain, offset)


def _read_window(path, start_s, end_s, *, tracks_wanted=TRACKS, raw_access_callback=None, caseid=None):
    """Decode only sample slices in [start_s,end_s); never use VitalFile.crop."""
    arrays = {}
    devices, tracks = {}, {}
    with gzip.open(path, "rb") as stream:
        if raw_access_callback is not None:
            raw_access_callback(str(path), caseid=caseid, start_s=float(start_s),
                                end_s=float(end_s), duration_s=float(end_s-start_s),
                                tracks=list(tracks_wanted), access_kind="waveform")
        if stream.read(4) != b"VITA":
            raise ValueError("Not a VitalDB file")
        stream.read(4)
        header = stream.read(struct.unpack("<H", stream.read(2))[0])
        if len(header) < 26:
            raise ValueError("Round-2 reader requires VitalDB timestamp header")
        origin = struct.unpack_from("<d", header, 10)[0]
        if origin <= 0:
            raise ValueError("Missing record origin; resolve metadata before waveform access")
        while True:
            packet = stream.read(5)
            if not packet:
                break
            kind, size = struct.unpack("<BI", packet)
            if kind == 9:
                buf = stream.read(size)
                did = struct.unpack_from("<I", buf)[0]
                devtype, pos = _string(buf, 4)
                name, _ = _string(buf, pos)
                devices[did] = name or devtype
            elif kind == 0:
                buf = stream.read(size)
                tid, trk = _track(buf, devices)
                tracks[tid] = trk
                if trk[0] in tracks_wanted:
                    if trk[1] != 1 or not np.isclose(trk[3], 500):
                        raise ValueError("Round 2 expects native 500 Hz SNUADC waveforms")
                    arrays[trk[0]] = np.full(round((end_s - start_s) * 500), np.nan)
            elif kind == 1:
                info = stream.read(min(12, size))
                if size < 12:
                    _skip(stream, size - len(info))
                    continue
                infolen, epoch, tid = struct.unpack("<HdH", info)
                pos = 2 + infolen
                if pos < 12 or pos > size:
                    raise ValueError("Invalid VitalDB record header")
                _skip(stream, pos - 12)
                trk = tracks.get(tid)
                if trk is None or trk[0] not in tracks_wanted:
                    _skip(stream, size - pos)
                    continue
                count = struct.unpack("<I", stream.read(4))[0]
                pos += 4
                name, _, fmt, rate, gain, offset = trk
                dtype = np.dtype(_DTYPES[fmt])
                rel = epoch - origin
                # Integer indices select only native samples in the allowed interval.
                lo = max(0, int(np.ceil((start_s - rel) * rate - 1e-6)))
                hi = min(count, int(np.ceil((end_s - rel) * rate - 1e-6)))
                if hi <= lo:
                    _skip(stream, size - pos)
                    continue
                _skip(stream, lo * dtype.itemsize)
                raw = stream.read((hi - lo) * dtype.itemsize)
                values = np.frombuffer(raw, dtype=dtype).astype(float)
                if fmt > 2:
                    values = values * gain + offset
                dst = int(round((rel + lo / rate - start_s) * rate))
                arrays[name][dst:dst + len(values)] = values
                _skip(stream, size - pos - hi * dtype.itemsize)
            else:
                _skip(stream, size)
    if set(arrays) != set(tracks_wanted):
        raise ValueError("Requested SNUADC tracks are required")
    if any(not np.isfinite(v).all() for v in arrays.values()):
        raise ValueError("Window contains missing or nonfinite samples")
    return arrays


def _authorized_event(caseid, start_s, end_s, authorization):
    _raw_path(caseid, authorization.raw_dir)
    if caseid not in allowed_cases(authorization.split_path, authorization.allow_splits):
        raise PermissionError("Case is outside the explicitly allowed vital_dev splits")
    w = authorization.windows
    listed = ((w.caseid == caseid)
              & np.isclose(w.start_s, start_s, atol=1e-8, rtol=0)
              & np.isclose(w.end_s, end_s, atol=1e-8, rtol=0))
    if not listed.any():
        raise PermissionError("Interval is absent from the explicit approved list")
    event = json.loads((Path(authorization.scan_dir) / "events" / f"{caseid}.json").read_text())
    if not (0 <= start_s < end_s <= .8 * event["dur_s"]):
        raise PermissionError("Interval must lie wholly inside the first 80%")
    return event


def _load(caseid, start_s, end_s, *, authorization, fs_hz, tracks_wanted,
          raw_access_callback=None):
    caseid = int(caseid)
    if fs_hz not in (50, 500):
        raise ValueError("Round 2 supports 50 or 500 Hz")
    event = _authorized_event(caseid, start_s, end_s, authorization)
    if "SNUADC/PLETH" in tracks_wanted:
        if caseid not in authorization.recorded_events:
            authorization.recorded_events[caseid] = read_recorded_events(caseid,
                authorization=authorization, event=event, raw_access_callback=raw_access_callback)
        event = authorization.recorded_events[caseid]
        for a, b in event_exclusions(event, policy=authorization.event_policy):
            if start_s < b and end_s > a:
                raise PermissionError("PLETH interval overlaps an excluded event")
    path = _raw_path(caseid, authorization.raw_dir)
    arrays = _read_window(path, start_s, end_s, tracks_wanted=tracks_wanted,
                          raw_access_callback=raw_access_callback, caseid=caseid)
    if fs_hz == 50:
        arrays = {k: resample_poly(v, 1, 10) for k, v in arrays.items()}
    time = start_s + np.arange(len(arrays[TRACKS[0]])) / fs_hz
    return WindowData(time, arrays[TRACKS[0]], arrays.get(TRACKS[1]), fs_hz,
                      caseid, start_s, end_s)


def load_window(caseid, start_s, end_s, *, authorization, fs_hz=50,
                raw_access_callback=None):
    """Read one approved exact ART/PLETH interval; raw data stay in place."""
    return _load(caseid, start_s, end_s, authorization=authorization, fs_hz=fs_hz,
                 tracks_wanted=TRACKS, raw_access_callback=raw_access_callback)


def load_art_window(caseid, start_s, end_s, *, authorization, fs_hz=500,
                    raw_access_callback=None):
    """Read an approved catheter-inspection interval decoding ART only."""
    return _load(caseid, start_s, end_s, authorization=authorization, fs_hz=fs_hz,
                 tracks_wanted=TRACKS[:1], raw_access_callback=raw_access_callback)


def load_selected_windows(segments_dir, fs_hz=500, raw_access_callback=None):
    directory = Path(segments_dir)
    meta = json.loads((directory / "selection.json").read_text())
    windows = pd.read_csv(directory / "windows.csv")
    auth = WindowAuthorization(windows, Path(meta["split_path"]), Path(meta["scan_dir"]),
                               Path(meta["raw_dir"]), tuple(meta["allow_splits"]),
                               meta["event_policy"])
    for row in windows.itertuples(index=False):
        yield load_window(row.caseid, row.start_s, row.end_s, authorization=auth,
                          fs_hz=fs_hz, raw_access_callback=raw_access_callback)


def _is_pump_rate(name):
    device, _, track = name.partition("/")
    return track.upper().endswith("_RATE") and (
        device.lower() == "orchestra" or device.lower().startswith("drugpump")
        or track.lower().startswith("drugpump"))


def _read_numeric_rates(path, end_s, *, caseid, raw_access_callback=None):
    """Read only recorded pump scalars in first80; skip all waveform payloads.

    Empty/missing tracks describe recorded coverage, never drug absence.
    """
    devices, tracks, rates = {}, {}, {}
    with gzip.open(path, "rb") as stream:
        if raw_access_callback is not None:
            raw_access_callback(str(path), caseid=caseid, start_s=0.,
                end_s=float(end_s), duration_s=float(end_s),
                tracks=["Orchestra/*_RATE", "drugpump*/*_RATE", "*/drugpump*_RATE"],
                access_kind="numeric-events")
        if stream.read(4) != b"VITA":
            raise ValueError("Not a VitalDB file")
        stream.read(4)
        header = stream.read(struct.unpack("<H", stream.read(2))[0])
        if len(header) < 26:
            raise ValueError("Missing VitalDB timestamp header")
        origin = struct.unpack_from("<d", header, 10)[0]
        if origin <= 0:
            raise ValueError("Missing record origin")
        while True:
            packet = stream.read(5)
            if not packet:
                break
            kind, size = struct.unpack("<BI", packet)
            if kind == 9:
                buf = stream.read(size)
                did = struct.unpack_from("<I", buf)[0]
                devtype, pos = _string(buf, 4)
                name, _ = _string(buf, pos)
                devices[did] = name or devtype
            elif kind == 0:
                tid, trk = _track(stream.read(size), devices)
                tracks[tid] = trk
                if trk[1] == 2 and _is_pump_rate(trk[0]):
                    rates.setdefault(trk[0], [])
            elif kind == 1:
                info = stream.read(min(12, size))
                if size < 12:
                    continue
                infolen, epoch, tid = struct.unpack("<HdH", info)
                pos = 2 + infolen
                if pos < 12 or pos > size:
                    raise ValueError("Invalid VitalDB record header")
                _skip(stream, pos - 12)
                trk = tracks.get(tid)
                rel = epoch - origin
                if trk is None or trk[1] != 2 or trk[0] not in rates or not 0 <= rel < end_s:
                    _skip(stream, size - pos)
                    continue
                dtype = np.dtype(_DTYPES[trk[2]])
                if size - pos < dtype.itemsize:
                    raise ValueError("Truncated pump scalar")
                value = struct.unpack("<" + dtype.char, stream.read(dtype.itemsize))[0]
                rates[trk[0]].append((float(rel), float(value)))
                _skip(stream, size - pos - dtype.itemsize)
            else:
                _skip(stream, size)
    return {name: sorted(records, key=lambda r: r[0]) for name, records in rates.items()}


def read_recorded_events(caseid, *, authorization, event=None, raw_access_callback=None):
    """Authorize before opening raw; collect scalar rates plus recorded scan NIBP.

    NIBP uses Round1 Solar8000/NIBP_SBP dedup: changed value or >120 s since
    the immediately preceding sample. Repeats do not prove new measurements.
    """
    caseid = int(caseid)
    path = _raw_path(caseid, authorization.raw_dir)
    if caseid not in allowed_cases(authorization.split_path, authorization.allow_splits):
        raise PermissionError("Case is outside the explicitly allowed vital_dev splits")
    listed = set(authorization.explicit_caseids)
    if "caseid" in authorization.windows:
        listed.update(authorization.windows.caseid.astype(int))
    if caseid not in listed:
        raise PermissionError("Numeric pass requires an explicit case list")
    if authorization.event_policy != EVENT_POLICY:
        raise ValueError("An explicit owner-20261104 event policy is required")
    if event is None:
        event = json.loads((Path(authorization.scan_dir) / "events" / f"{caseid}.json").read_text())
    result = dict(event)
    result["recorded_pump_rates"] = _read_numeric_rates(path, .8 * event["dur_s"],
        caseid=caseid, raw_access_callback=raw_access_callback)
    return result


def event_exclusions(event, *, policy, flush_pad_s=10):
    """Recorded active infusion, all changes +/-600 s, NIBP +/-60 s, flush +/-10 s.

    Initial status before a recorded track's first sample is unknown and
    excluded. First positive value is an initial state, not a rate change.
    Nonfinite status is unknown until the next finite reading.
    """
    if policy != EVENT_POLICY:
        raise ValueError("An explicit owner-20261104 event policy is required")
    if "recorded_pump_rates" not in event:
        raise ValueError("Numeric-only recorded pump pass is required before PLETH access")
    end = .8 * event["dur_s"]
    blocked = []
    for records in event["recorded_pump_rates"].values():
        records = [(float(t), float(v)) for t, v in records if 0 <= t < end]
        if not records:
            blocked.append((0., end))
            continue
        records.sort(key=lambda r: r[0])
        if records[0][0] > 0:
            blocked.append((0., records[0][0]))
        prev = None
        for i, (t, value) in enumerate(records):
            next_t = records[i + 1][0] if i + 1 < len(records) else end
            if not np.isfinite(value) or value > 0:
                blocked.append((t, next_t))
            if prev is not None and np.isfinite(prev) and np.isfinite(value) and value != prev:
                blocked.append((max(0., t - 600.), min(end, t + 600.)))
            prev = value
    blocked += [(max(0., v["t_s"] - 60.), min(end, v["t_s"] + 60.))
                for v in event.get("events", []) if v["kind"] == "nibp" and 0 <= v["t_s"] < end]
    blocked += [(max(0., f["t_s"] - flush_pad_s), min(end, f["t_s"] + f["dur_s"] + flush_pad_s))
                for f in event.get("flush", []) if 0 <= f["t_s"] < end]
    return [(a, b) for a, b in blocked if a < b]


def early_catheter(event):
    fits = [f for f in event["flush"] if f["t_s"] + f["dur_s"] + .5 <= .8 * event["dur_s"]
            and np.isfinite(f["fn_hz"]) and np.isfinite(f["zeta"])]
    if not fits:
        return np.nan, np.nan, "unknown"
    return float(np.median([f["fn_hz"] for f in fits])), float(np.median([f["zeta"] for f in fits])), "early_event_unverified"


def gain_step_flags(d, factor):
    """Flag extreme amplitude changes at adjacent original 10 s bins."""
    jump = (np.abs(np.log(d.ple_amp / d.ple_amp.shift())) > np.log(factor)) & (d.t_s.diff() == 10)
    return (jump | jump.shift(-1, fill_value=False)).fillna(False)


def case_scan_bins(caseid, *, scan_dir, ibi_cv_cutoff, event_policy, recorded_events):
    event = recorded_events
    blocked = event_exclusions(event, policy=event_policy)
    path = Path(scan_dir) / "windows" / f"{caseid}.parquet"
    # Read ART/time only first; discard disallowed intervals before any PLETH columns.
    art_cols = ["t_s", "art_nan", "dbp", "sbp", "art_max", "hr", "ibi_cv", "map"]
    have = pq.read_schema(path).names
    d = pd.read_parquet(path, columns=[c for c in art_cols if c in have],
                        filters=[("t_s", ">=", 0), ("t_s", "<=", .8 * event["dur_s"] - 10)]).reindex(columns=art_cols)
    initial_bins = len(d)
    for a, b in blocked:
        d = d.loc[~((d.t_s < b) & (d.t_s + 10 > a))]
    if d.empty:
        d.attrs.update(first80_bins=initial_bins, event_excluded_bins=initial_bins)
        return d
    ple_cols = ["t_s", "ple_nan", "ple_floor", "ple_clip", "ple_amp", "ple_p95", "hr_ple"]
    p = pd.read_parquet(path, columns=[c for c in ple_cols if c in have],
                        filters=[("t_s", "in", d.t_s.tolist())]).reindex(columns=ple_cols)
    d = d.merge(p, on="t_s").sort_values("t_s").reset_index(drop=True)
    d["quality_ok"] = good_mask(d) & (d.ibi_cv <= ibi_cv_cutoff) & (d.art_nan == 0) & (d.ple_nan == 0)
    d.attrs.update(first80_bins=initial_bins, event_excluded_bins=initial_bins-len(d))
    return d


def calibrate_gain_step(case_bins):
    """Freeze Train-only pilot amplitude screening before any model fit."""
    values = []
    for d in case_bins:
        if d.empty:
            continue
        valid = d.quality_ok & d.quality_ok.shift(fill_value=False) & (d.t_s.diff() == 10)
        delta = np.abs(np.log(d.ple_amp / d.ple_amp.shift()))
        values.extend(delta.loc[valid & np.isfinite(delta)].tolist())
    if not values:
        raise ValueError("Train gain calibration requires valid adjacent 10s quality-bin pairs")
    quantile = float(np.quantile(values, .995))
    return dict(mode="train-p995", quantile=.995, abs_log_amplitude_quantile=quantile,
                factor=max(1.5, float(np.exp(quantile))), valid_pairs=len(values),
                interpretation="extreme amplitude-step screening; not proven AGC")


def case_candidates(caseid, *, scan_dir, ibi_cv_cutoff, gain_step_factor, event_policy,
                    recorded_events, scan_bins=None):
    event = recorded_events
    d = case_scan_bins(caseid, scan_dir=scan_dir, ibi_cv_cutoff=ibi_cv_cutoff,
                      event_policy=event_policy, recorded_events=event) if scan_bins is None else scan_bins.copy()
    if d.empty:
        return pd.DataFrame()
    d["gain_step_flag"] = gain_step_flags(d, gain_step_factor)
    fn, zeta, status = early_catheter(event)
    rows = []
    for i in range(len(d) - 2):
        q = d.iloc[i:i + 3]
        if not ((q.t_s.diff().iloc[1:] == 10).all() and q.quality_ok.all() and not q.gain_step_flag.any()):
            continue
        rows.append(dict(caseid=caseid, start_s=float(q.t_s.iloc[0]), end_s=float(q.t_s.iloc[-1] + 10),
                         MAP=float(q["map"].mean()), HR=float(q.hr.median()), zeta=zeta, fn_hz=fn,
                         catheter_status=status, frequency_kind="ring_peak", quality_ok=True, ibi_cv=float(q.ibi_cv.max()),
                         gain_step_flag=False))
    return pd.DataFrame(rows)


def choose_windows(d, count=3, spacing_s=600):
    """Prioritize the largest MAP-separated pair, then fill separated windows."""
    if d.empty:
        return d
    d = d.sort_values("start_s").reset_index(drop=True)
    best_pair, best_delta = [], -1
    low = high = None
    j = 0
    for i in range(len(d)):
        while j < i and d.start_s.iloc[j] <= d.start_s.iloc[i] - spacing_s:
            if low is None or d.MAP.iloc[j] < d.MAP.iloc[low]:
                low = j
            if high is None or d.MAP.iloc[j] > d.MAP.iloc[high]:
                high = j
            j += 1
        for other in (low, high):
            if other is not None and abs(d.MAP.iloc[i] - d.MAP.iloc[other]) > best_delta:
                best_pair, best_delta = [other, i], abs(d.MAP.iloc[i] - d.MAP.iloc[other])
    chosen = best_pair if best_pair else [int(d.ibi_cv.idxmin())]
    while len(chosen) < count:
        gap = np.min(np.abs(d.start_s.to_numpy()[:, None] - d.start_s.iloc[chosen].to_numpy()), axis=1)
        available = np.flatnonzero(gap >= spacing_s)
        if not len(available):
            break
        chosen.append(int(available[np.argmax(gap[available])]))
    result = d.iloc[chosen[:count]].sort_values("start_s").copy()
    result["map_pair_ge15"] = bool(best_delta >= 15)
    return result


def stratified_cases(cases, count):
    """Round-robin MAP/HR tertiles and zeta strata; quantile edges are reported."""
    cases = cases.copy()
    for source, target in (("MAP", "map_tertile"), ("HR", "hr_tertile")):
        cases[target] = pd.cut(cases[source].rank(method="first", pct=True), [0, 1/3, 2/3, 1], labels=["low", "mid", "high"])
    cases["zeta_stratum"] = np.where(cases.zeta.isna(), "unknown", np.where(cases.zeta < .3, "lt0.3", "ge0.3"))
    groups = [list(g.sort_values(["map_pair_ge15", "caseid"], ascending=[False, True]).caseid)
              for _, g in cases.groupby(["map_tertile", "hr_tertile", "zeta_stratum"], observed=True, sort=True)]
    chosen = []
    while groups and len(chosen) < count:
        next_groups = []
        for g in groups:
            if len(chosen) < count:
                chosen.append(g.pop(0))
            if g:
                next_groups.append(g)
        groups = next_groups
    return cases.loc[cases.caseid.isin(chosen)]
