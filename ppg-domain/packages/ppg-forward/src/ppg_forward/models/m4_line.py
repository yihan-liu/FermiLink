"""M4: linear tapered radial-to-digital 1D line with parallel RC bed.

SI equations per unit length:
    dP/dx=-(R+i*w*L)Q, dQ/dx=-i*w*C*P
    A=pi*r^2, R=8*pi*mu/A^2, L=rho/A, C=A/(rho*c^2).
With NumPy's exp(+i*w*t) inverse Fourier convention, gamma=sqrt(Z*Y);
the upstream state is [[cosh(gamma*l), Zc*sinh(gamma*l)],
[sinh(gamma*l)/Zc, cosh(gamma*l)]] times the downstream state.
Thus Pout/Pin=1/(M00+M01/Zbed), Zbed=Rbed/(1+i*w*tau_bed).
The DC limit includes distributed Poiseuille resistance. Taper is linear
in radius, represented by 24 midpoint-uniform segments (not a nonlinear FV).
The distal pressure maps through linear local area compliance. Output is
fractional area change dA/A, whose scale is absorbed by external window gain.

Fixed geometry and blood properties are engineering assumptions. Only the
four declared case parameters are fitted; these are effective line parameters,
not independently identified anatomy. Constant extension on both sides of
the record suppresses FFT wraparound; discard 2 s at both boundaries when
comparing fits. No device or residual PTT is applied.
"""
import numpy as np
from scipy.fft import rfft, irfft, rfftfreq, next_fast_len
from . import _input, _priors

PARAM_BOUNDS = {"wave_speed_m_s": (3.0, 20.0), "taper_ratio": (0.3, 1.0),
                "terminal_resistance_ratio": (0.5, 30.0),
                "bed_tau_s": (0.02, 1.0)}
PARAM_NAMES = tuple(PARAM_BOUNDS)
PARAM_PRIORS = _priors(PARAM_BOUNDS)
DEFAULT_PARAMS = {"fs_hz": 50.0, "wave_speed_m_s": 8.0, "taper_ratio": 0.6,
                  "terminal_resistance_ratio": 8.0, "bed_tau_s": 0.2}
LENGTH_M = 0.25
INLET_RADIUS_M = 0.0015
RHO_KG_M3 = 1060.0
VISCOSITY_PA_S = 0.004
N_SEGMENTS = 24
BOUNDARY_DISCARD_S = 2.0


def transfer_function(frequency_hz, params):
    """Distal/inlet pressure transfer at nonnegative frequencies, Hz."""
    p = dict(DEFAULT_PARAMS)
    p.update(params)
    f = np.asarray(frequency_hz, dtype=float)
    c, taper, ratio, tau = (float(p[k]) for k in PARAM_NAMES)
    if c <= 0 or not 0 < taper <= 1 or ratio <= 0 or tau <= 0:
        raise ValueError("positive wave speed, bed R/tau and taper in (0,1] required")
    w = 2*np.pi*f
    area0 = np.pi*INLET_RADIUS_M**2
    rbed = ratio*RHO_KG_M3*c/area0
    zbed_inv = (1 + 1j*w*tau)/rbed
    m00 = np.ones(f.shape, dtype=complex)
    m01 = np.zeros(f.shape, dtype=complex)
    m10 = np.zeros(f.shape, dtype=complex)
    m11 = np.ones(f.shape, dtype=complex)
    dx = LENGTH_M/N_SEGMENTS
    for i in range(N_SEGMENTS):
        radius = INLET_RADIUS_M*(1+(taper-1)*(i+0.5)/N_SEGMENTS)
        area = np.pi*radius**2
        z = 8*np.pi*VISCOSITY_PA_S/area**2 + 1j*w*RHO_KG_M3/area
        y = 1j*w*area/(RHO_KG_M3*c*c)
        gd = np.sqrt(z*y)*dx
        ch = np.cosh(gd)
        # sinh(gd)/gd has limit 1; avoids a 0/0 characteristic impedance at DC.
        shc = np.ones_like(gd)
        nz = gd != 0
        shc[nz] = np.sinh(gd[nz])/gd[nz]
        a, b, cc = ch, z*dx*shc, y*dx*shc
        m00, m01, m10, m11 = (m00*a+m01*cc, m00*b+m01*a,
                               m10*a+m11*cc, m10*b+m11*a)
    return 1/(m00+m01*zbed_inv)


def predict(art, params):
    x, p, fs = _input(art, params, DEFAULT_PARAMS)
    # Ten maximum terminal time constants plus line transit/reflection margin.
    # Constant extension avoids a periodic join between the record endpoints.
    pad = int(np.ceil(12.0*fs))
    nfft = next_fast_len(len(x)+2*pad)
    xp = np.pad(x, (pad, nfft-len(x)-pad), mode="edge")
    h = transfer_function(rfftfreq(nfft, 1/fs), p)
    # The even-length Nyquist bin is self-conjugate and must be real.
    if nfft % 2 == 0:
        h[-1] = h[-1].real
    pressure = irfft(rfft(xp)*h, nfft)[pad:pad+len(x)]
    return (pressure-pressure[0])*133.322387415/(RHO_KG_M3*p["wave_speed_m_s"]**2)
