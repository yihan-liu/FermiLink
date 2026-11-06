All new options default to upstream behaviour:
  stiffness_law: "openbf" (E, h0) | "pwdb" (k1, k2, k3 in PWDB units)
  b0, b1: viscoelastic coefficients of the upstream Gamma = b1*0.5/R0 + b0 (defaults 0.6, 0.0015)
  visco_law: "openbf" | "pwdb" (PWDB generator Gamma from b0 [g/s], b1 [g cm/s]; Cv = Gamma_in*sqrt(A0)/rho)
  exact_taper: false | true (R(x) = Rp + (Rd-Rp) x/L at cell centres; per-metre dA0/dx)
  balanced_taper: false | true (taper source derived from the flux form; preserves rest state)

This is a copy of upstream openBF 2.8.0 (revision fae58658e060640fb523141e47001e1522b88b0b), Apache-2.0, changed only in src/vessel.jl and src/solver.jl as listed. With every option at its default the code path is upstream's.
