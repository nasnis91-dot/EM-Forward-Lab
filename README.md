# EM-Forward Lab

**MT | AMT | VLF-R — Interactive Forward Modeling**
Desktop application (Python + Qt) for teaching plane-wave electromagnetic methods with
genuine 1D and 2D forward modelling.

*Developed by Yanis Mawardinur for Academic Purpose*

---

## 1. Installation

Requires **Python 3.11 or newer**.

### macOS

```bash
cd EM-Forward-Lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

If `python3` is missing, install it from python.org or with Homebrew (`brew install python@3.12`).
On Apple Silicon everything (including PySide6) installs as native arm64 wheels.

### Windows

```bat
cd EM-Forward-Lab
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

### Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

(On minimal Linux installs Qt may need `libxcb-cursor0` / `libegl1` from the package manager.)

### Run the scientific tests

```bash
python -m pytest -q          # 16 tests, ~15 s
```

The same checks are available in the app under **Validation**.

---

## 2. What the program does

| Tab | Content |
|---|---|
| **1D Forward Model** | Layer editor (table + log sliders), instant recalculation, ρa / phase / Re-Im Z, Niblett–Bostick overlay, noise, reference pinning, interpretation computed from the curve, data table, all exports |
| **2D Forward Model (TE/TM)** | 7 model presets incl. geothermal system, editable layers/rectangles/polygons, station array, Run button with progress & cancel, pseudosections, station curves (with 1D column overlay), profiles, solver diagnostics, mesh-convergence check, exports |
| **Skin Depth** | δ(f, ρ) explorer, target-depth calculator, Bostick depth of the current 1D model |
| **Compare & Sensitivity** | Multi-model comparison with Δρa / Δφ; 1D sensitivity ∂lnρa/∂lnp; 2D parameter sweeps (anomaly depth, width, ρ, thickness) |
| **Learning Mode** | Theory, rendered equations, parameters/units, limitations, 6 guided experiments loadable into the 1D tab |
| **Validation** | Runs the 20 numerical checks and shows the numbers |

Sessions (all tabs) are saved/opened from **File → Save/Open session** (JSON).

### Methods and source assumptions

| Method | Preset band | Source | Modelled as |
|---|---|---|---|
| MT | 10⁻⁴ – 10³ Hz | natural | plane wave |
| AMT | 1 – 10⁵ Hz | natural (sferics) | plane wave |
| VLF-R | transmitter frequencies (15–30 kHz) | VLF navigation transmitters | plane wave **far field only**; r/δ check per frequency, violations shaded red |

Presets are educational, not instrument limits. Near-field / controlled-source effects are **not** modelled.

---

## 3. Governing equations and conventions

* Time dependence **exp(+iωt)**, quasi-static, μ = μ₀ = 4π·10⁻⁷ H/m, z positive down, x = strike.
* Z = Eₓ/H_y (TE). TM is reported as −E_y/Hₓ so that both modes give **+45°** on a half-space.
* ρa = |Z|²/(ωμ₀), φ = arg Z, δ = √(2ρ/ωμ₀) ≈ 503√(ρ/f).

**1D** — recursion from the half-space upwards, overflow-free tanh:

```
k_j  = sqrt(i ω μ0 σ_j),   Z0_j = i ω μ0 / k_j
Z_j  = Z0_j (Z_{j+1} + Z0_j tanh(k_j h_j)) / (Z0_j + Z_{j+1} tanh(k_j h_j))
```

**2D** — node-based finite volumes on a tensor mesh (SciPy sparse, SuperLU):

```
TE:  ∂²Ex/∂y² + ∂²Ex/∂z² = iωμ0σ Ex          (air included, σ_air = 1e-10 S/m)
TM:  ∂/∂y(ρ ∂Hx/∂y) + ∂/∂z(ρ ∂Hx/∂z) = iωμ0 Hx   (earth only, Hx = 1 at surface)
```

* Mesh rebuilt for every frequency: cells ≤ δ/10 near the surface and in conductors reached by the
  field, ≥ 5 skin depths of geometric padding (sides, bottom, air).
* Dirichlet boundaries from 1D solutions of the edge columns; model extended laterally and downward.
* Surface H_y / E_y by flux recovery on the half control volume below each surface node.

**Noise model:** Z_obs = Z·(1 + p(n_r + i n_i)/√2), n ~ N(0,1), fixed seed. ⇒ σ(ρa)/ρa ≈ √2·p, σ(φ) ≈ p/√2 rad.

---

## 4. Validation results (from `core/validation.py`)

| Check | Result |
|---|---|
| 1D half-space: ρa = ρ, φ = 45° | error ≤ 1e-15 |
| 1D recursion vs independent fine-mesh FD (3 models) | ≤ 0.013 % ρa, ≤ 0.01° |
| Asymptotes / phase range / phase–slope consistency | pass |
| 2D TE & TM → 1D for laterally uniform models | ≤ 0.14 % ρa, ≤ 0.15° |
| TE = TM for 1D models | ≤ 0.5 % |
| Vertical contact: TM jumps, TE smooth; far field → local 1D | pass |
| Symmetric body → symmetric profile; all presets finite | pass |
| EDI round trip and unit conversion | pass |

Mesh convergence (2D): second order. With the default Δy = 25 m the TM response over the 5 Ω·m block
changes ≤ ~1.3 % on further refinement; use the **Mesh convergence check** button for your own models.

---

## 5. Export formats

* **CSV** — exact column sets requested
  (`Frequency_Hz,Apparent_Resistivity_OhmM,Phase_Deg,Impedance_Real,Impedance_Imag` and the 2D variant with
  `Station_X_m, Mode`), plus observed-data / VLF far-field columns when relevant. Metadata (model, frequencies,
  conventions, noise, solver, credit) as `#` comment lines: `pandas.read_csv(path, comment="#")`.
* **Excel** — sheets Data / Model (/Bodies) / Metadata.
* **JSON** — metadata + data; model files and full sessions are JSON too.
* **EDI (SEG 1.0)** — MT/AMT only. Units mV/km/nT, exp(+iωt), Zxy = Z_TE, Zyx = −Z_TM, variances from the noise
  model (1 % floor stated in >INFO for noise-free data). One file per station for 2D. VLF-R is not written as EDI.
* **Figures** — PNG (200 dpi) + SVG, light theme, credit line. Every plot also has a toolbar save button.
* **Report (PDF)** — model, settings, interpretation and figures, with developer credit.

---

## 6. Project structure

```
EM-Forward-Lab/
├── app.py                 # start the desktop app
├── appinfo.py             # name, credit, conventions, metadata
├── core/                  # physics & numerics (no GUI dependency → reusable in a web platform)
│   ├── mt_1d.py           # 1D recursion, ρa, φ, Bostick
│   ├── mt_2d.py           # 2D TE/TM finite-volume solver, mesh, convergence check
│   ├── fd1d.py            # 1D column FV solver (BCs + independent benchmark)
│   ├── methods.py         # MT / AMT / VLF-R presets, source assumptions, far-field check
│   ├── skin_depth.py, noise.py, validation.py
├── models/                # LayeredModel, Model2D (+ bodies), presets
├── visualization/         # matplotlib plots (dark GUI theme / light export theme)
├── export/                # CSV, Excel, JSON, EDI, PDF report
├── education/             # theory text, guided experiments, numerical interpretation
├── gui/                   # PySide6 tabs and widgets
├── examples/              # example 1D/2D models, synthetic data, generator script
└── tests/                 # pytest suite
```

The `core`, `models` and `export` packages have no Qt dependency, so they can be called directly from a
web back end later (e.g. `core.mt_1d.forward_1d`, `core.mt_2d.run_2d`).

---

## 7. Limitations

Plane-wave sources only (no CSAMT / near-field transmitter modelling); quasi-static; isotropic; no topography;
μ = μ₀; no tipper output in the 2D solver; polygon edges are staircased at mesh resolution;
Niblett–Bostick depths are approximations. Stations placed exactly on a sharp surface contact show the
mesh-dependent TM value of the contact node.

---

*Developed by Yanis Mawardinur for Academic Purpose*
