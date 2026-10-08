"""JSON export of model + data + metadata (fully reproducible experiment)."""
import json

import numpy as np


def _default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, complex):
        return [o.real, o.imag]
    return str(o)


def write_json(path, payload: dict):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, default=_default)


def read_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
