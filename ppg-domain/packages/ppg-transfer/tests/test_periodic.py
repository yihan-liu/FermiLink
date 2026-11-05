import numpy as np

from ppg_transfer.delay import fit_delay
from ppg_transfer.harmonics import periodic_transfer


def test_periodic_group_delay_with_intercept_and_gain():
    period = .8228646661912338
    t = np.arange(412)/500
    tau, intercept = .0016, .2
    x, y = np.zeros(len(t)), np.zeros(len(t))
    for k in range(1, 6):
        omega = 2*np.pi*k/period
        x += np.cos(omega*t)/k
        y += (.9**k)*np.cos(omega*t+intercept-omega*tau)/k
    result = periodic_transfer(t, x, y, period, [1, 1, 1])
    scaled = periodic_transfer(t, x, 17*y, period, [1, 1, 1])
    assert abs(result["group_delay_k1_3_s"]-tau) < 1e-12
    assert abs(result["phase_wls_intercept_rad"]-intercept) < 1e-12
    assert abs(result["h2_over_h1"]-.9) < 1e-12
    assert abs(result["group_delay_k1_3_s"]-scaled["group_delay_k1_3_s"]) < 1e-12


def test_model_and_observation_share_one_delay_estimator():
    """Model transfers use the same fit_delay as observed records, without an operator."""
    period = .9
    h = np.array([np.exp(-1j*(2*np.pi*k/period*.004-.1))*(.8**k) for k in range(1, 6)])
    weights = [2., 1., .5]
    direct = fit_delay(h, np.arange(1, 6)/period, None, weights)
    t = np.arange(450)/500
    x = sum(np.cos(2*np.pi*k*t/period) for k in range(1, 6))
    y = sum(abs(z)*np.cos(2*np.pi*k*t/period+np.angle(z)) for k, z in enumerate(h, 1))
    periodic = periodic_transfer(t, x, y, period, weights)
    assert abs(direct["tau_s"]-periodic["group_delay_k1_3_s"]) < 1e-12
    assert abs(direct["intercept_rad"]-periodic["phase_wls_intercept_rad"]) < 1e-12
