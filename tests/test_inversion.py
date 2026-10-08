import numpy as np

from core.methods import frequencies
from core.mt_1d import forward_1d
from core.noise import apply_noise
from core.inversion import InvData, marquardt_auto, occam


def _data(rho, th, level=0.03, seed=1):
    f = frequencies(1e-3, 1e4, 41)
    r = forward_1d(rho, th, f)
    nz = apply_noise(r["Z"], f, "gauss_z", level, seed)
    return InvData.from_impedance(f, nz["Zobs"], nz["Zerr"], floor=level / np.sqrt(2))


def test_noise_reported_errors_give_rms_one():
    f = frequencies(1e-3, 1e4, 801)
    r = forward_1d([100, 10, 500], [200, 300], f)
    for method in ("gauss_z", "uniform_z", "gauss_rho_phase"):
        nz = apply_noise(r["Z"], f, method, 0.05, 3)
        d = InvData.from_impedance(f, nz["Zobs"], nz["Zerr"])
        dv, sd = d.vector()
        rms = np.sqrt(np.mean(((dv - d.predict([100, 10, 500], [200, 300])) / sd) ** 2))
        assert 0.85 < rms < 1.15, (method, rms)


def test_occam_reaches_target():
    res = occam(_data([100, 10, 500], [200, 300]))
    assert res["rms"] <= 1.05
    # conductor recovered between 150 and 600 m
    z = res["depth_top"]
    sel = (z > 150) & (z < 600)
    assert res["rho"][sel].min() < 30


def test_marquardt_recovers_layers():
    for rho, th in (([100, 10, 500], [200, 300]), ([50, 500, 5, 1000], [100, 400, 600])):
        res = marquardt_auto(_data(rho, th), len(rho))
        assert res["rms"] < 1.2
        k = int(np.argmin(rho[:-1]))                      # the conductive layer
        S_true = th[k] / rho[k]
        S_inv = res["thick"][k] / res["rho"][k]
        assert abs(S_inv / S_true - 1) < 0.25          # conductance is well resolved


def test_occam2d_small():
    from core.inv_2d import Data2D, occam2d
    from core.mt_2d import run_2d
    from models.model_presets import preset_2d
    m = preset_2d("4 - Conductive anomaly", bg=300, anom=5)
    m.stations = list(np.linspace(600, 3400, 8))
    f = frequencies(3, 3e3, 6)
    r = run_2d(m, f)
    Z, E = {}, {}
    for k, mo in enumerate(("TE", "TM")):
        nz = apply_noise(r["Z"][mo], f, "gauss_z", 0.03, 10 + k)
        Z[mo], E[mo] = nz["Zobs"], nz["Zerr"]
    res = occam2d(Data2D(f, m.stations, Z, E, floor=0.03), nz=8, max_iter=6)
    assert res["rms"] < res["history"][0]["rms"] / 3
    assert (10 ** res["logrho"]).min() < 100          # conductor appears
