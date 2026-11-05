include("ArterialPWDB.jl")
using .ArterialPWDB
using Test
const AP=ArterialPWDB
function config(kind;label="test",sn=1,tn=2,rp=.003,rd=.003)
    Dict{Any,Any}("label"=>label,"sn"=>sn,"tn"=>tn,"L"=>.02,"Rp"=>rp,"Rd"=>rd,"E"=>1.,
    "Pext"=>10000.,"wall_law"=>kind,"k1"=>3e6,"k2"=>-13.5,"k3"=>5.3849e5,"b0"=>600.,"b1"=>150.,
    "run_map_pa"=>12000.,"baseline_map_pa"=>12000.,"zeta_per_mmhg"=>.017,"lang_shape"=>.6,
    "R1"=>1e8,"R2"=>1e9,"Cc"=>1e-10,"Pout"=>4400.,"dx_m"=>.004)
end
@testset "explicit-law numerical adaptation" begin
    blood=AP.Blood(Dict("mu"=>.0025,"rho"=>1060.))
    for kind in ("default","hughes","langewouters")
        cfg=config(kind)
        w=AP.make_wall(cfg,.003); a=1.1w.ad; da=1e-5w.ad
        @test (AP.potential(a+da,w,1060.)-AP.potential(a-da,w,1060.))/(2da) ≈ a/1060*AP.dpda(a,w) rtol=1e-8
        @test (AP.characteristic(a+da,w,1060.)-AP.characteristic(a-da,w,1060.))/(2da) ≈ AP.wave_speed(a,w,1060.)/a rtol=1e-7
        dr=1e-7*.003; wp=AP.make_wall(cfg,.003+dr); wm=AP.make_wall(cfg,.003-dr)
        numerical=((AP.potential(a,wp,1060.)-AP.potential(a,wm,1060.))-a/1060*(AP.pressure(a,wp)-AP.pressure(a,wm)))/(2dr)
        dbdr=(4/3)*.1*cfg["k1"]*cfg["k2"]*100*exp(cfg["k2"]*100*.003)
        @test AP.geometry_source(a,w,.003,1.,dbdr,1060.) ≈ numerical rtol=2e-6
        v1=AP.Vessel(config(kind;label="parent",sn=1,tn=2),blood,5,["P"])
        v2=AP.Vessel(config(kind;label="child1",sn=2,tn=3,rp=.002,rd=.002),blood,5,["P"])
        v3=AP.Vessel(config(kind;label="child2",sn=2,tn=4,rp=.0022,rd=.0022),blood,5,["P"])
        for (v,u) in ((v1,.2),(v2,.05),(v3,.1))
            v.u .= u; v.Q .= v.A.*u
        end
        AP.junction!([v1,v2,v3],[1,-1,-1],0.)
        @test abs(v1.Q[end]-v2.Q[1]-v3.Q[1])/sum(abs.([v1.Q[end],v2.Q[1],v3.Q[1]])) < 1e-8
        heads=[AP.pressure(v.A[i],v.laws[i+1])+.5*1060*v.u[i]^2 for (v,i) in ((v1,v1.M),(v2,1),(v3,1))]
        @test maximum(heads)-minimum(heads) < 1e-4
        AP.junction!([v2,v3,v1],[1,1,-1],0.)
        @test abs(v2.Q[end]+v3.Q[end]-v1.Q[1])/sum(abs.([v2.Q[end],v3.Q[end],v1.Q[1]])) < 1e-8
        # A few synthetic steps exercise the actual network, boundaries and reused MUSCL.
        heart=AP.Heart(.1,[0. 1e-6;.1 1e-6],[0.,.1],[1e-6,1e-6])
        network=AP.Network([config(kind;label="root",sn=1,tn=2),config(kind;label="d1",sn=2,tn=3,rp=.002,rd=.002),config(kind;label="d2",sn=2,tn=4,rp=.002,rd=.002)],blood,heart,.2,5,["P"];verbose=false)
        t=0.
        for _=1:4
            dt=AP.calculateΔt(network)
            AP.solve!(network,dt,t); t+=dt
            parent,c1,c2=network.vessels_vec
            qs=[parent.Q[end],c1.Q[1],c2.Q[1]]
            @test abs(qs[1]-qs[2]-qs[3])/max(sum(abs.(qs)),eps())<1e-8
            hs=[AP.pressure(v.A[i],v.laws[i+1])+.5blood.rho*v.u[i]^2 for (v,i) in ((parent,parent.M),(c1,1),(c2,1))]
            @test maximum(hs)-minimum(hs)<1e-4
            for v in (c1,c2)
                @test abs(AP.pressure(v.A[end],v.laws[end-1])-v.Pc-v.R1*v.Q[end])<1e-4
                pc=v.Pc
                AP.outbc!(v,0.,blood.rho)
                @test v.Pc==pc
            end
        end
        @test all(all(isfinite,v.P) && all(v.A.>0) for v in network.vessels_vec)
    end
end
