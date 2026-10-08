"""Regenerate the example models and synthetic data sets in this folder.
Run from the project root:  python examples/make_examples.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from appinfo import CREDIT, metadata  # noqa: E402
from core.methods import frequencies  # noqa: E402
from core.mt_1d import forward_1d  # noqa: E402
from core.mt_2d import run_2d  # noqa: E402
from core.noise import add_impedance_noise  # noqa: E402
from export.export_csv import frame_1d, frame_2d, write_csv  # noqa: E402
from export.export_edi import write_edi  # noqa: E402
from export.export_json import write_json  # noqa: E402
from models.model_presets import PRESETS_1D, PRESETS_2D, preset_2d  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(HERE, "models_1d"), exist_ok=True)
os.makedirs(os.path.join(HERE, "models_2d"), exist_ok=True)
os.makedirs(os.path.join(HERE, "synthetic_data"), exist_ok=True)

for k, m in PRESETS_1D.items():
    write_json(os.path.join(HERE, "models_1d", f"model_{k[0]}.json"),
               {"type": "EM-Forward Lab 1D model", "credit": CREDIT, "model": m.to_dict()})
for k in PRESETS_2D:
    write_json(os.path.join(HERE, "models_2d", f"model2d_{k[0]}.json"),
               {"type": "EM-Forward Lab 2D model", "credit": CREDIT, "model": preset_2d(k).to_dict()})

# 1D: Model B, MT band, clean and 3 % noise
m = PRESETS_1D["B - Conductive layer"]
f = frequencies(1e-4, 1e3, 41)
r = forward_1d(m.rho, m.thick, f)
meta = metadata(method="MT", model=m.to_dict(), noise_level=0.0)
write_csv(os.path.join(HERE, "synthetic_data", "1D_modelB_MT_clean.csv"), frame_1d(f, r["Z"]), meta)
Zn = add_impedance_noise(r["Z"], 0.03, 12345)
write_csv(os.path.join(HERE, "synthetic_data", "1D_modelB_MT_noise3pct.csv"), frame_1d(f, Zn),
          metadata(method="MT", model=m.to_dict(), noise_level=0.03, noise_seed=12345))
write_edi(os.path.join(HERE, "synthetic_data", "1D_modelB_MT.edi"), f, r["Z"], -r["Z"], "MODELB")

# 2D: conductive anomaly, AMT, TE + TM
m2 = preset_2d("4 - Conductive anomaly")
r2 = run_2d(m2, frequencies(1.0, 1e5, 13))
write_csv(os.path.join(HERE, "synthetic_data", "2D_conductive_anomaly_AMT.csv"), frame_2d(r2),
          metadata(method="AMT", model=m2.to_dict(), modes=["TE", "TM"]))
print("Examples written to", HERE)
