"""Actual PWDB network bridge into the package-owned openBF adaptation."""
import csv
import json
import os
from pathlib import Path
import subprocess
import numpy as np
from .pwdb import SITES, MMHG_PA, load_baseline, network, reference, wall_parameters

DOMAIN = Path("/data/liuyihan/FermiLink/ppg-domain")
RUNTIME = DOMAIN / ".runtime/julia-round3"
JULIA = RUNTIME / "runtime/julia-1.11.2/bin/julia"
JULIA_SOURCE = Path(__file__).parent / "julia"


def julia(script, *args):
    return subprocess.run([str(JULIA), "--project="+str(RUNTIME/"project"), str(JULIA_SOURCE/script), *map(str,args)],
                          env=dict(os.environ, JULIA_DEPOT_PATH=str(RUNTIME/"depot")),
                          capture_output=True, text=True)


def prepare(config, data, out):
    cfg = data["model_config"]
    law = config.get("wall_law", "default")
    if law not in ("default", "hughes", "langewouters"):
        raise ValueError("Wall law must be default, hughes or langewouters")
    if law == "langewouters" and "lang_shape" not in config:
        raise ValueError("Langewouters requires explicit normalized lang_shape")
    pd = float(cfg["dbp [mmHg]"])*MMHG_PA
    map_pa = float(cfg["mbp [mmHg]"])*MMHG_PA
    rho = float(cfg["density [kg /m^3]"])
    settings = {"Pext":pd,"wall_law":law,"E":1.,"k1":float(cfg["k1 [g/s^2/cm]"]),
                "k2":float(cfg["k2 [/cm]"]),"k3":float(cfg["k3 [g/s^2/cm]"]),
                "b0":float(cfg["b0 [g/s]"]),"b1":float(cfg["b1 [g cm/s]"]),
                "baseline_map_pa":config.get("wall_reference_map_mmhg",map_pa/MMHG_PA)*MMHG_PA,
                "run_map_pa":config.get("wall_map_mmhg",map_pa/MMHG_PA)*MMHG_PA,
                "zeta_per_mmhg":config.get("zeta_per_mmhg",.016),
                "lang_shape":config.get("lang_shape",0.),"stiffness_scale":config.get("stiffness_scale",1.),
                "dx_m":config.get("dx_m",.001),"visco-elastic":True}
    segments=[]
    resistance_scale=config.get("resistance_scale",1.)
    for seg in network(data):
        row={**settings,"label":"segment_"+str(seg["seg_no"]),"sn":seg["inlet_node"],"tn":seg["outlet_node"],
             "L":seg["length"],"Rp":seg["inlet_radius"],"Rd":seg["outlet_radius"],
             "initial_pressure":pd,"initial_flow":0.,"Pout":float(cfg["p_out [mmHg]"])*MMHG_PA}
        if seg["peripheral_r"]:
            ad,b=wall_parameters(data,seg["outlet_radius"])
            r1=rho*np.sqrt(b/(2*rho))/ad
            rtotal=seg["peripheral_r"]*resistance_scale
            if rtotal<=r1:
                raise ValueError("Terminal total R must exceed original PWDB characteristic impedance")
            row.update(R1=float(r1),R2=float(rtotal-r1),Cc=seg["peripheral_c"])
        segments.append(row)
    at=np.arange(int(np.ceil(data["period_s"]*data["fs_hz"]))) / data["fs_hz"]
    root=reference(data,"root",at)
    # Periodic closure is interpolation's repeated first sample, not a fitted endpoint correction.
    np.savetxt(out/"inlet.dat",np.column_stack((np.r_[at,data["period_s"]],np.r_[root["Q"],root["Q"][0]]*config.get("inflow_scale",1.))))
    names=config.get("nodes",["radial","digital"])
    nodes=[{"name":name,"segment":SITES[name][0],"end":"proximal" if name=="root" else "distal"} for name in names]
    return {"blood":{"mu":float(cfg["viscosity [Pa s]"]),"rho":rho},"network":segments,
            "inlet_file":str(out/"inlet.dat"),"nodes":nodes,
            "solver":{"cfl":config.get("cfl",.5),"sample_rate_hz":500.,
                      "max_cycles":config.get("max_cycles",30),"min_cycles":3,
                      "convergence_tolerance_pa":config.get("convergence_tolerance_pa",1.)}}


def harmonic_phasors(t, y, period):
    t=np.asarray(t)
    cols=[np.ones(len(t))]
    for k in range(1,6):
        cols.extend((np.cos(2*np.pi*k*t/period),np.sin(2*np.pi*k*t/period)))
    x=np.column_stack(cols)
    beta=np.linalg.lstsq(x,y,rcond=None)[0]
    return beta[1::2]-1j*beta[2::2]


def harmonic_transfer(t, radial_p, digital_a, period, phase_weights=(1.,1.,1.)):
    h=harmonic_phasors(t,digital_a,period)/harmonic_phasors(t,radial_p,period)
    phases=np.unwrap(np.angle(h[:3]))
    omega=2*np.pi*np.arange(1,4)/period
    weights=np.asarray(phase_weights,float)
    if weights.shape!=(3,) or np.any(weights<=0):
        raise ValueError("Three positive predeclared phase WLS weights are required")
    design=np.column_stack((np.ones(3),omega))
    fit=np.linalg.lstsq(design*np.sqrt(weights[:,None]),phases*np.sqrt(weights),rcond=None)[0]
    return {"input":"radial_P_pa","output":"digital_A_m2","period_s":period,
            "harmonics":[{"k":k,"real":float(z.real),"imag":float(z.imag),"phase_rad":float(np.angle(z)),
                           "gain_over_h1":float(abs(z)/abs(h[0]))} for k,z in enumerate(h,1)],
            "h1_phase_delay_s":float(-np.angle(h[0])*period/(2*np.pi)),
            "h2_over_h1":float(abs(h[1])/abs(h[0])),
            "group_delay_k1_3_s":float(-fit[1]),"phase_wls_intercept_rad":float(fit[0]),
            "phase_wls_weights":weights.tolist()}


def _solve_once(config, run):
    from ppg_forward.manifests import dump
    data=load_baseline(config["baseline"])
    prepared=prepare(config,data,run.out)
    dump(run.out/"solver_input.json",prepared)
    checked=julia("run.jl",run.out/"solver_input.json",run.out)
    (run.out/"solver.log").write_text(checked.stdout+checked.stderr)
    checked.check_returncode()
    status=dict(line.split("=",1) for line in (run.out/"solver_status.txt").read_text().splitlines())
    converged=status["converged"]=="true"
    result={"status":"complete" if converged else "blocked","converged":converged,
            "cycles":int(status["cycles"]),"periodic_pressure_rmse_pa":float(status["periodic_pressure_rmse_pa"]),
            "junction_mass_relative_error":float(status["junction_mass_relative_error"]),
            "wall_law":config.get("wall_law","default"),"nominal_map_mmhg":float(data["model_config"]["mbp [mmHg]"]),
            "achieved_map_mmhg":float(status["achieved_radial_map_pa"])/MMHG_PA,
            "achieved_root_map_mmhg":float(status["achieved_root_map_pa"])/MMHG_PA,
            "wall_map_mmhg":config.get("wall_map_mmhg",float(data["model_config"]["mbp [mmHg]"])),
            "resistance_scale":config.get("resistance_scale",1.),"inflow_scale":config.get("inflow_scale",1.),
            "stiffness_scale":config.get("stiffness_scale",1.),
            "map_control":config.get("path","baseline")}
    if result["junction_mass_relative_error"]>1e-6:
        result.update(status="blocked",reason="Junction conservation exceeded pre-run threshold")
    with (run.out/"waveforms.csv").open() as f:
        rows=list(csv.DictReader(f))
    bynode={name:[row for row in rows if row["node"]==name] for name in ("radial","digital")}
    if all(bynode.values()):
        transfer=harmonic_transfer([float(row["t_s"]) for row in bynode["radial"]],
                                  [float(row["P_pa"]) for row in bynode["radial"]],
                                  [float(row["A_m2"]) for row in bynode["digital"]],data["period_s"],config.get("phase_wls_weights",(1.,1.,1.)))
        dump(run.out/"transfer.json",transfer)
    return result


def hughes_reference(config):
    """Read the required converged public reference before any expensive solve."""
    from ppg_forward.manifests import digest, validate_run
    reference_run=Path(config["hughes_reference_run"])
    audit=validate_run(reference_run)
    if not audit["valid"]:
        raise ValueError("Hughes requires a valid converged default baseline reference run")
    reference_result=json.loads((reference_run/"result.json").read_text())
    reference_manifest=json.loads((reference_run/"manifest.json").read_text())
    if (reference_result["wall_law"]!="default" or not reference_result["converged"] or
        any(reference_result[name]!=1. for name in ("resistance_scale","inflow_scale","stiffness_scale"))):
        raise ValueError("Hughes reference must be the unscaled public default baseline")
    baseline_key=str(Path(config["baseline"]).absolute())
    if reference_manifest["inputs"].get(baseline_key)!=digest(config["baseline"]):
        raise ValueError("Hughes reference uses a different public baseline input")
    mref=reference_result["achieved_map_mmhg"]
    return reference_run,mref


def simulate(config,run):
    """Hughes freezes modulus within each solve and solves its mean self-consistently."""
    if config.get("wall_law","default")!="hughes":
        return _solve_once(config,run)
    import shutil
    from ppg_forward.manifests import dump, digest, validate_run
    from .manifests import Run
    reference_run,mref=hughes_reference(config)
    run.add_inputs([reference_run/"manifest.json",reference_run/"result.json"])
    current=mref; iterations=[]; solved=False
    for iteration in range(1,9):
        point={**config,"wall_reference_map_mmhg":mref,"wall_map_mmhg":current}
        directory=run.out/"hughes_iterations"/f"{iteration:02d}"
        with Run(directory,"arterial-1d Hughes frozen-MAP solve",inputs=list(run.manifest["inputs"]),parameters=point) as child:
            dump(child.out/"config.json",point)
            result=_solve_once(point,child)
            dump(child.out/"result.json",result); child.result=result
        achieved=result["achieved_map_mmhg"]
        mismatch=abs(achieved-current)
        iterations.append({"iteration":iteration,"wall_map_mmhg":current,"achieved_map_mmhg":achieved,
                           "difference_mmhg":mismatch,"run_directory":str(directory)})
        if result["status"]!="complete":
            break
        if mismatch<=.1:
            solved=True; break
        current=achieved
    for name in ("inlet.dat","solver_input.json","solver.log","solver_status.txt","waveforms.csv","transfer.json"):
        source=directory/name
        if source.exists(): shutil.copyfile(source,run.out/name)
    dump(run.out/"hughes_iterations.json",iterations)
    result.update(hughes_reference_map_mmhg=mref,hughes_self_consistent=solved,
                  hughes_fixed_point_iterations=len(iterations),hughes_map_tolerance_mmhg=.1)
    if not solved:
        result.update(status="blocked",periodic_converged=result["converged"],converged=False,
                      reason="Hughes achieved-radial-MAP fixed point was not solved within eight actual solves")
    return result
