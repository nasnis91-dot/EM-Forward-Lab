"""Application identity and shared metadata."""
import datetime as _dt

APP_NAME = "EM-Forward Lab"
APP_SUBTITLE = "MT | AMT | VLF-R — Forward Modelling & Inversion"
APP_VERSION = "2.0.0"
CREDIT = "Developed by Yanis Mawardinur — Universitas Syiah Kuala"

CONVENTIONS = {
    "time_dependence": "exp(+i*omega*t)",
    "approximation": "quasi-static (displacement currents neglected), plane-wave source",
    "coordinates": "x = strike, y = profile, z positive down",
    "impedance": "Z = Ex/Hy (TE, Zxy); TM reported as Z = -Ey/Hx so both modes give +45 deg on a half-space",
    "apparent_resistivity": "rho_a = |Z|^2 / (omega * mu0)",
    "phase": "phi = arg(Z) in degrees; homogeneous half-space = +45 deg",
    "mu0": "4*pi*1e-7 H/m",
    "units": "Z in ohm (SI) unless stated; EDI files use mV/km/nT",
}

NOISE_MODEL_TEXT = ("Z_obs = Z * (1 + p * (n_r + i*n_i)/sqrt(2)), n_r, n_i ~ N(0,1); "
                    "p = relative noise level; fixed seed for reproducibility")


def metadata(**extra) -> dict:
    m = {"application": APP_NAME, "version": APP_VERSION, "credit": CREDIT,
         "created": _dt.datetime.now().isoformat(timespec="seconds"), "conventions": CONVENTIONS}
    m.update(extra)
    return m
