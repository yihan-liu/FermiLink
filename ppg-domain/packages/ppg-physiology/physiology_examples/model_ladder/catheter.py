"""Per-case second-order catheter response and regularized inversion.

The VitalDB scan flush table stores peak-to-peak ringing frequency as fn_hz.
That is damped frequency fd; it is not a verified natural frequency.
Conversion assumes an underdamped linear second-order catheter response.
"""
import numpy as np
from scipy import fft


def natural_frequency(fn_hz, zeta, frequency_kind):
    """Return natural frequency; callers must declare the estimate's meaning."""
    if not np.isfinite(fn_hz) or fn_hz <= 0:
        raise ValueError("Frequency must be finite and positive.")
    if not np.isfinite(zeta) or zeta <= 0:
        raise ValueError("Damping ratio must be finite and positive.")
    if frequency_kind == "damped":
        if zeta >= 1:
            raise ValueError("Damped ringing conversion requires 0 < zeta < 1.")
        return float(fn_hz / np.sqrt(1 - zeta ** 2))
    if frequency_kind != "natural":
        raise ValueError("Declare frequency_kind as 'natural' or 'damped'.")
    return float(fn_hz)


def response(frequency_hz, fn_hz, zeta):
    """Analog pressure transfer H(f), taking a declared natural fn in Hz."""
    ratio = np.asarray(frequency_hz, dtype=float) / fn_hz
    return 1 / (1 - ratio ** 2 + 2j * zeta * ratio)


def correct(art, params):
    """Return availability, corrected ART and effective catheter parameters.

    params: fs_hz=50, fn_hz, zeta, explicit frequency_kind, and
    regularization_hz=15. Missing/nonfinite fn_hz or zeta returns art=None.
    Invalid supplied parameters raise ValueError rather than fabricate a fit.

    Inverse H is multiplied by a zero-phase eighth-power low-pass taper:
    W(f)=1/(1+(f/f_reg)**8). This preserves DC and suppresses high-frequency
    derivative amplification. Constant padding (2 s) avoids periodic wrapping
    of the input record; boundary estimates still depend on this extension.
    Correction is offline and not a physiological validation of fn/zeta.
    """
    fn, zeta = params.get("fn_hz"), params.get("zeta")
    base = {"available": False, "art": None, "fn_hz": None, "zeta": zeta,
            "frequency_kind": params.get("frequency_kind")}
    if fn is None or zeta is None or not np.isfinite(fn) or not np.isfinite(zeta):
        return dict(base, reason="catheter fn_hz/zeta unavailable")
    fn = natural_frequency(float(fn), float(zeta), params.get("frequency_kind"))
    fs = float(params.get("fs_hz", 50))
    cutoff = float(params.get("regularization_hz", 15))
    corrected = _spectral_filter(art, fs, cutoff, fn, float(zeta))
    return dict(base, available=True, art=corrected, reason=None,
                fn_hz=fn, zeta=float(zeta), regularization_hz=cutoff)


def bandlimit(art, fs_hz=50, regularization_hz=15):
    """Apply the same fixed taper as correction, with no catheter inversion.

    Use for the uncorrected comparison branch so bandwidth and endpoint
    handling match the corrected branch.
    """
    return _spectral_filter(art, float(fs_hz), float(regularization_hz))


def _spectral_filter(art, fs, cutoff, fn=None, zeta=None):
    if fs <= 0 or not 0 < cutoff < fs / 2:
        raise ValueError("Require fs_hz > 0 and 0 < regularization_hz < Nyquist.")
    x = np.asarray(art, dtype=float)
    if x.ndim != 1 or x.size < 2 or not np.all(np.isfinite(x)):
        raise ValueError("ART must be a finite one-dimensional waveform.")
    pad = int(np.ceil(2 * fs))
    xp = np.pad(x, pad, mode="edge")
    nfft = fft.next_fast_len(len(xp))
    xp = np.pad(xp, (0, nfft - len(xp)), mode="edge")
    f = fft.rfftfreq(nfft, 1 / fs)
    transfer = 1 / (1 + (f / cutoff) ** 8)
    if fn is not None:
        transfer = transfer / response(f, fn, zeta)
    return fft.irfft(fft.rfft(xp) * transfer, nfft)[pad:pad + len(x)]
