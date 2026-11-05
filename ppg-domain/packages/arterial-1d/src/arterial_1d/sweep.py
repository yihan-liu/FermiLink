"""Authorized fixed-HR resistance and inflow-factor sweeps with actual achieved MAP."""
import csv
from itertools import product
import json
from .manifests import Run
from .solver import simulate, hughes_reference
from ppg_forward.manifests import dump


def grid_points(config):
    """A scales terminal total R; B scales inflow/SV. No pseudo target MAP."""
    for path,factor,law,stiffness in product(config["paths"],config["factors"],config["wall_laws"],config["stiffness_scales"]):
        if path not in ("A","B"):
            raise ValueError("Only owner-approved paths A and B are implemented")
        if factor<=0 or stiffness<=0:
            raise ValueError("Sweep factors and stiffness must be positive")
        zetas=config["hughes_zeta_per_mmhg"] if law=="hughes" else [None]
        shapes=config["lang_shapes"] if law=="langewouters" else [None]
        for zeta,shape in product(zetas,shapes):
            point={**config,"path":path,"factor":factor,"wall_law":law,"stiffness_scale":stiffness,
                   "resistance_scale":factor if path=="A" else 1.,
                   "inflow_scale":factor if path=="B" else 1.}
            if zeta is not None: point["zeta_per_mmhg"]=zeta
            if shape is not None: point["lang_shape"]=shape
            yield point


def sweep(config,run):
    points=list(grid_points(config))
    if any(point["wall_law"]=="hughes" for point in points):
        reference,_=hughes_reference(config)
        run.add_inputs([reference/"manifest.json",reference/"result.json"])
    rows=[]
    for index,point in enumerate(points):
        directory=run.out/"points"/f"{index:04d}"
        with Run(directory,"arterial-1d simulate",inputs=list(run.manifest["inputs"]),parameters=point) as child:
            dump(child.out/"config.json",point)
            result=simulate(point,child)
            dump(child.out/"result.json",result); child.result=result
        transfer=json.loads((directory/"transfer.json").read_text())
        rows.append({"run_directory":str(directory),"path":point["path"],"factor":point["factor"],
                     "wall_law":point["wall_law"],"stiffness_scale":point["stiffness_scale"],
                     "zeta_per_mmhg":point.get("zeta_per_mmhg") if point["wall_law"]=="hughes" else None,
                     "lang_shape":point.get("lang_shape") if point["wall_law"]=="langewouters" else None,
                     "achieved_map_mmhg":result["achieved_map_mmhg"],
                     "achieved_root_map_mmhg":result["achieved_root_map_mmhg"],
                     "h1_phase_delay_s":transfer["h1_phase_delay_s"],
                     "group_delay_k1_3_s":transfer["group_delay_k1_3_s"],
                     "h2_over_h1":transfer["h2_over_h1"],"converged":result["converged"],"status":result["status"]})
    if not rows:
        raise ValueError("Sweep grid is empty")
    with (run.out/"sweep.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    dump(run.out/"sweep.json",rows)
    return {"status":"complete" if all(r["status"]=="complete" for r in rows) else "blocked",
            "points":len(rows),"map_axis":"achieved radial distal mean pressure (mmHg)",
            "paths":{"A":"total terminal resistance scaling; fixed inflow, R1, C, Pout and HR",
                     "B":"inflow/SV scaling; baseline R1/R2/C/Pout and fixed HR"}}
