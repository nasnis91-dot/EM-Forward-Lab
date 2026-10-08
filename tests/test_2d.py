import numpy as np
from core.mt_1d import apparent_resistivity
from core.mt_2d import run_2d
from models.resistivity_2d import Model2D, Body
from models.model_presets import preset_2d, PRESETS_2D
from core.validation import check_2d


def test_2d_validation_suite():
    for r in check_2d():
        assert r["passed"], r


def test_symmetric_body_gives_symmetric_response():
    st = list(np.linspace(0, 4000, 21))
    m = Model2D(width=4000, depth=2000, dx=50, dz=25, bg_rho=[300],
                bodies=[Body("rect", 5, "b", 1500, 2500, 200, 600)], stations=st)
    r = run_2d(m, [10.0])
    for mode in ("TE", "TM"):
        ra = apparent_resistivity(r["Z"][mode][0], 10.0)
        assert np.allclose(ra, ra[::-1], rtol=2e-3)


def test_conductor_lowers_rho_a():
    m = preset_2d("4 - Conductive anomaly", bg=300, anom=5)
    r = run_2d(m, [100.0])
    ra = apparent_resistivity(r["Z"]["TE"][0], 100.0)
    mid = len(ra) // 2
    assert ra[mid] < 0.8 * ra[0]


def test_all_presets_run():
    for name in PRESETS_2D:
        m = preset_2d(name)
        r = run_2d(m, [1000.0, 10.0])
        for mode in ("TE", "TM"):
            assert np.all(np.isfinite(r["Z"][mode]))
