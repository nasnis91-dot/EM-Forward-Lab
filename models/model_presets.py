"""Example 1D and 2D models used in the GUI and in classroom exercises."""
import numpy as np

from .layered_earth import LayeredModel
from .resistivity_2d import Body, Model2D

PRESETS_1D = {
    "A - Homogeneous earth": LayeredModel([100.0], [], ["Half-space"], "Model A - Homogeneous earth"),
    "B - Conductive layer": LayeredModel([100.0, 10.0, 500.0], [200.0, 300.0],
                                         ["Overburden", "Conductive layer", "Basement"],
                                         "Model B - Conductive layer"),
    "C - Resistive layer": LayeredModel([20.0, 1000.0, 50.0], [200.0, 300.0],
                                        ["Conductive cover", "Resistive layer", "Half-space"],
                                        "Model C - Resistive layer"),
    "D - Four-layer earth": LayeredModel([50.0, 500.0, 5.0, 1000.0], [100.0, 400.0, 600.0],
                                         ["Soil / sediments", "Resistive volcanics", "Clay / conductor",
                                          "Crystalline basement"], "Model D - Four-layer earth"),
    "E - Interpretation exercise": LayeredModel([100.0, 5.0, 1000.0], [50.0, 200.0],
                                                ["Top soil", "Conductive clay", "Basement"],
                                                "Model E - Interpretation exercise"),
}


def _stations(width, n=21):
    return list(np.round(np.linspace(0.05 * width, 0.95 * width, n), 1))


def preset_2d(name: str, bg=None, anom=None, a_width=1000.0, a_top=200.0, a_thick=400.0,
              width=4000.0, depth=2000.0, dx=25.0, dz=25.0) -> Model2D:
    """Build a 2D preset. The anomaly parameters are used where meaningful.
    bg / anom default to the preset's own values (PRESET_2D_DEFAULTS)."""
    d_bg, d_an = PRESET_2D_DEFAULTS.get(name[:1], (100.0, 10.0))
    bg = d_bg if bg is None else bg
    anom = d_an if anom is None else anom
    cx = width / 2
    m = Model2D(title=name, width=width, depth=depth, dx=dx, dz=dz, bg_rho=[bg], bg_thick=[],
                stations=_stations(width))
    if name.startswith("1"):           # Horizontal layers
        m.bg_rho, m.bg_thick = [bg, anom, 10 * bg], [a_top, a_thick]
    elif name.startswith("2"):         # Vertical fault (dipping allowed via polygon)
        m.bodies = [Body("polygon", anom, "Downthrown block",
                         points=[(cx, 0.0), (width * 10, 0.0), (width * 10, depth * 10), (cx, depth * 10)])]
    elif name.startswith("3"):         # Conductive basin in resistive basement
        m.bg_rho = [10 * bg] if bg < 1000 else [bg]
        hw = a_width / 2
        m.bodies = [Body("polygon", anom, "Sedimentary basin",
                         points=[(cx - hw - 0.6 * a_thick, 0.0), (cx + hw + 0.6 * a_thick, 0.0),
                                 (cx + hw, a_thick), (cx - hw, a_thick)])]
    elif name.startswith("4"):         # Conductive anomaly
        m.bodies = [Body("rect", anom, "Conductor", cx - a_width / 2, cx + a_width / 2, a_top, a_top + a_thick)]
    elif name.startswith("5"):         # Resistive intrusion
        m.bodies = [Body("rect", anom, "Intrusion", cx - a_width / 2, cx + a_width / 2, a_top, a_top + a_thick)]
    elif name.startswith("6"):         # Geothermal system
        m.bg_rho = [bg]
        m.bodies = [
            Body("polygon", 60.0, "Reservoir (propylitic)",
                 points=[(cx - 1300, 900), (cx + 1300, 900), (cx + 1000, 1800), (cx - 1000, 1800)]),
            Body("polygon", 4.0, "Clay cap (smectite)",
                 points=[(cx - 1600, 380), (cx - 800, 230), (cx, 180), (cx + 800, 230), (cx + 1600, 380),
                         (cx + 1500, 700), (cx + 800, 540), (cx, 500), (cx - 800, 540), (cx - 1500, 700)]),
            Body("polygon", 8.0, "Fault zone (fluid pathway)",
                 points=[(cx + 500, 0), (cx + 650, 0), (cx + 1250, depth), (cx + 1100, depth)]),
            Body("rect", 60.0, "Weathered layer", -1e9, 1e9, 0, 30),
        ]
    else:                              # Custom: start with one rectangle
        m.bodies = [Body("rect", anom, "Body 1", cx - a_width / 2, cx + a_width / 2, a_top, a_top + a_thick)]
    return m


PRESETS_2D = ["1 - Horizontal layers", "2 - Vertical fault", "3 - Conductive basin", "4 - Conductive anomaly",
              "5 - Resistive intrusion", "6 - Geothermal system", "7 - Custom model"]

PRESET_2D_DEFAULTS = {   # bg, anomaly rho
    "1": (100.0, 10.0), "2": (100.0, 10.0), "3": (100.0, 5.0), "4": (300.0, 5.0),
    "5": (30.0, 1000.0), "6": (300.0, 10.0), "7": (100.0, 10.0),
}
