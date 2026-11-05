#=
Copyright 2015-2026 INSIGNEO Institute for in silico Medicine

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
=#

struct Blood
    mu::Float64
    rho::Float64
    Cf::Float64
end

function Blood(config::Dict)
    μ = config["mu"]
    ρ = config["rho"]
    Cf = 8π * μ / ρ
    Blood(μ, ρ, Cf)
end

mutable struct Vessel
    label::String
    laws::Vector{Wall}
    radii::Vector{Float64}
    radius_slope::Float64
    dbdr::Vector{Float64}
    wall_gamma::Vector{Float64}
    adot::Vector{Float64}
    rho::Float64
    tosave::Bool

    #Topological notation
    sn::Int64
    tn::Int64

    #Numerical constants
    M::Int64
    dx::Float64
    invDx::Float64
    halfDx::Float64

    #Physical constants
    beta::Vector{Float64}
    Cv::Vector{Float64}
    viscoelastic::Bool
    gamma::Vector{Float64}
    A0::Vector{Float64}
    tapered::Bool
    dA0dx::Vector{Float64}
    dTaudx::Vector{Float64}
    Pext::Float64
    gamma_profile::Int64

    #Iterative solution
    A::Vector{Float64}
    Q::Vector{Float64}
    u::Vector{Float64}
    P::Vector{Float64}

    #Riemann invariants
    W1M0::Float64
    W2M0::Float64

    #Ghost cells
    U00A::Float64
    U00Q::Float64
    UM1A::Float64
    UM1Q::Float64

    #Saving locations
    node2::Int64
    node3::Int64
    node4::Int64

    #Peripheral boundary condition
    usewk3::Bool
    Rt::Float64
    R1::Float64
    R2::Float64
    total_peripheral_resistance::Float64
    inlet_impedance_matching::Bool
    Cc::Float64
    Pc::Float64
    Pout::Float64

    #MUSCLArrays
    fluxA::Vector{Float64}
    fluxQ::Vector{Float64}

    vA::Vector{Float64}
    vQ::Vector{Float64}

    slopesA::Vector{Float64}
    slopesQ::Vector{Float64}

    Al::Vector{Float64}
    Ar::Vector{Float64}

    Ql::Vector{Float64}
    Qr::Vector{Float64}

    Fl::Vector{Float64}
    Fr::Vector{Float64}

    # waveforms
    waveforms::Dict{String, Array{Float64, 2}}
    waveforms_prev::Dict{String, Array{Float64, 2}}
end

wave_speed(v::Vessel) = [wave_speed(v.A[i],v.laws[i+1],v.rho) for i in eachindex(v.A)]

function mesh(config::Dict{Any,Any})
    L = config["L"]
    M = get(config, "M", 5)
    M = max(M, 5)
    M = max(M, ceil(Int, config["L"] / get(config,"dx_m",0.001))+1)

    dx = L / (M-1)
    invDx = (M-1) / L
    halfDx = 0.5 * dx

    L, M, dx, invDx, halfDx
end

function radii(config::Dict{Any,Any})
    ~haskey(config, "R0") &&
        ~haskey(config, "Rp") &&
        error("missing radius in $(config["label"])")
    R0 = get(config, "R0", 0.0)
    Rp = get(config, "Rp", R0)
    Rd = get(config, "Rd", Rp)
    Rp, Rd
end

function Vessel(config::Dict{Any,Any}, b::Blood, jump::Int64, tokeep::Vector{String})
    vessel_name = config["label"]
    tosave = get(config, "to_save", true)
    sn = config["sn"]
    tn = config["tn"]
    Rp, Rd = radii(config)
    L, M, dx, invDx, halfDx = mesh(config)
    E = config["E"]

    Pext = get(config, "Pext", 0.0)
    initial_pressure = get(config, "initial_pressure", 0.0)
    initial_flow = get(config, "initial_flow", 0.0)

    sigma = 0.5

    A0 = zeros(Float64, M)
    R0 = zeros(Float64, M)
    h0 = zeros(Float64, M) .+ get(config, "h0", 0.0)

    dA0dx = zeros(Float64, M)
    dTaudx = zeros(Float64, M)
    radius_slope = (Rd - Rp) / L
    tapered = Rd != Rp # retain published small-vessel taper; # less than 1μm difference = no tapering
    ah = 0.2802
    bh = -5.053e2
    ch = 0.1324
    dh = -0.1114e2
    for i = 1:M
        R0[i] = radius_slope * (i - 1) * L/(M-1) + Rp
        if ~haskey(config, "h0")
            h0[i] = R0[i] * (ah * exp(bh * R0[i]) + ch * exp(dh * R0[i]))
        end
        A0[i] = pi * R0[i] * R0[i]
        dA0dx[i] = 2 * pi * R0[i] * radius_slope

        if haskey(config, "h0")
            dTaudx[i] = 0.0
        else
            dTaudx[i] = (sqrt(pi) * E * radius_slope * 1.3 * (h0[i] / R0[i] + R0[i] * (ah * bh * exp(bh * R0[i]) + ch * dh * exp(dh * R0[i]))))
        end
    end

    laws_inner = [make_wall(config,r) for r in R0]
    laws = [laws_inner[1];laws_inner;laws_inner[end]]
    beta = [w.b for w in laws_inner]
    gamma = zeros(Float64,M+2) # retained upstream scratch layout, no constitutive dispatch
    gamma_profile = 2
    wall_gamma = [(float(config["b1"])/(2*100r)+float(config["b0"]))/1000/(pi*r*r) for r in R0]
    viscoelastic = L>0.011 && get(config,"visco-elastic",true)
    !viscoelastic && fill!(wall_gamma,0.)
    Cv = wall_gamma.*sqrt.(A0)./b.rho
    dbdr = [(4/3)*.1*config["k1"]*config["k2"]*100*exp(config["k2"]*100r)*get(config,"stiffness_scale",1.) for r in R0]
    if Symbol(config["wall_law"]) == :hughes
        dbdr .*= exp(config["zeta_per_mmhg"]*(config["run_map_pa"]-config["baseline_map_pa"])/133.322387415)
    end
    adot = zeros(M)

    A = zeros(Float64, M) + A0
    Q = zeros(Float64, M) .+ initial_flow
    u = zeros(Float64, M) + Q ./ A
    P = [pressure(A[i],laws[i+1]) for i in eachindex(A)]

    U00A = A0[1]
    UM1A = A0[M]
    U00Q = initial_flow
    UM1Q = initial_flow

    c = wave_speed(A[end], laws[end-1], b.rho)
    W1M0 = u[end] - 4c
    W2M0 = u[end] + 4c

    node2 = round(Int, M * 0.25)
    node3 = round(Int, M * 0.5)
    node4 = round(Int, M * 0.75)

    Rt = get(config, "Rt", 0.0)
    R1 = get(config, "R1", 0.0)
    R2 = get(config, "R2", 0.0)
    Cc = get(config, "Cc", 0.0)
    if R2 == 0.0
        R2 = R1 - b.rho * wave_speed(A0[end], laws[end-1], b.rho) / A0[end]
    end
    total_peripheral_resistance = R1 + R2
    inlet_impedance_matching = get(config, "inlet_impedance_matching", false)
    usewk3 = R2 != 0.0

    # `Pc` is the pressure through the peripheral compliance of the three
    # elements windkessel. It is set to zero to simulate the pressure at the
    # artery-vein interface.
    Pc = Pext
    Pout = get(config, "Pout", 0.0)

    # MUSCL arrays
    fluxA = zeros(Float64, M + 2)
    fluxQ = zeros(Float64, M + 2)

    vA = zeros(Float64, M + 2)
    vQ = zeros(Float64, M + 2)

    slopesA = zeros(Float64, M + 2)
    slopesQ = zeros(Float64, M + 2)

    Al = zeros(Float64, M + 2)
    Ar = zeros(Float64, M + 2)

    Ql = zeros(Float64, M + 2)
    Qr = zeros(Float64, M + 2)

    Fl = zeros(Float64, M + 2)
    Fr = zeros(Float64, M + 2)

    gamma_profile = get(config, "gamma_profile", 2)

    waveforms = Dict()
    waveforms_prev = Dict()
    for q in tokeep
        waveforms[q] = zeros(Float64, jump, 6)
        waveforms_prev[q] = zeros(Float64, jump, 6)
    end

    Vessel(
        vessel_name,
        laws, R0, radius_slope, dbdr, wall_gamma, adot, b.rho,
        tosave,
        sn,
        tn,
        M,
        dx,
        invDx,
        halfDx,
        beta,
        Cv,
        viscoelastic,
        gamma,
        A0,
        tapered,
        dA0dx,
        dTaudx,
        Pext,
        gamma_profile,
        A,
        Q,
        u,
        P,
        W1M0,
        W2M0,
        U00A,
        U00Q,
        UM1A,
        UM1Q,
        node2,
        node3,
        node4,
        usewk3,
        Rt,
        R1,
        R2,
        total_peripheral_resistance,
        inlet_impedance_matching,
        Cc,
        Pc,
        Pout,
        fluxA,
        fluxQ,
        vA,
        vQ,
        slopesA,
        slopesQ,
        Al,
        Ar,
        Ql,
        Qr,
        Fl,
        Fr,
        waveforms,
        waveforms_prev,
    )
end
