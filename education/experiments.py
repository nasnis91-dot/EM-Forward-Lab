"""Guided classroom experiments. Each one loads a model into the 1D tab and tells the student
what to change and what to look for."""

EXPERIMENTS = [
    {
        "title": "1. Half-space: the reference case",
        "method": "MT", "rho": [100.0], "thick": [], "names": ["Half-space"],
        "task": "Change ρ with the slider (10, 100, 1000 Ω·m).",
        "observe": "ρa equals ρ at every frequency and the phase stays at 45°. Only the skin depth changes.",
    },
    {
        "title": "2. Interactive interpretation: conductive clay",
        "method": "AMT", "rho": [100.0, 5.0, 1000.0], "thick": [50.0, 200.0],
        "names": ["Top soil", "Conductive clay", "Basement"],
        "task": "Press 'Pin as reference', then change layer 2 from 5 to 50 Ω·m.",
        "observe": "The ρa minimum disappears and the phase above 45° drops. The interpretation panel reports "
                   "which frequencies changed most and the Bostick depth they correspond to.",
    },
    {
        "title": "3. Equivalence of a thin conductor (S = h/ρ)",
        "method": "MT", "rho": [100.0, 10.0, 1000.0], "thick": [500.0, 100.0],
        "names": ["Cover", "Thin conductor", "Basement"],
        "task": "Pin as reference. Then set layer 2 to ρ = 5 Ω·m and h = 50 m (same S = 10 S).",
        "observe": "The two curves are almost identical: MT resolves the conductance of a thin conductor, "
                   "not ρ and h separately.",
    },
    {
        "title": "4. A resistive layer is hard to see",
        "method": "MT", "rho": [20.0, 1000.0, 50.0], "thick": [200.0, 300.0],
        "names": ["Conductive cover", "Resistor", "Half-space"],
        "task": "Pin as reference, then double the resistor to 2000 Ω·m. Then instead double its thickness.",
        "observe": "Changing ρ alone barely changes the curve; changing h·ρ (transverse resistance) does.",
    },
    {
        "title": "5. Frequency band and depth of investigation",
        "method": "AMT", "rho": [50.0, 500.0, 5.0, 1000.0], "thick": [100.0, 400.0, 600.0],
        "names": ["Sediments", "Volcanics", "Clay", "Basement"],
        "task": "Switch the method between AMT and MT (frequency presets).",
        "observe": "AMT sees only the upper layers; the MT band reaches the basement.",
    },
    {
        "title": "6. VLF-R: one frequency, shallow sensing",
        "method": "VLF-R", "rho": [200.0, 20.0, 500.0], "thick": [15.0, 40.0],
        "names": ["Dry soil", "Wet clay", "Bedrock"],
        "task": "Change the thickness of the dry soil from 5 to 40 m.",
        "observe": "At ~20 kHz ρa/φ react strongly while the soil is thinner than ~1 skin depth "
                   "and stop changing once it is much thicker.",
    },
    {
        "title": "7. Noise and inversion (full workflow)",
        "method": "MT", "rho": [100.0, 10.0, 500.0], "thick": [200.0, 300.0],
        "names": ["Overburden", "Conductive layer", "Basement"],
        "task": "Noise & Data: Gaussian 5 %, export EDI. 1D Inversion: load the EDI, run Occam, then Marquardt (3 layers).",
        "observe": "Occam recovers a smooth conductor near 200–500 m; Marquardt recovers ρ and h with uncertainties. "
                   "Compare both with the true model.",
    },
]
