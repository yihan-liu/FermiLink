# arterial-walls

Wall laws for 1D arterial networks from the literature: the square-root law with PWDB stiffness, Voigt viscosity (Alastruey 2012), the Hughes exponential modulus (1979) and the Langewouters arctangent law (1984, with the verified 65-specimen parameter table). Knowledge and reference code only; no CLI.

When a run pins this package, the `openbf` and `pwdb` knowledge bases are available under `external_packages/`.

- [Equations, closures and applicability](walls_knowledge/index.md)
- [Langewouters 1984 Table 2](walls_knowledge/langewouters1984_table2.md)
- [Sources](walls_knowledge/sources.md)
- [Reference closures](walls_examples/wall_laws_reference.py)
