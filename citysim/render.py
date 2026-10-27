"""Rasterise a Simulation to an RGB array (shared by the pygame UI and PNG export)."""
from __future__ import annotations

import numpy as np

from . import terrain
from .sim import Simulation
from .world import Zone

OVERLAYS = ["none", "land value", "pollution", "traffic", "desirability"]

ROAD = (70, 70, 75)
BIOME_COLORS = np.array(terrain.PALETTE, dtype=float)
ZONE_BASE = {
    Zone.RESIDENTIAL: (110, 225, 150), Zone.COMMERCIAL: (70, 110, 210),
    Zone.INDUSTRIAL: (210, 180, 60), Zone.PARK: (40, 130, 60),
}


def _heat(v: np.ndarray) -> np.ndarray:
    """0..1 -> blue→green→yellow→red."""
    v = np.clip(np.nan_to_num(v), 0, 1)[..., None]
    stops = np.array([(40, 60, 160), (50, 170, 90), (230, 210, 60), (210, 50, 40)], float)
    pos = v * (len(stops) - 1)
    i = np.minimum(pos.astype(int)[..., 0], len(stops) - 2)
    f = pos - i[..., None]
    return stops[i] * (1 - f) + stops[i + 1] * f


def tile_colors(sim: Simulation, overlay: str = "none") -> np.ndarray:
    w = sim.world
    img = BIOME_COLORS[w.biome]  # flat terrain colours straight from the palette
    ground = img.copy()
    for z, c in ZONE_BASE.items():
        m = w.zone == z
        if z == Zone.PARK:
            img[m] = c
            continue
        # empty lots are drawn pale; built-up levels get progressively darker
        img[m] = np.clip(np.array(c) * (1.2 - 0.15 * w.level[m])[:, None], 0, 255)
        img[m & (w.level == 0)] = np.array(c) * 0.5 + ground[m & (w.level == 0)] * 0.5
    img[w.road] = ROAD
    if overlay != "none":
        field = {
            "land value": sim.land_value, "pollution": sim.pollution,
            "traffic": sim.traffic / max(sim.traffic.max(), 1.0),
            "desirability": sim.desirability,
        }[overlay]
        heat = _heat(field)
        mask = w.road if overlay == "traffic" else ~w.water | w.road
        img[mask] = img[mask] * 0.35 + heat[mask] * 0.65
    return img.astype(np.uint8)


def render(sim: Simulation, overlay: str = "none", tile: int = 10, grid: bool = True) -> np.ndarray:
    px = np.kron(tile_colors(sim, overlay), np.ones((tile, tile, 1), dtype=np.uint8))
    if grid and tile >= 8:
        px[::tile] = (px[::tile] * 0.85).astype(np.uint8)
        px[:, ::tile] = (px[:, ::tile] * 0.85).astype(np.uint8)
    return px
