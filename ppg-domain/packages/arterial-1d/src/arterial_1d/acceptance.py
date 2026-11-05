"""Compare actual saved solver output on source common-root time without fitting."""
import csv
import json
from pathlib import Path
import numpy as np
from .pwdb import load_baseline, reference, periodic_interpolate
from ppg_forward.manifests import dump, validate_run
from .solver import harmonic_phasors, harmonic_transfer


def compare(simulation, baseline, out, tolerances, *, refinement):
    """Thresholds are supplied before numerical execution by the approved config.

    Expected actual solver CSV columns: t_s,node,P_pa,Q_m3_s,A_m2.
    Engineering reproduction and timing thresholds are distinct explicit inputs.
    """
    root = Path(simulation)
    manifest = json.loads((root/"manifest.json").read_text())
    result = json.loads((root/"result.json").read_text())
    for directory in (simulation,refinement):
        audit=validate_run(directory)
        if not audit["valid"]: raise ValueError("Invalid simulation manifest: "+str(audit["errors"]))
    if manifest["status"] != "complete" or result.get("converged") is not True:
        raise ValueError("Acceptance requires a complete, periodically converged simulation")
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
    observed_tf=harmonic_transfer(at,actual_signals["radial_P"],actual_signals["digital_A"],period)
    expected_tf=harmonic_transfer(at,reference_signals["radial_P"],reference_signals["digital_A"],period)
    def h1(tf):
        h=tf["harmonics"][0]
        return complex(h["real"],h["imag"])
    transfer_delay_error_s=float(abs(np.angle(h1(observed_tf)/h1(expected_tf)))*period/(2*np.pi))
    refined=json.loads((Path(refinement)/"transfer.json").read_text())
    refined_result=json.loads((Path(refinement)/"result.json").read_text())
    if refined_result.get("converged") is not True:
        raise ValueError("Refinement simulation must be periodically converged")
    refinement_delay_change_s=float(abs(np.angle(h1(observed_tf)/h1(refined)))*period/(2*np.pi))
    refinement_h2_ratio_change=abs(observed_tf["h2_over_h1"]-refined["h2_over_h1"])
    aggregate={"transfer_delay_error_s":transfer_delay_error_s,
               "refinement_delay_change_s":refinement_delay_change_s,
               "refinement_h2_ratio_change":refinement_h2_ratio_change,
               "junction_mass_relative_error":max(result["junction_mass_relative_error"],refined_result["junction_mass_relative_error"])}
    aggregate["pass"]=all(aggregate[name]<=limit for name,limit in tolerances["aggregate"].items())
    result = {"pass":all(item["pass"] for item in comparisons.values()) and aggregate["pass"],
              "metrics":comparisons,"aggregate":aggregate,"tolerances":tolerances,
              "time_registration":"published source onset offsets; no fitted shifts or amplitudes"}
    dump(Path(out)/"acceptance.json",result)
    return result
