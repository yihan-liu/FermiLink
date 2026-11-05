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


function calculateΔt(n::Network)
    minΔt = 1.0
    for v in n.vessels_vec
        maxspeed = 0.0
        for i in eachindex(v.u)
            @inbounds speed = abs(v.u[i]) + wave_speed(v.A[i], v.laws[i+1], v.rho)
            isfinite(speed) || error("Nonfinite wave speed")
            maxspeed = max(maxspeed, speed)
        end
        Δt = v.dx / maxspeed
        isfinite(Δt) || error("Nonfinite CFL step")
        minΔt = min(minΔt, Δt)
    end
    minΔt * n.Ccfl
end

# Apply inlet BC and downstream junction for one edge.
# Called in Phase A (junctions-only pass) before any muscl! runs this step.
@inline function _apply_junctions!(n::Network, eid::Int, current_time::Float64, dt::Float64)
    v = n.vessels_vec[eid]
    n.is_inlet[eid] && inbc!(v, current_time, dt, n.heart)

    nc = n.child_count[eid]
    if nc == 0
        outbc!(v, dt, n.blood.rho)
    elseif nc == 1
        c1 = Int(n.child_eids[eid][1])
        np_child = n.parent_count[c1]
        if np_child == 1
            n.junction_mass_error[1] = max(n.junction_mass_error[1],join_vessels!(v, n.vessels_vec[c1], n.blood.rho))
        else
            # Anastomosis: max-eid parent triggers the single solve per step.
            # In two-phase both parents' boundaries are pre-muscl → single consistent read.
            p1, p2 = Int(n.parent_eids[c1][1]), Int(n.parent_eids[c1][2])
            if eid == max(p1, p2)
                n.junction_mass_error[1] = max(n.junction_mass_error[1],solveAnastomosis(n.vessels_vec[p1], n.vessels_vec[p2], n.vessels_vec[c1]))
                n.anastomosis_solved[c1] = true
            end
        end
    elseif nc == 2
        c1, c2 = Int(n.child_eids[eid][1]), Int(n.child_eids[eid][2])
        n.junction_mass_error[1] = max(n.junction_mass_error[1],join_vessels!(v, n.vessels_vec[c1], n.vessels_vec[c2]))
    end
    return
end

function solve!(n::Network, dt::Float64, current_time::Float64)::Nothing
    fill!(n.anastomosis_solved, false)
    for v in n.vessels_vec
        v.adot .= v.A # save previous area before boundary updates
    end

    # Phase A: all junctions in topological order (reads only previous-step boundaries)
    @inbounds for k in eachindex(n.topo_order)
        _apply_junctions!(n, Int(n.topo_order[k]), current_time, dt)
    end

    update_ghost_cells!(n)

    # Phase B: all MUSCL advances (boundaries fully set; order irrelevant)
    @inbounds for k in eachindex(n.topo_order)
        muscl!(n.vessels_vec[Int(n.topo_order[k])], dt, n.blood)
    end
    # Project instantaneous endpoint states after both operators. dt=0 keeps
    # Windkessel capacitor pressure unchanged; no second dynamic update occurs.
    fill!(n.anastomosis_solved,false)
    for k in eachindex(n.topo_order)
        _apply_junctions!(n,Int(n.topo_order[k]),current_time+dt,0.)
    end
    # Measure the actual projected full-step states, not only Newton residuals.
    for eid in eachindex(n.vessels_vec)
        nc=n.child_count[eid]
        nc==0 && continue
        c1=Int(n.child_eids[eid][1])
        n.parent_count[c1]>1 && eid!=maximum(n.parent_eids[c1]) && continue
        flows=Float64[n.vessels_vec[eid].Q[end]]
        signs=Float64[1.]
        if n.parent_count[c1]>1
            other=filter(p->p!=eid,n.parent_eids[c1])[1]
            push!(flows,n.vessels_vec[Int(other)].Q[end]); push!(signs,1.)
        end
        for c in n.child_eids[eid][1:nc]
            push!(flows,n.vessels_vec[Int(c)].Q[1]); push!(signs,-1.)
        end
        rel=abs(sum(signs.*flows))/max(sum(abs.(flows)),eps())
        n.junction_mass_error[1]=max(n.junction_mass_error[1],rel)
    end
    for v in n.vessels_vec
        for i in eachindex(v.A)
            v.adot[i] = (v.A[i]-v.adot[i])/dt
            v.u[i] = v.Q[i]/v.A[i]
            v.P[i] = pressure(v.A[i],v.laws[i+1])+v.wall_gamma[i]/sqrt(v.A[i])*v.adot[i]
        end
    end
    return
end

# Shared half-step: limit slopes, reconstruct cell-edge states, compute fluxes.
# Called twice per muscl! (predictor + corrector).
@inline function muscl_halfstep!(v::Vessel, dxDt::Float64)
    limit_slopes!(v.slopesA, v.vA, v.invDx, v.halfDx)
    limit_slopes!(v.slopesQ, v.vQ, v.invDx, v.halfDx)
    @fastmath @inbounds for i = eachindex(v.Al)
        Ali = v.vA[i] + v.slopesA[i]
        Ari = v.vA[i] - v.slopesA[i]
        Qli = v.vQ[i] + v.slopesQ[i]
        Qri = v.vQ[i] - v.slopesQ[i]
        v.Al[i] = Ali
        v.Ar[i] = Ari
        v.Ql[i] = Qli
        v.Qr[i] = Qri
        v.Fl[i] = Qli * Qli / Ali + potential(Ali, v.laws[i], v.rho)
        v.Fr[i] = Qri * Qri / Ari + potential(Ari, v.laws[i], v.rho)
    end
    @fastmath @inbounds for i = 1:v.M+1
        v.fluxA[i] = 0.5 * (v.Qr[i+1] + v.Ql[i] - dxDt * (v.Ar[i+1] - v.Al[i]))
        v.fluxQ[i] = 0.5 * (v.Fr[i+1] + v.Fl[i] - dxDt * (v.Qr[i+1] - v.Ql[i]))
    end
    return
end

function muscl!(v::Vessel, dt::Float64, b::Blood)
    dxDt = v.dx / dt
    invDxDt = 1.0 / dxDt

    # step-1
    # i = 1
    @inbounds v.vA[1] = v.U00A
    @inbounds v.vQ[1] = v.U00Q
    # 2:v.M+1
    for i = eachindex(v.A, v.Q)
        @inbounds v.vA[i+1] = v.A[i]
        @inbounds v.vQ[i+1] = v.Q[i]
    end
    # i = M+2
    @inbounds v.vA[end] = v.UM1A
    @inbounds v.vQ[end] = v.UM1Q

    muscl_halfstep!(v, dxDt)

    # step-2
    for i = 2:v.M+1
        @inbounds v.vA[i] += invDxDt * (v.fluxA[i-1] - v.fluxA[i])
        @inbounds v.vQ[i] += invDxDt * (v.fluxQ[i-1] - v.fluxQ[i])
    end
    # i=1
    @inbounds v.vA[1] = v.vA[2]
    @inbounds v.vQ[1] = v.vQ[2]
    # i=M+2
    @inbounds v.vA[end] = v.vA[end-1]
    @inbounds v.vQ[end] = v.vQ[end-1]

    muscl_halfstep!(v, dxDt)

    # 2:v.M+1
    for i = eachindex(v.A)
        @inbounds v.A[i] =
            0.5 * (v.A[i] + v.vA[i+1] + invDxDt * (v.fluxA[i] - v.fluxA[i+1]))
        @inbounds v.Q[i] =
            0.5 * (v.Q[i] + v.vQ[i+1] + invDxDt * (v.fluxQ[i] - v.fluxQ[i+1]))
    end

    #source term
    for i = eachindex(v.Q) # 1:v.M
        #viscosity
        @inbounds v.Q[i] -= 2 * (v.gamma_profile + 2) * pi * b.mu * v.Q[i] / (v.A[i] * b.rho) * dt

        if v.tapered
            v.Q[i] += dt*geometry_source(v.A[i],v.laws[i+1],v.radii[i],v.radius_slope,v.dbdr[i],b.rho)
        end

        # update
        @inbounds v.u[i] = v.Q[i] / v.A[i]
    end

    # Original Voigt: Q_t=(A/rho)*Dx(B*Dx(Q)), B=GammaInput/sqrt(A).
    # Freeze A within this implicit split step, keeping A outside Dx.
    if v.viscoelastic
        coef = v.wall_gamma./sqrt.(v.A)
        faces = (coef[1:end-1].+coef[2:end])./2
        lower=zeros(v.M-1); upper=zeros(v.M-1); diagonal=ones(v.M)
        for i in 1:v.M
            left=i>1 ? dt*v.A[i]/b.rho*faces[i-1]/v.dx^2 : 0.
            right=i<v.M ? dt*v.A[i]/b.rho*faces[i]/v.dx^2 : 0.
            diagonal[i] += left+right
            i>1 && (lower[i-1] = -left)
            i<v.M && (upper[i] = -right)
        end
        v.Q .= Tridiagonal(lower,diagonal,upper)\v.Q
    end
    v.u .= v.Q./v.A
end

function limit_slopes!(slopes::Vector{Float64}, U::Vector{Float64},
                        invDx::Float64, halfDx::Float64)
    N = length(slopes)
    @inbounds slopes[1]   = 0.0
    @inbounds slopes[end] = 0.0
    @inbounds @simd for i in 2:N-1
        a = (U[i]   - U[i-1]) * invDx
        b = (U[i+1] - U[i])   * invDx
        t1 = max(min(a, 2b), min(2a, b))
        t2 = min(max(a, 2b), max(2a, b))
        slopes[i] = ifelse(a > 0, ifelse(b > 0, t1, zero(Float64)),
                                   ifelse(b < 0, t2, zero(Float64))) * halfDx
    end
    return
end
