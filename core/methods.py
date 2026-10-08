"""Method definitions: frequency presets and explicit SOURCE ASSUMPTIONS.

MT and AMT use natural sources and the plane-wave assumption is standard.
VLF-R uses distant VLF navigation transmitters.  EM-Forward Lab models it ONLY
in the far-field (plane-wave) regime.  Finite-distance transmitter effects
(near-field / transition zone) are NOT modelled; instead a far-field validity
check r / delta is reported per frequency.
"""
from __future__ import annotations

import numpy as np

from .skin_depth import skin_depth

METHODS = {
    "MT": {
        "name": "Magnetotelluric",
        "fmin": 1e-4, "fmax": 1e3, "n": 41,
        "source": "natural",
        "assumption": (
            "Natural source (ionospheric/magnetospheric currents, f < ~1 Hz; lightning, f > ~1 Hz). "
            "Plane-wave assumption is standard: the source is far away and laterally extensive "
            "compared with the skin depth."),
        "edi": True,
    },
    "AMT": {
        "name": "Audio Magnetotelluric",
        "fmin": 1.0, "fmax": 1e5, "n": 41,
        "source": "natural",
        "assumption": (
            "Natural source (mainly global lightning / sferics). Plane-wave assumption. "
            "Note the AMT 'dead band' (~1-5 kHz) where natural signal is weak; this affects real "
            "data quality, not the forward response."),
        "edi": True,
    },
    "VLF-R": {
        "name": "Very Low Frequency - Resistivity",
        "fmin": 1.5e4, "fmax": 3e4, "n": 9,
        "source": "VLF navigation transmitters",
        "assumption": (
            "Uses VLF navigation transmitters (15-30 kHz) thousands of km away: far-field plane wave "
            "is normally well justified. Each transmitter gives ONE frequency; the 2D mode (TE/TM) "
            "is set by the transmitter azimuth relative to geological strike (E parallel to strike "
            "-> TE / E-polarisation). Exported as a documented CSV/JSON format, not EDI."),
        "edi": False,
    },
}

# Commonly listed VLF transmitters (frequency in Hz). Operational status changes; verify before field use.
VLF_TRANSMITTERS = {
    "NWC  (Exmouth, Australia) 19.8 kHz": 19800.0,
    "NPM  (Hawaii, USA) 21.4 kHz": 21400.0,
    "JJI  (Ebino, Japan) 22.2 kHz": 22200.0,
    "GQD  (Anthorn, UK) 22.1 kHz": 22100.0,
    "DHO38 (Rhauderfehn, Germany) 23.4 kHz": 23400.0,
    "NAA  (Cutler, Maine, USA) 24.0 kHz": 24000.0,
    "NLK  (Jim Creek, USA) 24.8 kHz": 24800.0,
    "VTX3 (South Vijayanarayanam, India) 18.2 kHz": 18200.0,
}

FAR_FIELD_FACTOR = 5.0   # r > 5 * delta considered "far field" (rule of thumb)


def frequencies(fmin: float, fmax: float, n: int, spacing: str = "log", custom=None) -> np.ndarray:
    if spacing == "custom":
        f = np.array(sorted(set(float(v) for v in (custom or []))), dtype=float)
    elif spacing == "linear":
        f = np.linspace(fmin, fmax, int(n))
    else:
        f = np.logspace(np.log10(fmin), np.log10(fmax), int(n))
    return f[::-1].copy()   # high -> low frequency (MT convention: shallow first)


def far_field_check(freqs, rho_a, distance_m: float | None):
    """Return (ratio r/delta, ok-mask). distance None -> natural source, always OK."""
    f = np.asarray(freqs, float)
    if distance_m is None or distance_m <= 0:
        return np.full(f.shape, np.inf), np.ones(f.shape, bool)
    d = skin_depth(np.asarray(rho_a, float), f)
    ratio = distance_m / d
    return ratio, ratio > FAR_FIELD_FACTOR


def quasi_static_check(freqs, rho, eps_r: float = 10.0):
    """sigma / (omega eps) ratio; > ~10 means displacement currents negligible."""
    eps0 = 8.854187817e-12
    w = 2 * np.pi * np.asarray(freqs, float)
    return (1.0 / np.asarray(rho, float)) / (w * eps_r * eps0)
