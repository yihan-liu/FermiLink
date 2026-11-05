include("ArterialPWDB.jl")
using .ArterialPWDB
const AP=ArterialPWDB
using DelimitedFiles

function run_network(input_file,out)
    config=AP.YAML.load_file(input_file)
    blood=AP.Blood(config["blood"])
    heart=AP.Heart(config["inlet_file"])
    vessels=[Dict{Any,Any}(row) for row in config["network"]]
    net=AP.Network(vessels,blood,heart,Float64(config["solver"]["cfl"]),5,["P"];verbose=false)
    period=heart.cardiac_period
    sample_times=collect(0:1/config["solver"]["sample_rate_hz"]:prevfloat(period))
    columns=3length(net.vessels_vec)
    previous=nothing; final=nothing; final_monitor=nothing
    converged=false; error_pa=Inf; cycles=0
    t=0.
    nodes=config["nodes"]
    for cycle in 1:config["solver"]["max_cycles"]
        cycle_start=(cycle-1)*period
        monitor=zeros(length(sample_times),columns)
        output=zeros(length(sample_times),1+3length(nodes))
        for (row,phase) in enumerate(sample_times)
            target=cycle_start+phase
            while t<target-1e-12
                dt=min(AP.calculateΔt(net),target-t)
                AP.solve!(net,dt,t)
                t+=dt
            end
            for (k,v) in enumerate(net.vessels_vec)
                monitor[row,3k-2:3k] .= (v.P[1],v.P[cld(v.M,2)],v.P[end])
            end
            output[row,1]=phase
            for (k,node) in enumerate(nodes)
                v=net.vessels_vec[node["segment"]]
                i=node["end"]=="proximal" ? 1 : v.M
                output[row,3k-1:3k+1] .= (v.P[i],v.Q[i],v.A[i])
            end
        end
        target=cycle*period
        while t<target-1e-12
            dt=min(AP.calculateΔt(net),target-t)
            AP.solve!(net,dt,t); t+=dt
        end
        cycles=cycle; final=output; final_monitor=monitor
        if previous!==nothing
            error_pa=maximum(sqrt.(sum((monitor.-previous).^2,dims=1)./size(monitor,1)))
            if cycle>=config["solver"]["min_cycles"] && error_pa<=config["solver"]["convergence_tolerance_pa"]
                converged=true; break
            end
        end
        previous=monitor
    end
    open(joinpath(out,"waveforms.csv"),"w") do io
        println(io,"t_s,node,P_pa,Q_m3_s,A_m2")
        for row in axes(final,1), (k,node) in enumerate(nodes)
            println(io,join((final[row,1],node["name"],final[row,3k-1],final[row,3k],final[row,3k+1]),","))
        end
    end
    open(joinpath(out,"solver_status.txt"),"w") do io
        println(io,"converged=",converged)
        println(io,"cycles=",cycles)
        println(io,"periodic_pressure_rmse_pa=",error_pa)
        println(io,"junction_mass_relative_error=",net.junction_mass_error[1])
        # Periodic trapezoid at native sample times, retaining fractional last gap.
        targets=[("root",1)]
        for node in nodes
            node["name"]=="radial" && push!(targets,("radial",3node["segment"]))
        end
        for (label,column) in targets
            trace=final_monitor[:,column]
            total=0.
            for i in eachindex(sample_times)
                j=i==length(sample_times) ? 1 : i+1
                width=i==length(sample_times) ? period-sample_times[i] : sample_times[j]-sample_times[i]
                total+=width*(trace[i]+trace[j])/2
            end
            println(io,"achieved_",label,"_map_pa=",total/period)
        end
    end
end
run_network(ARGS[1],ARGS[2])
