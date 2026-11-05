import unittest
import tempfile
from pathlib import Path
import numpy as np
from openbf_walls.solver import prepare, julia
import json
import csv


def baseline():
    config={"dbp [mmHg]":"74.9","mbp [mmHg]":"88.925","density [kg /m^3]":"1060",
            "viscosity [Pa s]":".0025","p_out [mmHg]":"33.2","k1 [g/s^2/cm]":"3000000",
            "k2 [/cm]":"-13.5","k3 [g/s^2/cm]":"538490","b0 [g/s]":"600","b1 [g cm/s]":"150"}
    data={"model_config":config,"period_s":.1,"fs_hz":500.,"onset_times":{},"waveforms":{},
          "geometry":[dict(seg_no="1",inlet_node="1",outlet_node="2",length=".02",inlet_radius=".003",outlet_radius=".002",peripheral_r="1e9",peripheral_c="1e-10")]}
    for q,value in (("P",80.),("U",.1),("A",1e-5)):
        data["onset_times"]["AorticRoot_"+q]=0.
        data["waveforms"]["AorticRoot_"+q]=[value]*50
    return data


class ControlTests(unittest.TestCase):
    def test_A_B_controls_and_fixed_outlet_split(self):
        data=baseline()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            parent=Path(tmp)
            prepared=[]
            for i,cfg in enumerate(({}, {"wall_law":"langewouters","lang_shape":.6,"stiffness_scale":1.2},
                                    {"resistance_scale":1.2},{"inflow_scale":.8})):
                out=parent/str(i); out.mkdir()
                prepared.append(prepare(cfg,data,out))
            ref,law,resistance,inflow=[p["network"][0] for p in prepared]
            self.assertEqual((ref["R1"],ref["R2"],ref["Cc"]),(law["R1"],law["R2"],law["Cc"]))
            self.assertEqual(ref["R1"],resistance["R1"])
            self.assertAlmostEqual((resistance["R1"]+resistance["R2"])/(ref["R1"]+ref["R2"]),1.2)
            self.assertEqual((ref["R1"],ref["R2"]),(inflow["R1"],inflow["R2"]))
            inlet0=np.loadtxt(prepared[0]["inlet_file"]); inlet3=np.loadtxt(prepared[3]["inlet_file"])
            np.testing.assert_equal(inlet0[:,0],inlet3[:,0])
            np.testing.assert_allclose(inlet3[:,1],.8*inlet0[:,1])

    def test_actual_driver_reports_cycle_budget_without_false_convergence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            out=Path(tmp)
            cfg=prepare({"dx_m":.004},baseline(),out)
            template=cfg["network"][0]
            cfg["network"]=[{**template,"label":"root","sn":1,"tn":2},
                            {**template,"label":"child1","sn":2,"tn":3},
                            {**template,"label":"child2","sn":2,"tn":4}]
            cfg["nodes"]=[{"name":"radial","segment":2,"end":"distal"},
                          {"name":"digital","segment":3,"end":"distal"}]
            cfg["solver"].update(max_cycles=1,cfl=.2)
            np.savetxt(out/"inlet.dat",[[0.,1e-6],[.001,1e-6]])
            source=out/"input.json"; source.write_text(json.dumps(cfg))
            checked=julia("run.jl",source,out)
            self.assertEqual(checked.returncode,0,checked.stdout+checked.stderr)
            status=dict(line.split("=",1) for line in (out/"solver_status.txt").read_text().splitlines())
            self.assertEqual(status["converged"],"false")
            self.assertEqual(status["cycles"],"1")
            with (out/"waveforms.csv").open() as f:
                rows=list(csv.DictReader(f))
            self.assertEqual({row["node"] for row in rows},{"radial","digital"})
            self.assertTrue(all(np.isfinite(float(row["P_pa"])) for row in rows))
