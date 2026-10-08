"""CSV export. Metadata is written as '#' comment lines above the header
(read back with pandas.read_csv(path, comment='#'))."""
import json

import numpy as np
import pandas as pd

from core.mt_1d import apparent_resistivity, phase_deg

COLS_1D = ["Frequency_Hz", "Apparent_Resistivity_OhmM", "Phase_Deg", "Impedance_Real", "Impedance_Imag"]
COLS_2D = ["Station_X_m", "Frequency_Hz", "Mode", "Apparent_Resistivity_OhmM", "Phase_Deg",
           "Impedance_Real", "Impedance_Imag"]


def frame_1d(f, Z, extra: dict | None = None) -> pd.DataFrame:
    f = np.asarray(f, float)
    Z = np.asarray(Z, complex)
    df = pd.DataFrame({COLS_1D[0]: f, COLS_1D[1]: apparent_resistivity(Z, f), COLS_1D[2]: phase_deg(Z),
                       COLS_1D[3]: Z.real, COLS_1D[4]: Z.imag})
    for k, v in (extra or {}).items():
        df[k] = v
    return df


def frame_2d(result, Zdict=None) -> pd.DataFrame:
    Zdict = Zdict or result["Z"]
    rows = []
    f = result["freq"]
    for mode, Z in Zdict.items():
        for i, fi in enumerate(f):
            for j, y in enumerate(result["stations"]):
                z = Z[i, j]
                rows.append((y, fi, mode, apparent_resistivity(z, fi), phase_deg(z), z.real, z.imag))
    return pd.DataFrame(rows, columns=COLS_2D)


def _header(meta: dict) -> str:
    lines = [f"# {meta.get('credit', '')}", f"# {meta.get('application', '')} {meta.get('version', '')}"]
    for line in json.dumps(meta, indent=1, default=str).splitlines():
        lines.append("# " + line)
    return "\n".join(lines) + "\n"


def write_csv(path, df: pd.DataFrame, meta: dict):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(_header(meta))
        df.to_csv(fh, index=False, float_format="%.8e")
