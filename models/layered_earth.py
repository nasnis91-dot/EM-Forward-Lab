"""1D layered-earth model container."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.mt_1d import validate_layers


@dataclass
class LayeredModel:
    rho: list = field(default_factory=lambda: [100.0])
    thick: list = field(default_factory=list)          # n_layers - 1 values
    names: list = field(default_factory=list)
    title: str = "Custom model"

    @property
    def n(self) -> int:
        return len(self.rho)

    def depths(self) -> np.ndarray:
        """Depth to the top of each layer (0 for the first)."""
        return np.concatenate([[0.0], np.cumsum(self.thick)])

    def validate(self) -> list[str]:
        return validate_layers(self.rho, self.thick)

    def layer_name(self, i: int) -> str:
        if i < len(self.names) and self.names[i]:
            return self.names[i]
        from i18n import tr
        return tr("Layer {i}", i=i + 1) if i < self.n - 1 else tr("Layer {i} (half-space)", i=i + 1)

    def add_layer(self, rho=100.0, thick=100.0):
        """Insert a new layer just above the half-space."""
        self.rho.insert(self.n - 1, float(rho))
        self.thick.append(float(thick))
        if self.names:
            self.names.insert(self.n - 2, "")

    def remove_layer(self, i: int):
        if self.n <= 1:
            return
        if i >= self.n - 1:            # removing the half-space: previous layer becomes half-space
            self.rho.pop(i)
            self.thick.pop(-1)
        else:
            self.rho.pop(i)
            self.thick.pop(i)
        if i < len(self.names):
            self.names.pop(i)

    def to_dict(self) -> dict:
        return {"title": self.title, "rho_ohmm": list(map(float, self.rho)),
                "thickness_m": list(map(float, self.thick)), "names": list(self.names)}

    @classmethod
    def from_dict(cls, d: dict) -> "LayeredModel":
        return cls(rho=[float(v) for v in d["rho_ohmm"]], thick=[float(v) for v in d["thickness_m"]],
                   names=list(d.get("names", [])), title=d.get("title", "Loaded model"))

    def copy(self) -> "LayeredModel":
        return LayeredModel.from_dict(self.to_dict())
