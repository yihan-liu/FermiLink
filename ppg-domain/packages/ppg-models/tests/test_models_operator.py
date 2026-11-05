"""Synthetic numerical checks for the fixed Round 2 ladder and operator."""
import numpy as np
import pytest
from ppg_models import catheter, operator
from ppg_models.models import m0_empirical, m1_transmission, m2_nonlinear_pv, m3_2r1c, m4_line

@pytest.mark.parametrize("fs",[50,500])
def test_fixed_ladder_and_m0_nests_m1(fs):
    t=np.arange(30*fs)/fs
    art=85+20*np.sin(2*np.pi*1.2*t)+5*np.sin(2*np.pi*2.4*t+.3)
    for model in [m0_empirical,m1_transmission,m2_nonlinear_pv,m3_2r1c,m4_line]:
        y=model.predict(art,{"fs_hz":fs})
        assert y.shape==art.shape and np.isfinite(y).all()
        assert np.max(np.abs(model.predict(np.full(len(art),85.),{"fs_hz":fs})))<1e-9
    np.testing.assert_allclose(m0_empirical.predict(art,{"fs_hz":fs}),m1_transmission.predict(art,{"fs_hz":fs}),atol=1e-12)

def test_nonlinear_pv_retains_pressure_dc():
    t=np.arange(1500)/50; x=70+20*np.sin(2*np.pi*1.2*t)
    norm=lambda v:(v-v.mean())/v.std()
    assert np.linalg.norm(norm(m2_nonlinear_pv.predict(x,{}))-norm(m2_nonlinear_pv.predict(x+30,{})))>0.1

def test_fractional_delay_has_no_wrap_and_gain_is_positive():
    x=np.zeros(1000);x[500]=1
    y=operator.delay(x,.43,50)
    assert np.isnan(y[:22]).all() and np.nanargmax(y) in (521,522)
    with pytest.raises(ValueError,match="positive gain"):
        operator.apply(x,dict(lo_hz=.1,hi_hz=10,order=2,phase="causal",sign=1,gain=-1))

def test_catheter_conversion_common_bandwidth_and_missing():
    assert catheter.natural_frequency(12*np.sqrt(1-.2**2),.2,"damped")==pytest.approx(12)
    assert not catheter.correct(np.ones(1500),{})["available"]
    t=np.arange(1500)/50;x=85+20*np.sin(2*np.pi*1.2*t)
    y=catheter.bandlimit(x,50)
    near_identity=catheter.correct(x,dict(fn_hz=1e10,zeta=.2,frequency_kind="natural"))["art"]
    np.testing.assert_allclose(y,near_identity,atol=1e-6)

def test_m4_dc_is_passive():
    h=m4_line.transfer_function(np.array([0.]),m4_line.DEFAULT_PARAMS)
    assert np.isfinite(h).all() and abs(h[0].imag)<1e-12 and 0<h[0].real<1
