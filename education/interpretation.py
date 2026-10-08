"""Interpretation text generated ONLY from the computed numbers (no fixed canned rules).

Every statement quotes the value it is based on, so students can verify it on the plots.
"""
import numpy as np
from scipy.signal import find_peaks

from core.mt_1d import bostick
from core.skin_depth import skin_depth


def _layer_at(depth, tops):
    return int(np.searchsorted(tops, depth, side="right") - 1)


def interpret_1d(model, f, rho_a, phase) -> list[str]:
    f = np.asarray(f, float)
    o = np.argsort(f)[::-1]                       # high -> low frequency
    f, ra, ph = f[o], np.asarray(rho_a)[o], np.asarray(phase)[o]
    rho = np.asarray(model.rho, float)
    tops = model.depths()
    dB, rB = bostick(ra, ph, f)
    out = []

    # --- shallowest information
    d1 = skin_depth(rho[0], f[0])
    diff1 = (ra[0] / rho[0] - 1) * 100
    if rho.size == 1:
        out.append(f"Homogeneous earth: ρa = {ra.mean():.4g} Ω·m and φ = {ph.mean():.2f}° at all frequencies "
                   f"(exactly ρ = {rho[0]:g} Ω·m and 45° for a half-space).")
        out.append(f"Skin depth ranges from {skin_depth(rho[0], f[0]):.3g} m at {f[0]:.3g} Hz to "
                   f"{skin_depth(rho[0], f[-1]):.3g} m at {f[-1]:.3g} Hz: lower frequency → deeper sensing.")
        return out
    h1 = model.thick[0]
    if d1 < h1:
        out.append(f"Highest frequency {f[0]:.3g} Hz: skin depth in layer 1 is {d1:.3g} m (< h₁ = {h1:g} m), "
                   f"so the field barely 'sees' deeper layers: ρa = {ra[0]:.4g} Ω·m vs ρ₁ = {rho[0]:g} Ω·m "
                   f"({diff1:+.1f} %), φ = {ph[0]:.1f}°.")
    else:
        out.append(f"Highest frequency {f[0]:.3g} Hz already penetrates below layer 1 (skin depth {d1:.3g} m ≥ "
                   f"h₁ = {h1:g} m): ρa = {ra[0]:.4g} Ω·m differs from ρ₁ = {rho[0]:g} Ω·m by {diff1:+.1f} %. "
                   "Add higher frequencies to resolve the top layer.")

    # --- deepest information
    zN = tops[-1]
    diffN = (ra[-1] / rho[-1] - 1) * 100
    if abs(diffN) < 10:
        out.append(f"Lowest frequency {f[-1]:.3g} Hz: Bostick depth ≈ {dB[-1]:.3g} m (half-space top at {zN:g} m); "
                   f"ρa = {ra[-1]:.4g} Ω·m approaches ρ_N = {rho[-1]:g} Ω·m ({diffN:+.1f} %).")
    elif dB[-1] > 2 * zN:
        S = float(np.sum(np.asarray(model.thick) / rho[:-1]))
        out.append(f"Lowest frequency {f[-1]:.3g} Hz: Bostick depth ≈ {dB[-1]:.3g} m is far below the half-space "
                   f"top ({zN:g} m), yet ρa = {ra[-1]:.4g} Ω·m is still {diffN:+.1f} % from ρ_N = {rho[-1]:g} Ω·m. "
                   f"The total conductance of the cover, S = Σh/ρ = {S:.3g} S, slows the approach to the "
                   "asymptote (typical for a resistive basement below conductive layers).")
    else:
        out.append(f"Lowest frequency {f[-1]:.3g} Hz: Bostick depth ≈ {dB[-1]:.3g} m (half-space top at {zN:g} m); "
                   f"ρa = {ra[-1]:.4g} Ω·m has not converged to ρ_N = {rho[-1]:g} Ω·m ({diffN:+.1f} %). "
                   "Lower frequencies are needed to sense the half-space.")

    # --- extrema of the apparent resistivity curve (prominence > 1 %)
    lr = np.log10(ra)
    mins, _ = find_peaks(-lr, prominence=0.01)          # prominence 0.01 decade (~2.3 %)
    maxs, _ = find_peaks(lr, prominence=0.01)
    for k in sorted(list(mins) + list(maxs)):
        is_min = k in mins
        is_max = not is_min
        j = min(max(_layer_at(dB[k], tops), 0), rho.size - 1)
        kind = "minimum" if is_min else "maximum"
        txt = (f"ρa {kind} of {ra[k]:.4g} Ω·m at {f[k]:.3g} Hz (Bostick depth ≈ {dB[k]:.3g} m; the true model "
               f"there is {model.layer_name(j)}, ρ = {rho[j]:g} Ω·m).")
        # nearest true layer of the matching type (local conductor / resistor)
        cand = []
        for i in range(1, rho.size - 1):
            if is_min and rho[i] < rho[i - 1] and rho[i] < rho[i + 1]:
                cand.append(i)
            if is_max and rho[i] > rho[i - 1] and rho[i] > rho[i + 1]:
                cand.append(i)
        def _dist(i):
            return abs(np.log10(max(dB[k], 1)) - np.log10(max(tops[i] + model.thick[i] / 2, 1)))
        cand = [i for i in cand if _dist(i) < 0.5]       # within half a decade of the Bostick depth
        if cand:
            jc = min(cand, key=_dist)
            if is_min:
                txt += (f" It reflects {model.layer_name(jc)} (ρ = {rho[jc]:g} Ω·m, top {tops[jc]:g} m) but stays above "
                        f"its true ρ because ρa is a volume average; a thin conductor is mainly resolved through its "
                        f"conductance S = h/ρ = {model.thick[jc] / rho[jc]:.3g} S.")
            else:
                txt += (f" It reflects {model.layer_name(jc)} (ρ = {rho[jc]:g} Ω·m, top {tops[jc]:g} m) but stays below "
                        f"its true ρ; a thin resistor is mainly resolved through its transverse resistance "
                        f"T = h·ρ = {model.thick[jc] * rho[jc]:.3g} Ω·m².")
        else:
            txt += (" No layer of matching type exists in the true model: this is an overshoot of the curve near a "
                    "resistivity transition (ρa is not a depth profile).")
        out.append(txt)

    # --- phase vs slope of rho_a (computed, then checked)
    above = ph > 45.0
    slope = np.gradient(lr, np.log10(f))                  # d log rho_a / d log f
    agree = np.mean((slope > 0) == above) * 100 if f.size > 2 else np.nan
    bands = []
    start = 0
    for k in range(1, f.size + 1):
        if k == f.size or above[k] != above[start]:
            bands.append((f[start], f[k - 1], above[start]))
            start = k
    desc = "; ".join(f"{a:.3g}–{b:.3g} Hz: φ {'>' if up else '<'} 45°" for a, b, up in bands)
    out.append(f"Phase bands: {desc}. φ > 45° means ρa decreases towards lower frequency (more conductive at "
               f"depth); φ < 45° means it increases. Here sign(φ − 45°) agrees with the computed ρa slope at "
               f"{agree:.0f} % of the frequencies; mismatches sit near turning points, because the phase depends "
               f"on the ρa slope over a band of frequencies, not at a single point.")
    return out


def interpret_change(f, ra_ref, ph_ref, ra, ph) -> str:
    f = np.asarray(f, float)
    d = (np.asarray(ra) / np.asarray(ra_ref) - 1) * 100
    k = int(np.argmax(np.abs(d)))
    kp = int(np.argmax(np.abs(np.asarray(ph) - np.asarray(ph_ref))))
    dB, _ = bostick(np.asarray(ra_ref)[[k]], np.asarray(ph_ref)[[k]], f[[k]])
    return (f"Compared with the reference: the largest ρa change is {d[k]:+.1f} % at {f[k]:.3g} Hz "
            f"(reference Bostick depth ≈ {dB[0]:.3g} m); the largest phase change is "
            f"{ph[kp] - ph_ref[kp]:+.2f}° at {f[kp]:.3g} Hz. Frequencies where the change is < 1 %: "
            f"{np.mean(np.abs(d) < 1) * 100:.0f} % of the band — those frequencies are insensitive to the edit.")


# ----------------------------------------------------------------------------- Indonesian rendering
_ID_PHRASES = [
    ("Homogeneous earth: ", "Bumi homogen: "), (" at all frequencies ", " pada semua frekuensi "),
    ("(exactly ρ = ", "(tepat ρ = "), (" and 45° for a half-space).", " dan 45° untuk setengah ruang)."),
    ("Skin depth ranges from ", "Skin depth berkisar dari "), (" m at ", " m pada "), (" Hz to ", " Hz hingga "),
    (": lower frequency → deeper sensing.", ": frekuensi lebih rendah → penetrasi lebih dalam."),
    ("Highest frequency ", "Frekuensi tertinggi "), (": skin depth in layer 1 is ", ": skin depth di lapisan 1 adalah "),
    ("so the field barely 'sees' deeper layers: ", "sehingga medan hampir tidak 'melihat' lapisan lebih dalam: "),
    (" already penetrates below layer 1 (skin depth ", " sudah menembus di bawah lapisan 1 (skin depth "),
    (" differs from ρ₁ = ", " berbeda dari ρ₁ = "), (" Ω·m by ", " Ω·m sebesar "),
    ("Add higher frequencies to resolve the top layer.", "Tambahkan frekuensi lebih tinggi untuk menyelesaikan lapisan atas."),
    ("Lowest frequency ", "Frekuensi terendah "), (": Bostick depth ≈ ", ": kedalaman Bostick ≈ "),
    ("(half-space top at ", "(puncak setengah ruang di "), (" approaches ρ_N = ", " mendekati ρ_N = "),
    (" is far below the half-space top (", " jauh di bawah puncak setengah ruang ("), ("), yet ρa = ", "), namun ρa = "),
    (" is still ", " masih "), (" % from ρ_N = ", " % dari ρ_N = "),
    ("The total conductance of the cover, ", "Konduktansi total lapisan penutup, "),
    (", slows the approach to the asymptote (typical for a resistive basement below conductive layers).",
     ", memperlambat pendekatan ke asimtot (khas untuk batuan dasar resistif di bawah lapisan konduktif)."),
    (" has not converged to ρ_N = ", " belum konvergen ke ρ_N = "),
    ("Lower frequencies are needed to sense the half-space.", "Diperlukan frekuensi lebih rendah untuk mendeteksi setengah ruang."),
    ("ρa minimum of ", "Minimum ρa sebesar "), ("ρa maximum of ", "Maksimum ρa sebesar "), (" Hz (Bostick depth ≈ ", " Hz (kedalaman Bostick ≈ "),
    (" m; the true model there is ", " m; model sebenarnya di sana adalah "),
    (" It reflects ", " Ini mencerminkan "), (", top ", ", puncak "),
    (" but stays above its true ρ because ρa is a volume average; a thin conductor is mainly resolved through its conductance ",
     " tetapi tetap di atas ρ sebenarnya karena ρa adalah rata-rata volume; konduktor tipis terutama terselesaikan melalui konduktansinya "),
    (" but stays below its true ρ; a thin resistor is mainly resolved through its transverse resistance ",
     " tetapi tetap di bawah ρ sebenarnya; resistor tipis terutama terselesaikan melalui resistansi transversalnya "),
    (" No layer of matching type exists in the true model: this is an overshoot of the curve near a resistivity transition (ρa is not a depth profile).",
     " Tidak ada lapisan sejenis dalam model sebenarnya: ini adalah overshoot kurva di dekat transisi resistivitas (ρa bukan profil kedalaman)."),
    ("Phase bands: ", "Pita fase: "),
    (" φ > 45° means ρa decreases towards lower frequency (more conductive at depth); φ < 45° means it increases. Here sign(φ − 45°) agrees with the computed ρa slope at ",
     " φ > 45° berarti ρa menurun ke arah frekuensi rendah (lebih konduktif di kedalaman); φ < 45° berarti meningkat. Di sini tanda(φ − 45°) sesuai dengan kemiringan ρa pada "),
    (" % of the frequencies; mismatches sit near turning points, because the phase depends on the ρa slope over a band of frequencies, not at a single point.",
     " % frekuensi; ketidaksesuaian berada di dekat titik balik, karena fase bergantung pada kemiringan ρa dalam satu pita frekuensi, bukan pada satu titik."),
    ("Compared with the reference: the largest ρa change is ", "Dibandingkan referensi: perubahan ρa terbesar "),
    ("(reference Bostick depth ≈ ", "(kedalaman Bostick referensi ≈ "), ("; the largest phase change is ", "; perubahan fase terbesar "),
    (". Frequencies where the change is < 1 %: ", ". Frekuensi dengan perubahan < 1 %: "),
    (" % of the band — those frequencies are insensitive to the edit.", " % pita — frekuensi tersebut tidak peka terhadap perubahan ini."),
    (" at ", " pada "), (" vs ", " vs "),
]


def to_id(text: str) -> str:
    for a, b in _ID_PHRASES:
        text = text.replace(a, b)
    return text
