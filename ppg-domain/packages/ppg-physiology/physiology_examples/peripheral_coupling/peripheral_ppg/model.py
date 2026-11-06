"""2R1C model, pressure mmHg, volume mL, time s."""
import math


def local_model(time_s, pressure_mmHg, cfg):
    """Exact piecewise-linear-input solution; return P, inlet/outlet Q and V.

    Pressure is linearly interpolated between supplied samples. No transport
    delay or feedback to the systemic solver is represented.
    """
    rin, rout, c = (float(cfg[k]) for k in ("R_in_mmHg_s_per_mL", "R_out_mmHg_s_per_mL", "C_mL_per_mmHg"))
    if not all(math.isfinite(x) and x > 0 for x in (rin, rout, c)):
        raise ValueError("R_in, R_out and C must be positive")
    if len(time_s) != len(pressure_mmHg) or len(time_s) < 2:
        raise ValueError("at least two aligned pressure samples are required")
    pv, pref, vref, p = (float(cfg[k]) for k in ("P_venous_mmHg", "P_ref_mmHg", "V_ref_mL", "P_initial_mmHg"))
    if not all(math.isfinite(x) for x in (pv, pref, vref, p)) or vref <= 0:
        raise ValueError("reference and initial values must be finite and reference volume positive")
    tau = c * rin * rout / (rin + rout)
    alpha = rout / (rin + rout)
    beta = rin / (rin + rout)
    result = []
    for i, (t, pin) in enumerate(zip(time_s, pressure_mmHg)):
        t, pin = float(t), float(pin)
        if not math.isfinite(t) or not math.isfinite(pin):
            raise ValueError("time and pressure must be finite")
        if i:
            dt = t - float(time_s[i-1])
            if dt <= 0:
                raise ValueError("time must be strictly increasing")
            target0 = alpha * float(pressure_mmHg[i-1]) + beta * pv
            slope = alpha * (pin - float(pressure_mmHg[i-1])) / dt
            decay = math.exp(-dt/tau)
            p = target0 + slope * (dt - tau) + (p - target0 + slope * tau) * decay
        volume = vref+c*(p-pref)
        if not math.isfinite(volume) or volume <= 0:
            raise ValueError(f"local volume must be finite and positive at {t} s; check initial/reference parameters")
        result.append({"time_s": t, "P_in_mmHg": pin, "P_local_mmHg": p,
                       "Q_in_mL_per_s": (pin-p)/rin, "Q_out_mL_per_s": (p-pv)/rout,
                       "V_local_mL": volume})
    return result


def blood_fraction(rows, cfg):
    fref, vref, volume = (float(cfg[k]) for k in ("f_b_ref", "V_ref_mL", "V_sampling_mL"))
    if not all(math.isfinite(x) for x in (fref, vref, volume)) or volume <= 0 or not 0 <= fref <= 1:
        raise ValueError("sampling volume must be positive and reference fraction in [0,1]")
    for row in rows:
        fraction = fref + (row["V_local_mL"] - vref)/volume
        if not 0 <= fraction <= 1:
            raise ValueError(f"blood fraction {fraction} outside [0,1] at {row['time_s']} s; check volume convention and parameters")
        row["f_b"] = fraction
    return rows


def absorption(fraction, blood_per_mm, matrix_per_mm):
    if not all(math.isfinite(x) and x >= 0 for x in (blood_per_mm, matrix_per_mm)):
        raise ValueError("absorption coefficients must be nonnegative")
    return fraction*blood_per_mm + (1-fraction)*matrix_per_mm
