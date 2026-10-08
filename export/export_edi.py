"""SEG EDI (MT standard) export for MT / AMT impedance data.

* Units: impedance in mV/km/nT (field units).  Z_field = Z_SI / (mu0 * 1e3) ~= 795.77 * Z_SI.
* Sign/time convention: exp(+i*omega*t), as in most modern EDI files (Zxy phase in 1st quadrant,
  Zyx in 3rd quadrant).
* 1D:  Zxx = Zyy = 0, Zxy = Z, Zyx = -Z.
* 2D (x = strike): Zxy = Z_TE, Zyx = -Z_TM, Zxx = Zyy = 0. Rotation angle 0 (data in strike frame).
* Variances: (p*|Z|)^2 from the documented noise model; for noise-free data a 1 % floor is written
  and stated in the >INFO block (EDI readers often divide by the variance).
* No tipper is written (the 2D solver does not output Hz in this version).
VLF-R data are NOT written as EDI (single-frequency transmitter data; use CSV/JSON).
"""
import datetime as dt

import numpy as np

from core.mt_1d import MU0

SI_TO_FIELD = 1.0 / (MU0 * 1e3)
EMPTY = 1.0e32


def _block(name, values, extra=""):
    values = np.asarray(values, float)
    out = [f">{name}{(' ' + extra) if extra else ''} //{values.size}"]
    for i in range(0, values.size, 5):
        out.append("  " + " ".join(f"{v: .6E}" for v in values[i:i + 5]))
    return "\n".join(out)


def edi_text(freqs, Zxy, Zyx, station="ST01", info_lines=(), var_level=0.0, y_m=0.0,
             Zxy_err=None, Zyx_err=None):
    """Zxy_err / Zyx_err: 1-sigma error per impedance component (SI, ohm). If absent, a relative
    error var_level (or a 1 % floor for noise-free data) is used."""
    f = np.asarray(freqs, float)
    order = np.argsort(f)[::-1]
    f = f[order]
    zxy = np.asarray(Zxy, complex)[order] * SI_TO_FIELD
    zyx = np.asarray(Zyx, complex)[order] * SI_TO_FIELD
    zero = np.zeros_like(zxy)
    lvl = var_level if var_level > 0 else 0.01
    if Zxy_err is not None:
        exy = np.asarray(Zxy_err, float)[order] * SI_TO_FIELD
        eyx = (np.asarray(Zyx_err, float)[order] * SI_TO_FIELD) if Zyx_err is not None else exy
        var_note = "Variance = sd^2, sd = 1-sigma error of each impedance component from the noise model"
    else:
        exy = lvl * np.abs(zxy)
        eyx = lvl * np.abs(zyx)
        var_note = f"Variance = (p*|Z|)^2 with p = {lvl:g}" + (" (1 % floor, data are noise-free)"
                                                                if var_level <= 0 else "")
    today = dt.date.today().strftime("%m/%d/%y")
    L = [">HEAD",
         f'  DATAID="{station}"', '  ACQBY="EM-Forward Lab (synthetic)"', '  FILEBY="EM-Forward Lab"',
         f"  ACQDATE={today}", f"  FILEDATE={today}", '  PROSPECT="SYNTHETIC"', '  LOC="Synthetic forward model"',
         "  LAT=+00:00:00.00", "  LONG=+000:00:00.00", "  ELEV=0", '  STDVERS="SEG 1.0"',
         '  PROGVERS="EM-Forward Lab 2.0"', f"  PROGDATE={today}", "  MAXSECT=999", f"  EMPTY={EMPTY:.1E}", "",
         ">INFO MAXINFO=999",
         "  Developed by Yanis Mawardinur - Universitas Syiah Kuala",
         "  SYNTHETIC DATA - computed by EM-Forward Lab, not field measurements.",
         "  Time dependence exp(+i*omega*t). Impedance units mV/km/nT.",
         f"  Station profile position y = {y_m:.2f} m (local synthetic coordinates).",
         "  " + var_note,
         *["  " + s for s in info_lines], "",
         ">=DEFINEMEAS", "  MAXCHAN=5", "  MAXRUN=999", "  MAXMEAS=9999", "  UNITS=M", "  REFTYPE=CART",
         "  REFLAT=+00:00:00.00", "  REFLONG=+000:00:00.00", "  REFELEV=0", "",
         ">HMEAS ID=1001.001 CHTYPE=HX X=0.0 Y=0.0 Z=0.0 AZM=0.0",
         ">HMEAS ID=1002.001 CHTYPE=HY X=0.0 Y=0.0 Z=0.0 AZM=90.0",
         ">EMEAS ID=1003.001 CHTYPE=EX X=-50.0 Y=0.0 Z=0.0 X2=50.0 Y2=0.0 Z2=0.0",
         ">EMEAS ID=1004.001 CHTYPE=EY X=0.0 Y=-50.0 Z=0.0 X2=0.0 Y2=50.0 Z2=0.0", "",
         ">=MTSECT", f'  SECTID="{station}"', f"  NFREQ={f.size}", "  HX=1001.001", "  HY=1002.001",
         "  EX=1003.001", "  EY=1004.001", "",
         _block("FREQ", f, "ORDER=DEC"), _block("ZROT", np.zeros(f.size))]
    small = 0.01 * np.minimum(exy, eyx)
    for name, z, e in (("ZXX", zero, small), ("ZXY", zxy, exy), ("ZYX", zyx, eyx), ("ZYY", zero, small)):
        L += [_block(name + "R", z.real, "ROT=ZROT"), _block(name + "I", z.imag, "ROT=ZROT"),
              _block(name + ".VAR", e ** 2, "ROT=ZROT")]
    L.append(">END")
    return "\n".join(L) + "\n"


def write_edi(path, freqs, Zxy, Zyx, station="ST01", info_lines=(), var_level=0.0, y_m=0.0,
              Zxy_err=None, Zyx_err=None):
    with open(path, "w", encoding="ascii", errors="replace") as fh:
        fh.write(edi_text(freqs, Zxy, Zyx, station, info_lines, var_level, y_m, Zxy_err, Zyx_err))


def read_edi(path):
    """General SEG-EDI reader for impedance data.

    Returns dict: freq (Hz), Z {ZXX, ZXY, ZYX, ZYY} in SI (ohm), err {..} 1-sigma per component in SI
    (None if no .VAR blocks), info (list of INFO lines), station, true_model (dict or None, only for
    EM-Forward Lab synthetic files that record the 1D model).
    """
    blocks, cur, info, head = {}, None, [], {}
    section = None
    with open(path, "r", encoding="latin-1") as fh:
        for line in fh:
            s = line.strip()
            if not s:
                continue
            if s.startswith(">"):
                tok = s[1:].split()[0].upper()
                section = tok
                if tok.startswith("=") or tok in ("HEAD", "INFO", "HMEAS", "EMEAS", "END"):
                    cur = None
                else:
                    cur = tok
                    blocks[cur] = []
                continue
            if section == "INFO":
                info.append(s)
                continue
            if section == "HEAD" and "=" in s:
                k, v = s.split("=", 1)
                head[k.strip().upper()] = v.strip().strip('"')
                continue
            if cur:
                try:
                    blocks[cur] += [float(v) for v in s.split()]
                except ValueError:
                    pass
    if "FREQ" not in blocks:
        raise ValueError("No >FREQ block found - is this an impedance EDI file?")
    f = np.array(blocks["FREQ"])
    empty = float(head.get("EMPTY", EMPTY))
    Z, E = {}, {}
    for k in ("ZXX", "ZXY", "ZYX", "ZYY"):
        if k + "R" in blocks and k + "I" in blocks:
            re, im = np.array(blocks[k + "R"]), np.array(blocks[k + "I"])
            z = (re + 1j * im) / SI_TO_FIELD
            z[(np.abs(re) >= empty * 0.99) | (np.abs(im) >= empty * 0.99)] = np.nan
            Z[k] = z
            if k + ".VAR" in blocks:
                v = np.array(blocks[k + ".VAR"])
                E[k] = np.where(v >= empty * 0.99, np.nan, np.sqrt(np.abs(v))) / SI_TO_FIELD
    if "ZXY" not in Z or "ZYX" not in Z:
        raise ValueError("EDI file has no ZXY/ZYX impedance blocks.")
    true = None
    rr = [l for l in info if l.lower().startswith("model rho (ohm.m):")]
    tt = [l for l in info if l.lower().startswith("model thickness (m):")]
    if rr:
        try:
            rho = [float(v) for v in rr[0].split(":", 1)[1].split(",") if v.strip()]
            th = [float(v) for v in tt[0].split(":", 1)[1].split(",") if v.strip()] if tt else []
            if len(th) == len(rho) - 1:
                true = {"rho": rho, "thick": th}
        except ValueError:
            true = None
    return {"freq": f, "Z": Z, "err": E or None, "info": info, "station": head.get("DATAID", ""),
            "true_model": true}


def read_edi_impedance(path):
    d = read_edi(path)
    return d["freq"], d["Z"]
