"""2D resistivity model: layered background + bodies (rectangles / polygons).

Geometry rules (important for the numerical solver):
* Profile coordinate y runs from 0 to `width` (m); depth z from 0 to `depth` (m), positive down.
* Outside 0..width the model is extended laterally with the edge columns (1D at the edges).
* Below `depth` the bottom row of the model is extended to infinite depth.
* Bodies are painted in list order: later bodies overwrite earlier ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from matplotlib.path import Path


@dataclass
class Body:
    kind: str = "rect"              # "rect" or "polygon"
    rho: float = 10.0
    name: str = "Body"
    x0: float = 0.0
    x1: float = 100.0
    z0: float = 0.0
    z1: float = 100.0
    points: list = field(default_factory=list)   # [(y, z), ...] for polygons

    def mask(self, y, z):
        if self.kind == "polygon":
            if len(self.points) < 3:
                return np.zeros(np.shape(y), bool)
            path = Path(np.asarray(self.points, float))
            pts = np.column_stack([np.ravel(y), np.ravel(z)])
            return path.contains_points(pts).reshape(np.shape(y))
        return (y >= self.x0) & (y <= self.x1) & (z >= self.z0) & (z <= self.z1)

    def to_dict(self):
        d = {"kind": self.kind, "rho": self.rho, "name": self.name}
        if self.kind == "polygon":
            d["points"] = [list(map(float, p)) for p in self.points]
        else:
            d.update(x0=self.x0, x1=self.x1, z0=self.z0, z1=self.z1)
        return d

    @classmethod
    def from_dict(cls, d):
        b = cls(kind=d.get("kind", "rect"), rho=float(d["rho"]), name=d.get("name", "Body"))
        if b.kind == "polygon":
            b.points = [tuple(map(float, p)) for p in d["points"]]
        else:
            b.x0, b.x1, b.z0, b.z1 = (float(d[k]) for k in ("x0", "x1", "z0", "z1"))
        return b


@dataclass
class Model2D:
    title: str = "2D model"
    width: float = 4000.0
    depth: float = 2000.0
    dx: float = 50.0
    dz: float = 25.0
    bg_rho: list = field(default_factory=lambda: [100.0])
    bg_thick: list = field(default_factory=list)
    bodies: list = field(default_factory=list)
    stations: list = field(default_factory=list)

    def rho_at(self, y, z):
        y = np.clip(np.asarray(y, float), 0.0, self.width)
        z = np.clip(np.asarray(z, float), 0.0, self.depth)
        tops = np.concatenate([[0.0], np.cumsum(self.bg_thick)])
        idx = np.searchsorted(tops, z, side="right") - 1
        rho = np.asarray(self.bg_rho, float)[np.clip(idx, 0, len(self.bg_rho) - 1)]
        rho = np.array(rho, dtype=float)
        for b in self.bodies:
            rho = np.where(b.mask(y, z), b.rho, rho)
        return rho

    def all_rho(self):
        return np.array(list(self.bg_rho) + [b.rho for b in self.bodies], float)

    def validate(self) -> list[str]:
        e = []
        if self.width <= 0 or self.depth <= 0:
            e.append("Model width and depth must be > 0.")
        if self.dx <= 0 or self.dz <= 0:
            e.append("Grid spacing must be > 0.")
        if self.width / max(self.dx, 1e-9) > 400:
            e.append("Too many horizontal cells (width/dx > 400). Increase dx.")
        if self.depth / max(self.dz, 1e-9) > 400:
            e.append("Too many vertical cells (depth/dz > 400). Increase dz.")
        if np.any(self.all_rho() <= 0) or np.any(~np.isfinite(self.all_rho())):
            e.append("All resistivities must be > 0.")
        if len(self.bg_thick) != len(self.bg_rho) - 1 or any(t <= 0 for t in self.bg_thick):
            e.append("Background: need n-1 positive thicknesses.")
        st = np.asarray(self.stations, float)
        if st.size == 0:
            e.append("No stations defined.")
        elif np.any(st < 0) or np.any(st > self.width):
            e.append("Stations must lie inside 0..width.")
        return e

    def to_dict(self):
        return {"title": self.title, "width": self.width, "depth": self.depth, "dx": self.dx, "dz": self.dz,
                "bg_rho": list(map(float, self.bg_rho)), "bg_thick": list(map(float, self.bg_thick)),
                "bodies": [b.to_dict() for b in self.bodies],
                "stations": list(map(float, self.stations))}

    @classmethod
    def from_dict(cls, d):
        return cls(title=d.get("title", "2D model"), width=float(d["width"]), depth=float(d["depth"]),
                   dx=float(d["dx"]), dz=float(d["dz"]), bg_rho=list(map(float, d["bg_rho"])),
                   bg_thick=list(map(float, d["bg_thick"])),
                   bodies=[Body.from_dict(b) for b in d.get("bodies", [])],
                   stations=list(map(float, d.get("stations", []))))

    def copy(self):
        return Model2D.from_dict(self.to_dict())
