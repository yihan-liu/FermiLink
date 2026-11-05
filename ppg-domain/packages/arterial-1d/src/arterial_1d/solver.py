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
                "baseline_map_pa":map_pa,"run_map_pa":map_pa,
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
    np.savetxt(out/"inlet.dat",np.column_stack((np.r_[at,data["period_s"]],np.r_[root["Q"],root["Q"][0]])))
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


def harmonic_transfer(t, radial_p, digital_a, period):
    h=harmonic_phasors(t,digital_a,period)/harmonic_phasors(t,radial_p,period)
    return {"input":"radial_P_pa","output":"digital_A_m2","period_s":period,
            "harmonics":[{"k":k,"real":float(z.real),"imag":float(z.imag),"phase_rad":float(np.angle(z)),
                           "gain_over_h1":float(abs(z)/abs(h[0]))} for k,z in enumerate(h,1)],
            "h1_phase_delay_s":float(-np.angle(h[0])*period/(2*np.pi)),
            "h2_over_h1":float(abs(h[1])/abs(h[0]))}


def simulate(config, run):
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
            "map_control":"baseline inflow and Pout; no target-MAP control applied"}
    if result["junction_mass_relative_error"]>1e-6:
        result.update(status="blocked",reason="Junction conservation exceeded pre-run threshold")
    with (run.out/"waveforms.csv").open() as f:
        rows=list(csv.DictReader(f))
    bynode={name:[row for row in rows if row["node"]==name] for name in ("radial","digital")}
    if all(bynode.values()):
        transfer=harmonic_transfer([float(row["t_s"]) for row in bynode["radial"]],
                                  [float(row["P_pa"]) for row in bynode["radial"]],
                                  [float(row["A_m2"]) for row in bynode["digital"]],data["period_s"])
        dump(run.out/"transfer.json",transfer)
    return result
