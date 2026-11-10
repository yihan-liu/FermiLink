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


# -------------------- deprecated ???? -----------------------------------------
function compute_pressure(n::Network)
    compute_pressure.(n.vessels_vec, Ref(n.blood.rho), Ref("temp"))
    compute_pressure.(n.vessels_vec, Ref(n.blood.rho), Ref("last"))
end
function compute_pressure(v::Vessel, rho::Float64, ext::String)
    A = readdlm(v.label * "_A.$(ext)")

    P = zeros(Float64, size(A))
    P[:,1] = A[:,1]

    for (i, j) in enumerate([1, v.node2, v.node3, v.node4, v.M])
        @. P[:,i+1] = pressure(A[:,i+1], v.A0[j], v.beta[j], v.Pext)

        if v.viscoelastic
            P[:,i+1] .+= v.Cv[j] .* rho ./ A[:,i+1] .* diff([A[:,i+1];A[end,i+1]])./diff([A[:,1];A[end,1]+(A[end,1]-A[end-1,1])])
        end
    end

    open(v.label * "_P.$(ext)", "w") do io
        writedlm(io, P)
    end
end
# ------------------------------------------------------------------------------

load_yaml_config(yaml_config::String) = YAML.load_file(yaml_config)

function get_conv_error(n::Network)
    error, idx = findmax(get_conv_error, n.vessels_vec)
    error, n.vessels_vec[idx].label
end

function get_conv_error(v::Vessel)
    current = @view v.waveforms["P"][:, 4]
    prev    = @view v.waveforms_prev["P"][:, 4]
    sqrt(mean(abs2.(current .- prev))) / 133.332
end

getprog(cycle::Int64, verbose::Bool) =
    verbose ?
    ProgressUnknown(desc = "Solving cycle #$cycle:", spinner = true, showspeed = true) :
    nothing
function cycle_site_stats(v::Vessel, field::String, column::Int)
    y = @view v.waveforms[field][:, column]
    return (mean(y), minimum(y), maximum(y))
end

function network_total_volume(n::Network)
    volume = 0.0
    for v in n.vessels_vec
        volume += sum(v.A) * v.dx
    end
    return volume
end

function get_inlet_file(config)::String
    if ~haskey(config, "inlet_file")
        return config["project_name"]::String * "_inlet.dat"
    end
    config["inlet_file"]
end

function preamble(yaml_config, verbose, savedir)

    verbose && println("Loading config...")
    config = load_yaml_config(yaml_config)

    project_name = config["project_name"]
    verbose && println("project name: $project_name")

    if savedir == ""
        results_dir = get(config, "output_directory", project_name * "_results")
    else
        results_dir = savedir
    end
    isdir(results_dir) && rm(results_dir, recursive = true)
    ~isdir(results_dir) && mkpath(results_dir)
    yaml_config_name = last(splitpath(yaml_config))
    cp(yaml_config, joinpath(results_dir, yaml_config_name), force = true)

    inlet_file = get_inlet_file(config)
    try
        cp(inlet_file, joinpath(results_dir, inlet_file), force = true)
    catch
        cp(joinpath([splitpath(yaml_config)[1:end-1]; inlet_file]), joinpath(results_dir, inlet_file), force=true)
    end
    cd(results_dir)

    config
end

function run_simulation(
    yaml_config::String;
    verbose::Bool = true,
    out_files::Bool = false,
    save_stats::Bool = false,
    savedir::String = "",
)
    initial_dir = pwd()
    config::Dict{String, Any} = preamble(yaml_config, verbose, savedir)

    blood = Blood(config["blood"])
    heart = Heart(get_inlet_file(config)::String)

    tempsave::Vector{String} = deepcopy(get(config, "write_results", []))
    "P" ∉ tempsave && push!(tempsave, "P")
    diagnostics = get(config, "diagnostics", false)
    diagnostics && "Q" ∉ tempsave && push!(tempsave, "Q")
    diagnostics && "A" ∉ tempsave && push!(tempsave, "A")
    network = Network(
        config["network"],
        blood,
        heart,
        config["solver"]["Ccfl"]::Float64,
        config["solver"]["jump"]::Int64,
        tempsave,
        verbose = verbose,
    )
    total_time = float(config["solver"]["cycles"]) * heart.cardiac_period
    jump::Int64 = config["solver"]["jump"]
    checkpoints = range(0, stop = heart.cardiac_period, length = jump)

    diag_sites = Tuple{String,String,String,Int,Int}[]
    if diagnostics
        positions = Dict("inlet" => 2, "quarter" => 3, "midpoint" => 4,
                         "three_quarter" => 5, "outlet" => 6)
        for entry in get(config, "diagnostics_sites", [])
            length(entry) == 3 || error("Each diagnostics_sites entry must be [label, segment, position]")
            site_label, segment_label, position = String.(entry)
            column = get(positions, position, 0)
            column != 0 || error("Unknown diagnostics position $(position)")
            vessel_index = findfirst(v -> String(v.label) == segment_label, network.vessels_vec)
            vessel_index === nothing && error("Unknown diagnostics segment $(segment_label)")
            push!(diag_sites, (site_label, segment_label, position, vessel_index, column))
        end
    end

    diag_volume_samples = Float64[]
    diag_volume_times = Float64[]
    diag_wk_residual = Float64[]
    diag_wk_time = Float64[]
    diag_wk_dt = Float64[]
    diag_wk_label = String[]
    diag_wk_iters = Int[]
    if diagnostics
        open("diagnostics_cycles.csv", "w") do io
            println(io, "cycle,cycle_error_mmHg,error_segment,volume_mean_m3,volume_end_m3,volume_change_m3,wk_step_residual_max_Pa,wk_step_residual_mean_Pa,wk_iterations_total,n_steps")
        end
        open("diagnostics_sites.csv", "w") do io
            println(io, "cycle,site,segment,position,P_mean_Pa,P_min_Pa,P_max_Pa,Q_mean_m3_s,Q_min_m3_s,Q_max_m3_s,A_mean_m2,A_min_m2,A_max_m2")
        end
        open("diagnostics_volume_steps.csv", "w") do io
            println(io, "cycle,sample,time_s,volume_m3")
        end
        open("diagnostics_windkessel_steps.csv", "w") do io
            println(io, "cycle,step,time_s,dt_s,max_residual_Pa,label,iterations")
        end
    end
    previous_volume_end = NaN

    verbose && println("\nStart simulation")

    current_time = 0.0
    passed_cycles = 0
    prog = getprog(passed_cycles, verbose)
    counter = 1
    counter_prog = 0
    conv_error::Float64 = floatmax()
    error_loc = ""
    converged = false

    try
        stats = @timed while true

            # step
            dt = calculateΔt(network)
            solve!(network, dt, current_time)
            update_ghost_cells!(network)
            verbose && (counter_prog += 1) % 100 == 0 && next!(prog)
            if diagnostics
                push!(diag_wk_residual, WK_STEP_MAX_RESIDUAL[])
                push!(diag_wk_time, current_time)
                push!(diag_wk_dt, dt)
                push!(diag_wk_label, WK_STEP_MAX_LABEL[])
                push!(diag_wk_iters, WK_STEP_TOTAL_ITERATIONS[])
            end

            if current_time >= checkpoints[counter]
                save_waveforms.(counter, current_time, network.vessels_vec)
                if diagnostics
                    push!(diag_volume_times, current_time)
                    push!(diag_volume_samples, network_total_volume(network))
                end
                counter += 1
            end

            # at the end of the cardiac cycle
            if (current_time - heart.cardiac_period * passed_cycles) >= heart.cardiac_period &&
               (current_time - heart.cardiac_period * passed_cycles + dt) > heart.cardiac_period

                # check convergence
                if passed_cycles > 0
                    # compute_pressure(network)
                    conv_error, error_loc = get_conv_error(network)
                end

                if diagnostics
                    cycle_number = passed_cycles + 1
                    volume_end = network_total_volume(network)
                    volume_mean = isempty(diag_volume_samples) ? volume_end : mean(diag_volume_samples)
                    volume_change = isnan(previous_volume_end) ? NaN : volume_end - previous_volume_end
                    wk_max = isempty(diag_wk_residual) ? NaN : maximum(diag_wk_residual)
                    wk_mean = isempty(diag_wk_residual) ? NaN : mean(diag_wk_residual)
                    wk_iters = isempty(diag_wk_iters) ? 0 : sum(diag_wk_iters)
                    open("diagnostics_cycles.csv", "a") do io
                        println(io, join((cycle_number, conv_error, error_loc, volume_mean,
                                          volume_end, volume_change, wk_max, wk_mean, wk_iters,
                                          length(diag_wk_residual)), ","))
                    end
                    for (site, segment, position, vessel_index, column) in diag_sites
                        vessel = network.vessels_vec[vessel_index]
                        pm, pmin, pmax = cycle_site_stats(vessel, "P", column)
                        qm, qmin, qmax = cycle_site_stats(vessel, "Q", column)
                        am, amin, amax = cycle_site_stats(vessel, "A", column)
                        open("diagnostics_sites.csv", "a") do io
                            println(io, join((cycle_number, site, segment, position, pm, pmin, pmax,
                                              qm, qmin, qmax, am, amin, amax), ","))
                        end
                    end
                    for k in eachindex(diag_volume_samples)
                        open("diagnostics_volume_steps.csv", "a") do io
                            println(io, join((cycle_number, k, diag_volume_times[k],
                                              diag_volume_samples[k]), ","))
                        end
                    end
                    for k in eachindex(diag_wk_residual)
                        open("diagnostics_windkessel_steps.csv", "a") do io
                            println(io, join((cycle_number, k, diag_wk_time[k], diag_wk_dt[k],
                                              diag_wk_residual[k], diag_wk_label[k],
                                              diag_wk_iters[k]), ","))
                        end
                    end
                    empty!(diag_volume_samples)
                    empty!(diag_volume_times)
                    empty!(diag_wk_residual)
                    empty!(diag_wk_time)
                    empty!(diag_wk_dt)
                    empty!(diag_wk_label)
                    empty!(diag_wk_iters)
                    previous_volume_end = volume_end
                end

                flush_waveforms.(network.vessels_vec)
                swap_waveforms!.(network.vessels_vec)
                out_files && append_last_to_out.(network.vessels_vec)

                if verbose
                    if passed_cycles > 0
                        finish!(
                            prog,
                            showvalues = [("RMSE (mmHg)", conv_error), ("@", error_loc)],
                        )
                    else
                        finish!(prog)
                    end
                    println()
                end

                checkpoints = checkpoints .+ heart.cardiac_period
                passed_cycles += 1
                prog = getprog(passed_cycles, verbose)
                counter = 1
            end

            # at the end of the simulation
            if current_time >= total_time ||
               passed_cycles == config["solver"]["cycles"] ||
               conv_error < config["solver"]["convergence_tolerance"]
                verbose && finish!(prog)
                converged = true
                break
            end
            current_time += dt
        end
        tokeep::Vector{String} = get(config, "write_results", [])
        cleanup.(network.vessels_vec, Ref(tokeep))

        verbose && printstats(stats, converged, passed_cycles)
        save_stats && savestats(stats, converged, passed_cycles, config["project_name"])
    catch e
        println("\nAn error occurred, terminating simulation.\n")
        println(e)
    end

    cd(initial_dir)
end

function cleanup(v::Vessel, tokeep)
    ~v.tosave && rm.(glob("$(v.label)_*"))
    for l in ("P", "A", "Q", "u")
        l ∉ tokeep && rm.(glob("$(v.label)_$l.*"), force=true)
    end
end

function printstats(s, converged, passed_cycles)
    if converged
        println("Simulation converged after $passed_cycles cardiac cycles")
    else
        println("Simulation not converged, stopping after $passed_cycles cardiac cycles")
    end
    @printf "Elapsed time: %5.2fs\n" s.time
    @printf "Memory: %5.2fGB\n" s.bytes*1e-9
    gctime = @sprintf "GC time: %5.2f" s.gctime
    println("$(gctime)%")
end

function savestats(s, converged, passed_cycles, simulation_name)
    open("$simulation_name.conv", "w") do io
        println(io, "$converged")
        println(io, "$passed_cycles")
        println(io, "$(s.time)")
        println(io, "$(s.bytes)")
        println(io, "$(s.gctime)")
    end
end
