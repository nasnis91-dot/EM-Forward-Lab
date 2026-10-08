import numpy as np
import pandas as pd
from appinfo import CREDIT, metadata
from core.mt_1d import forward_1d
from core.mt_2d import run_2d
from export.export_csv import frame_1d, frame_2d, write_csv, COLS_1D, COLS_2D
from export.export_edi import write_edi, read_edi_impedance, SI_TO_FIELD
from export.export_excel import write_excel
from models.model_presets import preset_2d


def test_csv_roundtrip(tmp_path):
    f = np.logspace(-2, 3, 11)
    r = forward_1d([100, 10, 500], [200, 300], f)
    p = tmp_path / "a.csv"
    write_csv(p, frame_1d(f, r["Z"]), metadata(method="MT"))
    assert CREDIT in p.read_text()
    df = pd.read_csv(p, comment="#")
    assert list(df.columns) == COLS_1D
    assert np.allclose(df["Apparent_Resistivity_OhmM"], r["rho_a"], rtol=1e-7)


def test_edi_roundtrip_and_units(tmp_path):
    f = np.logspace(-3, 3, 13)
    r = forward_1d([100.0], [], f)
    p = tmp_path / "s.edi"
    write_edi(p, f, r["Z"], -r["Z"], "T1")
    ff, z = read_edi_impedance(p)
    o = np.argsort(f)[::-1]
    assert np.allclose(ff, f[o])
    assert np.allclose(z["ZXY"], r["Z"][o], rtol=1e-5)
    # field-unit check: rho_a = 0.2 T |Z_field|^2
    zf = np.abs(r["Z"][o]) * SI_TO_FIELD
    assert np.allclose(0.2 / ff * zf ** 2, 100.0, rtol=1e-6)
    txt = p.read_text()
    assert ">END" in txt and "Yanis Mawardinur" in txt


def test_2d_frames_and_excel(tmp_path):
    m = preset_2d("4 - Conductive anomaly")
    m.stations = [500.0, 2000.0]
    r = run_2d(m, [100.0])
    df = frame_2d(r)
    assert list(df.columns) == COLS_2D and len(df) == 4
    write_excel(tmp_path / "x.xlsx", df, m.to_dict(), metadata())
    assert set(pd.read_excel(tmp_path / "x.xlsx", sheet_name=None)) >= {"Data", "Model", "Metadata"}
