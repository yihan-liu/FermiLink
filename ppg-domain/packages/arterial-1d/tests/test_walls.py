import unittest
import numpy as np
from arterial_1d.pwdb import MMHG_PA
from arterial_1d.walls import SqrtWall, LangewoutersWall, hughes_wall


class WallTests(unittest.TestCase):
    def test_reference_tangent_and_inverse(self):
        default = SqrtWall(1e-5, 1e4, 8e4)
        walls = [default, LangewoutersWall.normalized(default.ad, default.pd, default.b/(2*default.ad), shape=.6)]
        for wall in walls:
            self.assertAlmostEqual(wall.pressure(default.ad), default.pd)
            self.assertAlmostEqual(wall.dpda(default.ad)/default.dpda(default.ad), 1)
            a = default.ad*np.array([.9,1,1.1])
            np.testing.assert_allclose(wall.area(wall.pressure(a)), a)
            eps = default.ad*1e-5
            slope = (wall.pressure(default.ad+eps)-wall.pressure(default.ad-eps))/(2*eps)
            self.assertAlmostEqual(slope/wall.dpda(default.ad), 1, places=7)
            self.assertTrue(np.all(wall.wave_speed(a,1060)>0))

    def test_hughes_is_frozen_at_supplied_run_mean(self):
        base = hughes_wall(1e-5,1e4,8e4,run_map_pa=12000,baseline_map_pa=12000,zeta_per_mmhg=.017)
        self.assertEqual(base.b, 8e4)
        raised = hughes_wall(1e-5,1e4,8e4,run_map_pa=100*MMHG_PA+12000,baseline_map_pa=12000,zeta_per_mmhg=.017)
        self.assertAlmostEqual(raised.b/base.b, np.exp(1.7))

    def test_langewouters_asymptotes_and_domain(self):
        wall = LangewoutersWall(1e-5,1000,2000)
        self.assertAlmostEqual(wall.area(1e15), wall.am)
        self.assertAlmostEqual(wall.area(-1e15), 0)
        with self.assertRaises(ValueError): wall.pressure(wall.am)
        with self.assertRaises(ValueError): wall.pressure(0)
