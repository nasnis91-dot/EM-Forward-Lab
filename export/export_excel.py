"""Excel export: Data sheet + Model sheet + Metadata sheet."""
import json

import pandas as pd


def write_excel(path, data: pd.DataFrame, model: dict, meta: dict):
    meta_rows = [("credit", meta.get("credit", ""))]
    for k, v in meta.items():
        if k != "credit":
            meta_rows.append((k, v if isinstance(v, (str, int, float)) else json.dumps(v, default=str)))
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        data.to_excel(xw, sheet_name="Data", index=False)
        if "rho_ohmm" in model:          # 1D
            n = len(model["rho_ohmm"])
            th = list(model["thickness_m"]) + ["half-space"]
            names = (list(model.get("names", [])) + [""] * n)[:n]
            pd.DataFrame({"Layer": range(1, n + 1), "Name": names, "Resistivity_OhmM": model["rho_ohmm"],
                          "Thickness_m": th}).to_excel(xw, sheet_name="Model", index=False)
        else:                            # 2D
            pd.DataFrame([{k: (json.dumps(v) if isinstance(v, (list, dict)) else v)
                           for k, v in model.items() if k != "bodies"}]).T.to_excel(xw, sheet_name="Model")
            pd.DataFrame([{**b, "points": json.dumps(b.get("points", ""))} for b in model.get("bodies", [])]) \
                .to_excel(xw, sheet_name="Bodies", index=False)
        pd.DataFrame(meta_rows, columns=["Key", "Value"]).to_excel(xw, sheet_name="Metadata", index=False)
