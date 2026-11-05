"""Explicit elastic closures; wall viscosity is a separate common component.

Hughes is a run-MAP-parametrized modulus held constant within each beat.
Both literature transfers match PWDB reference area and tangent at baseline.
"""
from dataclasses import dataclass
import numpy as np
from .pwdb import MMHG_PA


@dataclass(frozen=True)
class SqrtWall:
    ad: float
    pd: float
    b: float

    def pressure(self, area):
        return self.pd + self.b * (np.sqrt(np.asarray(area) / self.ad) - 1)

    def dpda(self, area):
        return self.b / (2 * np.sqrt(self.ad * np.asarray(area)))

    def area(self, pressure):
        factor = 1 + (np.asarray(pressure) - self.pd) / self.b
        if np.any(factor <= 0):
            raise ValueError("Square-root inverse requires P > Pd-B")
        return self.ad * factor**2

    def wave_speed(self, area, rho):
        return np.sqrt(np.asarray(area) * self.dpda(area) / rho)


def hughes_wall(ad, pd, b, *, run_map_pa, baseline_map_pa, zeta_per_mmhg):
    """Normalized modelling transfer of Hughes E(MAP), not an instantaneous ODE.

    Explicit coefficients avoid importing canine-aortic E0 into finger vessels.
    """
    return SqrtWall(ad, pd, b * np.exp(zeta_per_mmhg *
                       (run_map_pa - baseline_map_pa) / MMHG_PA))


@dataclass(frozen=True)
class LangewoutersWall:
    am: float
    p0: float
    p1: float

    def __post_init__(self):
        if self.am <= 0 or self.p1 <= 0:
            raise ValueError("Langewouters requires Am>0 and P1>0")

    def area(self, pressure):
        return self.am * (.5 + np.arctan((np.asarray(pressure) - self.p0) / self.p1) / np.pi)

    def pressure(self, area):
        fraction = np.asarray(area) / self.am
        if np.any((fraction <= 0) | (fraction >= 1)):
            raise ValueError("Langewouters requires 0<A<Am")
        return self.p0 + self.p1 * np.tan(np.pi * (fraction - .5))

    def dpda(self, area):
        pressure = self.pressure(area)
        return np.pi * self.p1 / self.am * (1 + ((pressure-self.p0)/self.p1)**2)

    def wave_speed(self, area, rho):
        return np.sqrt(np.asarray(area) * self.dpda(area) / rho)

    @classmethod
    def normalized(cls, ad, pd, kd, *, shape):
        """Match area Ad and dP/dA=Kd at Pd for an explicit dimensionless shape.

        shape=(Pd-P0)/P1. This algebra does not choose a finger parameter range.
        """
        f = .5 + np.arctan(shape) / np.pi
        am = ad / f
        p1 = kd * ad / (np.pi * (1+shape**2) * f)
        return cls(am, pd - shape*p1, p1)
