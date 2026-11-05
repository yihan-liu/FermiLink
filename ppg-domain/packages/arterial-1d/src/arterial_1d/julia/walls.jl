# Explicit current-round constitutive laws. All values SI.
struct Wall
    kind::Symbol
    ad::Float64
    pd::Float64
    b::Float64
    am::Float64
    p0::Float64
    p1::Float64
end
function make_wall(config, radius)
    ad = pi*radius^2
    b = (4/3)*0.1*(config["k1"]*exp(config["k2"]*100radius)+config["k3"])*get(config,"stiffness_scale",1.0)
    kind = Symbol(config["wall_law"])
    if kind == :hughes
        b *= exp(config["zeta_per_mmhg"]*(config["run_map_pa"]-config["baseline_map_pa"])/133.322387415)
    end
    pd = config["Pext"]
    if kind == :langewouters
        q = config["lang_shape"]
        f = 0.5+atan(q)/pi
        am = ad/f
        p1 = (b/2)/(pi*f*(1+q*q))
        return Wall(kind,ad,pd,b,am,pd-q*p1,p1)
    end
    kind in (:default,:hughes) || error("Unknown wall law")
    Wall(kind,ad,pd,b,0.,0.,0.)
end
@inline function pressure(a::Float64,w::Wall)
    a>0 || error("Nonpositive arterial area")
    if w.kind == :langewouters
        a<w.am || error("Area outside Langewouters domain")
        return w.p0+w.p1*tan(pi*(a/w.am-0.5))
    end
    w.pd+w.b*(sqrt(a/w.ad)-1)
end
@inline function dpda(a::Float64,w::Wall)
    w.kind == :langewouters && return pi*w.p1/w.am/cos(pi*(a/w.am-0.5))^2
    w.b/(2sqrt(a*w.ad))
end
@inline wave_speed(a::Float64,w::Wall,rho::Float64) = sqrt(a*dpda(a,w)/rho)
@inline function potential(a::Float64,w::Wall,rho::Float64)
    if w.kind == :langewouters
        za = pi*(a/w.am-0.5); zd=pi*(w.ad/w.am-0.5)
        return w.p1/rho*(a*tan(za)-w.ad*tan(zd)+w.am/pi*(log(cos(za))-log(cos(zd))))
    end
    w.b/(3rho*sqrt(w.ad))*(a*sqrt(a)-w.ad*sqrt(w.ad))
end
const GX = (-.9602898564975363,-.7966664774136267,-.5255324099163290,-.1834346424956498,.1834346424956498,.5255324099163290,.7966664774136267,.9602898564975363)
const GW = (.1012285362903763,.2223810344533745,.3137066458778873,.3626837833783620,.3626837833783620,.3137066458778873,.2223810344533745,.1012285362903763)
@inline function characteristic(a::Float64,w::Wall,rho::Float64)
    w.kind != :langewouters && return 4*(wave_speed(a,w,rho)-wave_speed(w.ad,w,rho))
    mid=(a+w.ad)/2; half=(a-w.ad)/2
    total=0.
    for k=1:8
        aa=mid+half*GX[k]
        total += GW[k]*wave_speed(aa,w,rho)/aa
    end
    half*total
end
# Analytic geometry derivative at fixed A; q is held fixed for the Lang transfer.
function geometry_source(a,w::Wall,radius,slope,dbdr,rho)
    slope==0 && return 0.
    adr=2w.ad/radius
    if w.kind != :langewouters
        s=sqrt(a/w.ad)
        pr=dbdr*(s-1)-w.b*s/radius
        tau=w.b/sqrt(w.ad)
        taur=(dbdr-w.b/radius)/sqrt(w.ad)
        pir=(taur*(a*sqrt(a)-w.ad*sqrt(w.ad))-tau*1.5sqrt(w.ad)*adr)/(3rho)
        return slope*(pir-a/rho*pr)
    end
    amr=2w.am/radius; p1r=w.p1*dbdr/w.b
    q=(w.pd-w.p0)/w.p1; p0r=-q*p1r
    za=pi*(a/w.am-0.5); zd=pi*(w.ad/w.am-0.5)
    pr=p0r+p1r*tan(za)-w.p1/cos(za)^2*pi*a/w.am^2*amr
    g(aa,z)=aa*tan(z)+w.am/pi*log(cos(z))
    gam(aa,z)=-pi*aa^2/w.am^2/cos(z)^2+log(cos(z))/pi+aa*tan(z)/w.am
    gad=pi*w.ad/w.am/cos(zd)^2
    pir=(p1r*(g(a,za)-g(w.ad,zd))+w.p1*((gam(a,za)-gam(w.ad,zd))*amr-gad*adr))/rho
    slope*(pir-a/rho*pr)
end
