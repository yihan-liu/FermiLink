import unittest
import numpy as np
from arterial_1d.pwdb import radius, periodic_interpolate, reference


class PublicDataTests(unittest.TestCase):
    def test_geometry_uses_physical_length(self):
        s = dict(length=.2, inlet_radius=.003, outlet_radius=.001)
        np.testing.assert_allclose(radius(s, [0, .1, .2]), [.003, .002, .001])


    def test_native_time_preserves_relative_onsets(self):
        data = dict(fs_hz=500., period_s=1., onset_times={}, waveforms={})
        raw = np.sin(2*np.pi*np.arange(500)/500)
        for prefix, onset in (("Radial", .084), ("Digital", .090)):
            for q in ("P", "U", "A"):
                data["onset_times"][prefix+"_"+q] = onset
                data["waveforms"][prefix+"_"+q] = raw.tolist()
        at = np.arange(500)/500
        rad, dig = reference(data, "radial", at), reference(data, "digital", at)
        np.testing.assert_allclose(dig["A"], np.roll(rad["A"], 3), atol=1e-14)


    def test_fractional_period_keeps_native_spacing(self):
        t = np.arange(4)/500
        at = np.array([.002, .004, .007])
        np.testing.assert_allclose(periodic_interpolate(t, [0,1,2,3], .009, at), [1,2,2])
