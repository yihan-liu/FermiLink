"""Native-rate harmonic and frozen-operator waveform descriptors."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .fit import fit_case
from .segments import load_selected_windows
from .tf_harmonics import compute_tf_harmonics
from .tf_delay import fit_delay, freeze_harmonic_weights, half_branch_diagnostics, operator_phase


def number(v):
    return float(v) if np.isfinite(v) else None


def reliability(table, names):
    """Within-case odd/even correlation; Spearman-Brown assumes parallel halves."""
    rows=[]
    for name in names:
        d=table[["caseid","odd_"+name,"even_"+name]].dropna()
        a,b=[],[]
        for _,case in d.groupby("caseid"):
            if len(case)<2:
                continue
            x,y=case.iloc[:,1].to_numpy(),case.iloc[:,2].to_numpy()
            a.extend(x-x.mean());b.extend(y-y.mean())
        a,b=np.asarray(a),np.asarray(b)
        r=float(np.corrcoef(a,b)[0,1]) if len(a)>=3 and np.std(a)>0 and np.std(b)>0 else None
        sb=2*r/(1+r) if r is not None and r>-1 else None
        rows.append(dict(feature=name,n_paired_windows=len(a),odd_even_r=r,
            full_mean_reliability_approx=sb,
            odd_variance=number(np.var(a,ddof=1)) if len(a)>1 else None,
            even_variance=number(np.var(b,ddof=1)) if len(b)>1 else None,
            approximation="Spearman-Brown; parallel-halves approximation, including nonlinear M0"))
    return rows


def _m0(window,operator,tf,parity,max_nfev):
    mask=None
    if parity is not None:
        t=np.arange(len(window.art))/500
        mask=np.zeros(len(t),bool)
        for start,end in tf["beat_feet_s"][parity::2]:
            mask|=(t>=start)&(t<end)
        mask=[mask]
    fitted=fit_case([window],"M0",operator,fit_fs_hz=500,
                   analysis_masks=mask,evaluate=False,max_nfev=max_nfev)
    if not fitted.get("available") or not fitted.get("success"):
        return {},fitted
    p=fitted["physiology"]
    omega=2*np.pi*p["frequency_hz"]
    poles=list(np.roots([1.,2*p["zeta"]*omega,omega*omega]))
    poles.extend(-2*np.pi*p[f"pole{i}_hz"] for i in (1,2) if p[f"pole{i}_hz"]!=p[f"zero{i}_hz"])
    dominant=max(poles,key=lambda v:np.real(v))
    return {"m0_delay_residual_s":fitted["ptt_s"],
            "m0_frequency_hz":p["frequency_hz"],"m0_damping":p["zeta"],
            "m0_dominant_pole_real_s_inv":float(np.real(dominant)),
            "m0_dominant_pole_imag_s_inv":float(abs(np.imag(dominant)))},fitted


def run_extract(segments_dir,operator_path,out_dir,*,feature_config=None,
                raw_access_callback=None,max_nfev=200,harmonics=(1,2,3)):
    """Extract all windows, then apply one frozen harmonic weighting/branch.

    With no feature_config, estimate case-balanced split noise and phase origins.
    A later call supplies that saved configuration. Model predictions use its
    same weights. Case-common delays are subtracted identically from full/halves.
    """
    out=Path(out_dir);out.mkdir(parents=True,exist_ok=True)
    root=Path(segments_dir)
    meta=json.loads((root/"selection.json").read_text())
    if meta.get("selection_mode")!="sliding":
        raise ValueError("TF extraction requires sliding selected-window metadata")
    operator_path=Path(operator_path).absolute()
    operator=dict(json.loads(operator_path.read_text()),fs_hz=500)
    config=json.loads(Path(feature_config).read_text()) if feature_config else None
    harmonics=tuple(config["harmonics"]) if config else tuple(harmonics)
    if harmonics not in ((1,2,3),(1,2)):
        raise ValueError("Group-delay harmonics must be 1,2,3 or 1,2")
    if config:
        weights=np.asarray(config["weights"],float)
        if weights.shape!=(len(harmonics),):
            raise ValueError("Frozen feature configuration requires aligned harmonic weights")
        if config.get("weight_estimation",{}).get("defined",True):
            if not np.isfinite(weights).all() or np.any(weights<=0):
                raise ValueError("Frozen feature configuration requires positive harmonic weights")
        elif (config["weights"]!=config["weight_estimation"]["weights"] or
              any(value is not None and (not np.isfinite(value) or value<=0)
                  for value in config["weights"])):
            raise ValueError("Frozen undefined harmonic weights differ from their estimate")
        if config["operator"]!=operator:
            raise ValueError("Frozen feature/operator settings differ")
    names=([f"gainratio_k{k}" for k in range(2,6)]
           +[f"phase_k{k}" for k in range(2,6)]
           +[f"groupdelay_k{k}_k{k+1}_s" for k in range(1,5)]
           +["group_delay_residual_s","h1_phase_delay_residual_s",
             "m0_delay_residual_s","m0_frequency_hz","m0_damping",
             "m0_dominant_pole_real_s_inv","m0_dominant_pole_imag_s_inv"])
    rows,records,audits,harmonic_rows=[],[],[],[]
    for w in load_selected_windows(root,fs_hz=500,raw_access_callback=raw_access_callback):
        tf=compute_tf_harmonics(w.art,w.pleth,fs_hz=500)
        row=dict(caseid=int(w.caseid),start_s=w.start_s,end_s=w.end_s,
                 timestamp_s=(w.start_s+w.end_s)/2,map_mmHg=float(np.mean(w.art)),
                 hr_bpm=tf.get("hr_bpm"),n_beats=tf.get("n_beats",0),
                 harmonics_defined=tf["defined"],reason=tf.get("reason"))
        row.update({prefix+name:None for prefix in ("","odd_","even_") for name in names})
        record=dict(caseid=w.caseid,index=len(rows));audit=dict(caseid=w.caseid,start_s=w.start_s)
        if tf["defined"]:
            for prefix,estimate,parity in (("",tf,None),("odd_",tf["odd"],0),("even_",tf["even"],1)):
                row.update({prefix+k:number(v) for k,v in estimate["features"].items()})
                h=estimate["H"]
                record[prefix+"H"]=h;record[prefix+"frequencies_hz"]=tf["frequencies_hz"]
                phase=fit_delay(h,tf["frequencies_hz"],operator,np.ones(len(harmonics)),harmonics=harmonics)
                record[prefix+"phase_rad"]=(phase["phase_rad"] if phase["defined"] else np.full(len(harmonics),np.nan))
                if np.isfinite(h[0]) and abs(h[0])>0:
                    f1=float(tf["frequencies_hz"][0])
                    guide=float(operator_phase([f1],operator)[0])
                    phi=guide+np.angle(h[0]*np.exp(-1j*guide))
                    row[prefix+"h1_phase_delay_residual_s"]=float(-phi/(2*np.pi*f1))
                for k,value in enumerate(h,1):
                    harmonic_rows.append(dict(caseid=w.caseid,start_s=w.start_s,half=prefix[:-1] or "full",k=k,
                        frequency_hz=float(tf["frequencies_hz"][k-1]),H_real=number(value.real),H_imag=number(value.imag)))
                try:
                    values,fitted=_m0(w,operator,tf,parity,max_nfev)
                except ValueError as exc:
                    values,fitted={},dict(available=False,reason=str(exc))
                row.update({prefix+k:number(v) for k,v in values.items()})
                row[prefix+"m0_converged"]=bool(fitted.get("success",False));audit[prefix+"m0"]=fitted
            records.append(record)
        rows.append(row);audits.append(audit)
    weight_info=((dict(defined=True,weights=config["weights"],harmonics=list(harmonics))
                  if config.get("weight_estimation",{}).get("defined",True)
                  else dict(config["weight_estimation"])) if config else
                 freeze_harmonic_weights(records,harmonics=harmonics))
    branch_diagnostics=[]
    if weight_info["defined"]:
        for record in records:
            estimates=[];row=rows[record["index"]]
            for prefix in ("","odd_","even_"):
                fitted=fit_delay(record[prefix+"H"],record[prefix+"frequencies_hz"],operator,
                                 weight_info["weights"],harmonics=harmonics)
                estimates.append(fitted)
                row[prefix+"group_delay_residual_s"]=fitted.get("tau_s")
                if fitted.get("h1_phase_delay_s") is not None:
                    row[prefix+"h1_phase_delay_residual_s"]=fitted["h1_phase_delay_s"]
            branch_diagnostics.append(dict(caseid=int(record["caseid"]),start_s=row["start_s"],
                **half_branch_diagnostics(*estimates)))
    phase_origins=dict(config.get("phase_origins_rad",{})) if config else {}
    table=pd.DataFrame(rows)
    if table.empty:
        table=pd.DataFrame(columns=["caseid","start_s","end_s","timestamp_s","map_mmHg","hr_bpm","harmonics_defined","n_beats","reason"]+
            [prefix+name for prefix in ("","odd_","even_") for name in names])
    for name in [f"phase_k{k}" for k in range(2,6)]:
        if not config:
            centres=[np.exp(1j*d[name].dropna().to_numpy()).mean() for _,d in table.groupby("caseid") if d[name].notna().any()]
            phase_origins[name]=float(np.angle(np.mean(centres))) if centres else 0.
        for prefix in ("","odd_","even_"):
            table[prefix+name]=phase_origins[name]+np.angle(np.exp(1j*(pd.to_numeric(table[prefix+name])-phase_origins[name])))
    for name in ("group_delay_residual_s","h1_phase_delay_residual_s"):
        for _,indices in table.groupby("caseid").groups.items():
            common=pd.to_numeric(table.loc[indices,name]).mean()
            table.loc[indices,name+"_case_common_s"]=common
            for prefix in ("","odd_","even_"):
                table.loc[indices,prefix+name]=pd.to_numeric(table.loc[indices,prefix+name])-common
    table.to_csv(out/"features.csv",index=False)
    pd.DataFrame(harmonic_rows,columns=["caseid","start_s","half","k","frequency_hz","H_real","H_imag"]).to_csv(out/"harmonics.csv",index=False)
    rel=reliability(table,names);pd.DataFrame(rel).to_csv(out/"reliability.csv",index=False)
    frozen=dict(harmonics=list(harmonics),weights=weight_info.get("weights"),weight_estimation=weight_info,
                phase_origins_rad=phase_origins,features=names,fs_hz=500,
                phase_branch="known frozen operator removed for residual unwrap, then analytic continuous operator phase restored",
                branch_assumption="residual adjacent harmonic increments within (-pi,pi)",
                operator=operator,case_common="full-window case mean; identical subtraction in odd/even")
    def save(name,value):
        (out/name).write_text(json.dumps(value,indent=2,allow_nan=False)+"\n")
    save("feature_config.json",frozen);save("branch_diagnostics.json",branch_diagnostics);save("m0_fits.json",audits)
    return dict(status="complete",n_windows=len(table),n_cases=int(table.caseid.nunique()),fs_hz=500,
                n_harmonics_defined=int(table.harmonics_defined.sum()),
                weights_defined=weight_info["defined"],input_files=[str(operator_path)]+([str(Path(feature_config).absolute())] if feature_config else []))
