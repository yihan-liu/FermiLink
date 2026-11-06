# Rest-state check: one MUSCL step on a tapered PWDB-stiffness vessel at rest.
# Run: JULIA_DEPOT_PATH=.runtime/julia/depot julia --project=.runtime/julia/project-param tests/check_balanced_taper.jl
# Expected (2026-11-06): interior median |dQ/dt| ~3e-3 without balanced_taper, ~2e-7 with it; residual only in the first cells.
using openBF, Statistics
b = openBF.Blood(Dict("mu"=>0.004, "rho"=>1060.0))
base = Dict{Any,Any}("label"=>"t","sn"=>1,"tn"=>2,"L"=>0.126,"Rp"=>3.0e-3,"Rd"=>1.5e-3,"h0"=>0.24e-3,"M"=>504,
  "stiffness_law"=>"pwdb","k1"=>3.0e6,"k2"=>-13.5,"k3"=>5.3849e5,"R1"=>2.4875e8,"R2"=>1.8697e9,"Cc"=>1.7529e-10,"exact_taper"=>true)
for bal in (false, true)
    v = openBF.Vessel(merge(base, Dict("balanced_taper"=>bal)), b, 100, ["P"])
    dt = 1e-5
    openBF.muscl!(v, dt, b)
    a = abs.(v.Q) ./ dt
    k = argmax(a[4:end-3]) + 3
    println("balanced=",bal," median=",median(a[10:end-10])," max interior at cell ",k," of ",v.M, " value ",a[k], " cells 1-6: ", round.(a[1:6], sigdigits=3))
end
