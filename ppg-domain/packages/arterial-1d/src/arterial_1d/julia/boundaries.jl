# Package adaptation of openBF boundary/junction Newton iterations.
# Copyright 2015-2026 INSIGNEO Institute for in silico Medicine
# Apache-2.0, see ../../../../LICENSE-openBF. Modified for explicit Wall state.

function inlet_from_data(t,h::Heart)
    tt=mod(t,h.cardiac_period)
    i=clamp(searchsortedlast(h.t,tt),1,length(h.t)-1)
    h.q[i]+(tt-h.t[i])*(h.q[i+1]-h.q[i])/(h.t[i+1]-h.t[i])
end
function outgoing(v::Vessel,side,dt)
    i=side==1 ? v.M : 1
    j=side==1 ? v.M-1 : 2
    w=v.laws[i+1]; wj=v.laws[j+1]
    inv=v.u[i]+side*characteristic(v.A[i],w,v.rho)
    neighbor=v.u[j]+side*characteristic(v.A[j],wj,v.rho)
    speed=wave_speed(v.A[i],w,v.rho)+side*v.u[i]
    inv+(neighbor-inv)*speed*dt/v.dx
end
function scalar_area_newton(fun,w::Wall,initial)
    x=log(initial/w.ad)
    for _ in 1:30
        a=w.ad*exp(x)
        f,df=fun(a)
        abs(f)<1e-10 && return a
        step=f/df
        damping=1.
        accepted=false
        for _ in 1:20
            trial=x-damping*step
            aa=w.ad*exp(trial)
            if isfinite(aa) && aa>0 && (w.kind!=:langewouters || aa<w.am)
                ft,_=fun(aa)
                if abs(ft)<abs(f)
                    x=trial; accepted=true; break
                end
            end
            damping*=.5
        end
        accepted || error("Boundary Newton line search failed")
    end
    error("Boundary Newton did not converge")
end
function inbc!(v::Vessel,t,dt,h::Heart)
    q=inlet_from_data(t,h); w=v.laws[2]; inv=outgoing(v,-1,dt)
    fun(a)=(q/a-characteristic(a,w,v.rho)-inv,-q/a-wave_speed(a,w,v.rho))
    a=scalar_area_newton(fun,w,v.A[1])
    v.A[1]=a; v.Q[1]=q; v.u[1]=q/a
end
function outbc!(v::Vessel,dt,rho)
    v.usewk3 || error("PWDB wrapper requires three-element Windkessel outlets")
    w=v.laws[end-1]; inv=outgoing(v,1,dt)
    denominator=1+dt/(v.R2*v.Cc)
    gain=dt/v.Cc/denominator
    pcbase=(v.Pc+dt*v.Pout/(v.R2*v.Cc))/denominator
    function fun(a)
        u=inv-characteristic(a,w,rho); q=a*u
        dq=q-a*wave_speed(a,w,rho)
        ((pressure(a,w)-pcbase-(v.R1+gain)*q)/w.b,
         (a*dpda(a,w)-(v.R1+gain)*dq)/w.b)
    end
    a=scalar_area_newton(fun,w,v.A[end])
    q=a*(inv-characteristic(a,w,rho))
    v.Pc=pcbase+gain*q
    v.A[end]=a; v.Q[end]=q; v.u[end]=q/a
end

# n outgoing characteristic equations are eliminated analytically; Newton solves
# n endpoint areas and their common elastic total pressure with exact mass balance.
function junction!(vessels,sides,dt)
    n=length(vessels); rho=vessels[1].rho
    ids=[sides[k]==1 ? vessels[k].M : 1 for k=1:n]
    walls=[vessels[k].laws[ids[k]+1] for k=1:n]
    inv=[outgoing(vessels[k],sides[k],dt) for k=1:n]
    heads=[pressure(vessels[k].A[ids[k]],walls[k])+.5rho*vessels[k].u[ids[k]]^2 for k=1:n]
    pscale=sum(w.b for w in walls)/n
    qscale=sum(w.ad*wave_speed(w.ad,w,rho) for w in walls)
    x=[log(vessels[k].A[ids[k]]/walls[k].ad) for k=1:n]
    push!(x,sum(heads)/n/pscale)
    function residual(x)
        f=zeros(n+1); jac=zeros(n+1,n+1)
        for k=1:n
            a=walls[k].ad*exp(x[k]); w=walls[k]
            (a>0 && (w.kind!=:langewouters || a<w.am)) || error("Junction area domain")
            u=inv[k]-sides[k]*characteristic(a,w,rho)
            c=wave_speed(a,w,rho)
            f[k]=(pressure(a,w)+.5rho*u*u)/pscale-x[end]
            jac[k,k]=(a*dpda(a,w)-rho*u*sides[k]*c)/pscale
            jac[k,end]=-1
            f[end]+=sides[k]*a*u/qscale
            jac[end,k]=sides[k]*a*(u-sides[k]*c)/qscale
        end
        f,jac
    end
    for _=1:30
        f,jac=residual(x)
        if maximum(abs.(f))<1e-11
            for k=1:n
                a=walls[k].ad*exp(x[k]); u=inv[k]-sides[k]*characteristic(a,walls[k],rho)
                v=vessels[k]; i=ids[k]; v.A[i]=a; v.Q[i]=a*u; v.u[i]=u
            end
            flows=[vessels[k].Q[ids[k]] for k=1:n]
            return abs(sum(sides.*flows))/max(sum(abs.(flows)),eps())
        end
        step=jac\f; damping=1.; accepted=false
        for _=1:20
            trial=x-damping*step
            valid=all(isfinite(trial[k]) && (walls[k].kind!=:langewouters || walls[k].ad*exp(trial[k])<walls[k].am) for k=1:n)
            if valid
                ft,_=residual(trial)
                if maximum(abs.(ft))<maximum(abs.(f))
                    x=trial; accepted=true; break
                end
            end
            damping*=.5
        end
        accepted || error("Junction Newton line search failed")
    end
    error("Junction Newton did not converge")
end
join_vessels!(v1::Vessel,v2::Vessel,rho) = junction!([v1,v2],[1,-1],0.)
join_vessels!(v1::Vessel,v2::Vessel,v3::Vessel) = junction!([v1,v2,v3],[1,-1,-1],0.)
solveAnastomosis(v1::Vessel,v2::Vessel,v3::Vessel) = junction!([v1,v2,v3],[1,1,-1],0.)
function update_ghost_cells!(n::Network)
    for v in n.vessels_vec
        v.U00A=v.A[1]; v.U00Q=v.Q[1]; v.UM1A=v.A[end]; v.UM1Q=v.Q[end]
    end
end
