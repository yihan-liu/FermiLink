"""Compare actual saved solver output on source common-root time without fitting."""
import csv
import json
from pathlib import Path
import numpy as np
from .pwdb import load_baseline, reference, periodic_interpolate
from ppg_forward.manifests import dump, validate_run
from .solver import harmonic_phasors, harmonic_transfer


def compare(simulation, baseline, out, tolerances, *, refinement, phase_weights):
    """Thresholds are supplied before numerical execution by the approved config.

    Expected actual solver CSV columns: t_s,node,P_pa,Q_m3_s,A_m2.
    Engineering reproduction and timing thresholds are distinct explicit inputs.
    """
    root = Path(simulation)
    if root.resolve()==Path(refinement).resolve():
        raise ValueError("Refinement must be a distinct finer run")
    manifest = json.loads((root/"manifest.json").read_text())
    result = json.loads((root/"result.json").read_text())
    for directory in (simulation,refinement):
        audit=validate_run(directory)
        if not audit["valid"]: raise ValueError("Invalid simulation manifest: "+str(audit["errors"]))
    if manifest["status"] != "complete" or result.get("converged") is not True:
        raise ValueError("Acceptance requires a complete, periodically converged simulation")
    coarse=json.loads((root/"solver_input.json").read_text())
    fine=json.loads((Path(refinement)/"solver_input.json").read_text())
    if coarse["blood"] != fine["blood"] or coarse["nodes"] != fine["nodes"]:
        raise ValueError("Joint refinement requires identical blood and requested nodes")
    for original, refined_input in zip(coarse["network"],fine["network"],strict=True):
        if refined_input["dx_m"]>original["dx_m"]/2+1e-15:
            raise ValueError("Refinement must at least halve the requested spatial step")
        if {k:v for k,v in original.items() if k!="dx_m"} != {k:v for k,v in refined_input.items() if k!="dx_m"}:
            raise ValueError("Refinement changed physical network parameters")
    if fine["solver"]["cfl"]>coarse["solver"]["cfl"] or fine["solver"]["convergence_tolerance_pa"]>coarse["solver"]["convergence_tolerance_pa"]:
        raise ValueError("Refinement requires an equal or smaller CFL and convergence tolerance")
    if not np.array_equal(np.loadtxt(coarse["inlet_file"]),np.loadtxt(fine["inlet_file"])):
        raise ValueError("Refinement changed the prescribed inflow")
    with (root/"waveforms.csv").open() as f:
        rows = list(csv.DictReader(f))
    data = load_baseline(baseline)
    period = data["period_s"]
    at = np.arange(int(np.ceil(period*data["fs_hz"]))) / data["fs_hz"]
    comparisons = {}
    actual_signals = {}; reference_signals = {}
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    fig, axes = plt.subplots(3,2,figsize=(10,8),sharex=True)
    for col, site in enumerate(("radial", "digital")):
        actual = [row for row in rows if row["node"] == site]
        t = np.array([float(row["t_s"]) for row in actual])
        expected = reference(data,site,at)
        for row,(q,key) in enumerate((("P","P_pa"),("Q","Q_m3_s"),("A","A_m2"))):
            values = np.array([float(item[key]) for item in actual])
            observed = periodic_interpolate(t,values,period,at)
            ref = expected[q]
            span = np.ptp(ref)
            phasor_ref = harmonic_phasors(at,ref,period)[0]
            phasor_sim = harmonic_phasors(at,observed,period)[0]
            actual_signals[site+"_"+q]=observed
            reference_signals[site+"_"+q]=ref
            phase_error = abs(np.angle(phasor_sim/phasor_ref))
            metrics = {"nrmse":float(np.sqrt(np.mean((observed-ref)**2))/span),
                       "mean_error_over_range":float(abs(np.mean(observed-ref))/span),
                       "mean_relative_error":float(abs(np.mean(observed-ref))/abs(np.mean(ref))),
                       "harmonic1_phase_error_rad":float(phase_error),
                       "harmonic1_equivalent_timing_error_ms":float(1000*period*phase_error/(2*np.pi))}
            metrics["pass"] = all(metrics[name] <= limit for name,limit in tolerances["quantities"][q].items())
            comparisons[site+"_"+q] = metrics
            axes[row,col].plot(at,ref,label="PWDB common-root reference")
            axes[row,col].plot(at,observed,label="actual solver")
            axes[row,col].set_ylabel(key); axes[row,col].set_title(site)
    axes[0,0].legend(); axes[2,0].set_xlabel("root time (s)"); axes[2,1].set_xlabel("root time (s)")
    fig.tight_layout(); fig.savefig(Path(out)/"comparison.png",dpi=160); plt.close(fig)
    observed_tf=harmonic_transfer(at,actual_signals["radial_P"],actual_signals["digital_A"],period,phase_weights)
    expected_tf=harmonic_transfer(at,reference_signals["radial_P"],reference_signals["digital_A"],period,phase_weights)
    def h1(tf):
        h=tf["harmonics"][0]
        return complex(h["real"],h["imag"])
    transfer_delay_error_s=float(abs(np.angle(h1(observed_tf)/h1(expected_tf)))*period/(2*np.pi))
    refined=json.loads((Path(refinement)/"transfer.json").read_text())
    refined_result=json.loads((Path(refinement)/"result.json").read_text())
    if refined_result.get("converged") is not True:
        raise ValueError("Refinement simulation must be periodically converged")
    refinement_delay_change_s=float(abs(np.angle(h1(observed_tf)/h1(refined)))*period/(2*np.pi))
    if refined["phase_wls_weights"] != list(phase_weights):
        raise ValueError("Refinement must use the same predeclared phase WLS weights")
    refinement_h2_ratio_relative_change=abs(observed_tf["h2_over_h1"]-refined["h2_over_h1"])/abs(refined["h2_over_h1"])
    aggregate={"transfer_delay_error_s":transfer_delay_error_s,
               "transfer_group_delay_error_s":abs(observed_tf["group_delay_k1_3_s"]-expected_tf["group_delay_k1_3_s"]),
               "refinement_delay_change_s":refinement_delay_change_s,
               "refinement_group_delay_change_s":abs(observed_tf["group_delay_k1_3_s"]-refined["group_delay_k1_3_s"]),
               "refinement_h2_ratio_relative_change":refinement_h2_ratio_relative_change,
               "junction_mass_relative_error":max(result["junction_mass_relative_error"],refined_result["junction_mass_relative_error"])}
    aggregate["pass"]=all(aggregate[name]<=limit for name,limit in tolerances["aggregate"].items())
    result = {"pass":all(item["pass"] for item in comparisons.values()) and aggregate["pass"],
              "metrics":comparisons,"aggregate":aggregate,"tolerances":tolerances,
              "time_registration":"published source onset offsets; no fitted shifts or amplitudes"}
    dump(Path(out)/"acceptance.json",result)
    return result
