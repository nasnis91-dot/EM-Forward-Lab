"""Learning-mode content. Equations are written as $...$ (matplotlib mathtext) inside
[[EQ: ... ]] markers; the GUI renders each marker to an image."""

TOPICS = {}

TOPICS["Overview & conventions"] = """
<h2>EM-Forward Lab — what it computes</h2>
<p>EM-Forward Lab computes the <b>surface impedance</b> of a plane electromagnetic wave travelling into the
earth, for 1D layered and 2D resistivity models. From the impedance it derives the apparent resistivity and
phase that MT, AMT and VLF-R surveys measure.</p>
<h3>Conventions (used everywhere in the program and in exported files)</h3>
<ul>
<li>Time dependence <b>exp(+iωt)</b>; quasi-static approximation (displacement currents neglected).</li>
<li>Coordinates: x = strike, y = profile, z positive <b>down</b>. μ = μ₀ = 4π×10⁻⁷ H/m.</li>
<li>Impedance Z = E<sub>x</sub>/H<sub>y</sub> (TE). The TM mode is reported as −E<sub>y</sub>/H<sub>x</sub>,
so both modes give +45° on a half-space.</li>
</ul>
[[EQ: $\\rho_a = \\dfrac{|Z|^2}{\\omega\\mu_0},\\qquad \\varphi = \\arg(Z),\\qquad \\omega = 2\\pi f$]]
<p>With exp(+iωt) a homogeneous half-space gives ρ<sub>a</sub> = ρ and φ = +45° at every frequency.
φ &gt; 45° indicates resistivity <i>decreasing</i> with depth, φ &lt; 45° resistivity <i>increasing</i>.</p>
<h3>Source assumption</h3>
<p>All responses assume a <b>plane-wave source</b>. This is standard for MT and AMT (natural sources) and
valid for VLF-R only in the far field of the transmitter (distance ≫ skin depth). Near-field transmitter
effects are <b>not</b> modelled — the program flags frequencies where the far-field criterion fails.</p>
"""

TOPICS["Magnetotellurics (MT)"] = """
<h2>Magnetotellurics (MT)</h2>
<p><b>Source:</b> natural time-varying magnetic fields. Below ~1 Hz they come from the interaction of the solar
wind with the magnetosphere/ionosphere; above ~1 Hz from worldwide lightning (sferics).</p>
<p><b>Measured:</b> orthogonal horizontal electric (E<sub>x</sub>, E<sub>y</sub>) and magnetic
(H<sub>x</sub>, H<sub>y</sub>) fields; the impedance tensor relates them:</p>
[[EQ: $E_x = Z_{xx}H_x + Z_{xy}H_y,\\qquad E_y = Z_{yx}H_x + Z_{yy}H_y$]]
<p>For 1D: Z<sub>xx</sub> = Z<sub>yy</sub> = 0 and Z<sub>xy</sub> = −Z<sub>yx</sub>. For 2D in strike coordinates
the two off-diagonal elements are the independent TE and TM responses.</p>
<p><b>Typical band:</b> 10⁻⁴ – 10³ Hz (educational preset). Depth of investigation: hundreds of metres to
hundreds of kilometres — crust and upper mantle, geothermal systems, sedimentary basins, fault zones.</p>
"""

TOPICS["Audio Magnetotellurics (AMT)"] = """
<h2>Audio Magnetotellurics (AMT)</h2>
<p>Same physics as MT, at audio frequencies (≈ 1 Hz – 100 kHz). The source is mainly global lightning
activity. Because frequencies are higher, the skin depth is smaller: AMT images the upper ~1–2 km.</p>
<p>Field practice note: around 1–5 kHz the natural signal is weak (the <i>AMT dead band</i>); this degrades
real data quality but does not change the forward response computed here.</p>
<p>Applications: geothermal clay caps, mineral exploration, groundwater, near-surface fault structure.</p>
"""

TOPICS["VLF-Resistivity (VLF-R)"] = """
<h2>VLF-Resistivity (VLF-R)</h2>
<p><b>Source:</b> powerful military navigation transmitters at 15–30 kHz (e.g. NWC Australia 19.8 kHz, the
transmitter usually used in Indonesia). They are thousands of km away, so at the survey site the field is
a <b>plane wave</b> — the same physics as MT/AMT, at a single frequency per transmitter.</p>
<p><b>Measured:</b> horizontal E (with a short dipole) and the orthogonal horizontal H, giving ρ<sub>a</sub>
and φ at each station along a profile.</p>
<p><b>Mode:</b> the transmitter azimuth relative to geological strike decides the mode. E parallel to strike
→ TE (E-polarisation); E perpendicular to strike → TM (H-polarisation, sharper response at contacts).</p>
<p><b>Depth:</b> at 20 kHz the skin depth is ~36 m in 100 Ω·m ground and ~11 m in 10 Ω·m — VLF-R is a
near-surface method. With 1D modelling and a few transmitters you get a few frequencies only, so
use the 2D tab to see VLF-R profiles across structures.</p>
<p><b>Far-field check:</b> the program reports r/δ (transmitter distance / skin depth) and marks frequencies
with r/δ &lt; 5. For real VLF transmitters this ratio is enormous and the plane-wave assumption holds.</p>
"""

TOPICS["1D forward modelling"] = """
<h2>1D layered earth — impedance recursion</h2>
<p>Layer j has resistivity ρ<sub>j</sub> (σ<sub>j</sub> = 1/ρ<sub>j</sub>) and thickness h<sub>j</sub>; the
last layer is a half-space. In each layer the field obeys</p>
[[EQ: $\\dfrac{d^2E_x}{dz^2} = i\\omega\\mu_0\\sigma_j\\,E_x = k_j^2E_x,\\qquad k_j=\\sqrt{i\\omega\\mu_0\\sigma_j}$]]
<p>with intrinsic impedance</p>
[[EQ: $Z_j^0=\\sqrt{\\dfrac{i\\omega\\mu_0}{\\sigma_j}} = \\dfrac{i\\omega\\mu_0}{k_j}$]]
<p>Starting with Z = Z<sub>N</sub><sup>0</sup> in the half-space, the impedance at the top of each layer is
obtained upwards:</p>
[[EQ: $Z_j = Z_j^0\\,\\dfrac{Z_{j+1}+Z_j^0\\tanh(k_jh_j)}{Z_j^0+Z_{j+1}\\tanh(k_jh_j)}$]]
<p>The value at the surface gives ρ<sub>a</sub> and φ. The program evaluates tanh in an overflow-free form,
so very thick or very conductive layers are handled safely.</p>
<h3>Validation</h3>
<p>The recursion is checked against (1) the exact half-space result and (2) an <b>independent</b> fine-mesh
finite-volume solution of the same differential equation (automated tests).</p>
<h3>Niblett–Bostick transform (approximate imaging)</h3>
[[EQ: $D=\\sqrt{\\dfrac{\\rho_a}{\\omega\\mu_0}},\\qquad \\rho_B=\\rho_a\\left(\\dfrac{\\pi}{2\\varphi}-1\\right)$]]
<p>Shown as orange dots on the model plot. It is a quick approximation, not an inversion.</p>
"""

TOPICS["Skin depth & sensitivity"] = """
<h2>Skin depth</h2>
[[EQ: $\\delta=\\sqrt{\\dfrac{2\\rho}{\\omega\\mu_0}}\\approx 503\\sqrt{\\dfrac{\\rho}{f}}\\ \\ \\mathrm{[m]}$]]
<p>δ is the depth where a plane wave in a <b>homogeneous</b> medium decays to 1/e (37 %). It is only an
indicator of investigation depth in a layered earth.</p>
<ul>
<li>Lower frequency → larger δ → deeper sensing.</li>
<li>Higher resistivity → larger δ. A conductive cover "shields" deeper layers.</li>
<li>Thin conductors are resolved through their conductance S = h/ρ, thin resistors through T = hρ
(equivalence). Try it with the Marquardt inversion.</li>
</ul>
<h3>Sensitivity</h3>
<p>The normalised sensitivity of the data to a parameter p is</p>
[[EQ: $S_p(f) = \\dfrac{\\partial \\ln\\rho_a(f)}{\\partial \\ln p}$]]
<p>The frequency band where |S<sub>p</sub>| is large is the band that "sees" that layer. Inversion uses exactly
these derivatives (the Jacobian).</p>
"""

TOPICS["2D forward modelling (TE / TM)"] = """
<h2>2D earth: TE and TM modes</h2>
<p>For a resistivity ρ(y, z) that is constant along strike x, Maxwell's equations split into two
independent polarisations:</p>
[[EQ: $\\mathrm{TE:}\\ \\ \\dfrac{\\partial^2E_x}{\\partial y^2}+\\dfrac{\\partial^2E_x}{\\partial z^2}=i\\omega\\mu_0\\sigma E_x,\\qquad H_y=-\\dfrac{1}{i\\omega\\mu_0}\\dfrac{\\partial E_x}{\\partial z}$]]
[[EQ: $\\mathrm{TM:}\\ \\ \\dfrac{\\partial}{\\partial y}\\left(\\rho\\dfrac{\\partial H_x}{\\partial y}\\right)+\\dfrac{\\partial}{\\partial z}\\left(\\rho\\dfrac{\\partial H_x}{\\partial z}\\right)=i\\omega\\mu_0H_x,\\qquad E_y=\\rho\\dfrac{\\partial H_x}{\\partial z}$]]
<ul>
<li><b>TE</b> (E-polarisation): currents flow along strike; the air layer must be included because
H<sub>y</sub> is perturbed above the surface. Responses vary smoothly across contacts; sensitive to
conductors.</li>
<li><b>TM</b> (H-polarisation): currents cross the structure; charges build up on boundaries. H<sub>x</sub> is
constant in the air, so the domain starts at the surface. E<sub>y</sub> is discontinuous at a surface contact,
so TM ρ<sub>a</sub> shows sharp jumps; sensitive to resistors and lateral boundaries.</li>
</ul>
<h3>Numerical method used here</h3>
<ul>
<li>Node-based finite volumes on a tensor mesh, cell-constant resistivity, 5-point stencil, sparse direct
solver (SciPy / SuperLU).</li>
<li>A new mesh is built for every frequency: cells near the surface and inside conductors are ≤ δ/10;
geometric padding extends ≥ 5 skin depths laterally, downwards and (TE) into the air.</li>
<li>Dirichlet boundaries: E<sub>x</sub> = 1 at the top of the air (TE), H<sub>x</sub> = 1 at the surface (TM);
side boundaries from 1D solutions of the edge columns; the model is extended laterally and downward.</li>
<li>Surface fields by flux recovery on the half control volume below each surface node.</li>
<li>Validation: laterally uniform models reproduce the 1D recursion (errors ≈ 0.1 %, 0.15°), TE = TM for 1D
models, symmetric bodies give symmetric profiles, mesh-convergence check available.</li>
</ul>
"""

TOPICS["Noise, errors and error floor"] = """
<h2>Noise and data errors</h2>
<p>Real data contain noise. The Noise &amp; Data tab adds it to the synthetic impedance and records the
1-σ error that is written to the EDI file (VAR = σ²) and used by the inversion.</p>
<ul><li><b>Gaussian on Z</b>: Z<sub>obs</sub> = Z(1 + p·n). σ(ρa)/ρa ≈ √2·p, σ(φ) ≈ p/√2 rad.</li>
<li><b>Gaussian on ρa and φ</b>: independent noise on ρa (%) and phase (°).</li>
<li><b>Uniform</b>: bounded noise ±p.</li>
<li><b>Outliers</b>: a few frequencies receive k× larger errors that are <i>not</i> in the reported σ.</li></ul>
<p><b>Error floor</b>: the smallest error accepted (e.g. 5 % of |Z|). A larger floor gives a smoother model with
lower RMS; a too small floor forces the inversion to fit noise.</p>
"""

TOPICS["1D inversion (Occam & Marquardt)"] = """
<h2>1D inversion</h2>
<p>Data d = [log10 ρa, φ]; misfit</p>
[[EQ: $\\mathrm{RMS}=\\sqrt{\\dfrac{1}{N}\\sum_i\\left(\\dfrac{d_i^{obs}-d_i^{pred}}{\\sigma_i}\\right)^2}$]]
<p>RMS ≈ 1 means the model explains the data to within their errors.</p>
<h3>Occam (smooth)</h3>
[[EQ: $\\min\\ \\|W(d-F(m))\\|^2+\\lambda\\|Rm\\|^2$]]
<p>Many thin layers with fixed depths; m = log10 ρ. λ is chosen so that the <b>smoothest</b> model that reaches
the target RMS is kept. The result shows only the structure the data require.</p>
<h3>Marquardt (layered)</h3>
[[EQ: $(G^TG+\\mu\\,\\mathrm{diag}(G^TG))\\,\\Delta m=G^TW\\,r$]]
<p>Few layers; unknowns log ρ and log h. Several starting models are tried and the best is kept. The
uncertainty factor (×/÷) and parameter correlation reveal <b>equivalence</b>: a thin conductor is resolved
through S = h/ρ, a thin resistor through T = h·ρ.</p>
"""

TOPICS["2D inversion (Occam)"] = """
<h2>2D Occam inversion</h2>
<p>The model is a grid of blocks (columns between stations, log-spaced layers); m = log10 ρ of every block.
The Jacobian is computed with the adjoint method of the finite-volume solver. Each iteration solves</p>
[[EQ: $(G^TG+\\lambda R^TR)\\,m_{k+1}=G^TW\\,(d-F(m_k)+Jm_k)$]]
<p>R contains horizontal (weight α) and vertical first differences. λ is chosen from the linearised misfit;
a step is accepted only if the true RMS decreases. Use few frequencies and stations — this is a teaching
version.</p>
"""

TOPICS["Limitations"] = """
<h2>Limitations (read before using results for research)</h2>
<ul>
<li>Plane-wave sources only. No controlled-source (CSAMT/CSRMT) or near-field transmitter modelling.</li>
<li>Quasi-static: displacement currents neglected (fine for MT/AMT/VLF at typical earth resistivities).</li>
<li>Isotropic resistivity; no topography; no induced polarisation; μ = μ₀.</li>
<li>2D solver: no tipper output in this version; model geometry is sampled at cell centres
(polygon edges are staircased at the mesh resolution).</li>
<li>Niblett–Bostick depths are approximations.</li>
</ul>
"""
