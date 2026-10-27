"""City state: a grid of terrain, roads, zones and building levels."""
from __future__ import annotations

import json
from enum import IntEnum

import numpy as np


class Zone(IntEnum):
    NONE = 0
    RESIDENTIAL = 1
    COMMERCIAL = 2
    INDUSTRIAL = 3
    PARK = 4


MAX_LEVEL = 3


class World:
    def __init__(self, width: int = 80, height: int = 60, seed: int | None = None):
        self.width, self.height = width, height
        self.water = np.zeros((height, width), dtype=bool)
        self.road = np.zeros((height, width), dtype=bool)
        self.zone = np.zeros((height, width), dtype=np.int8)
        self.level = np.zeros((height, width), dtype=np.int8)  # 0 = empty lot
        self.tick = 0
        self.rng = np.random.default_rng(seed)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    # --- editing -----------------------------------------------------------
    def build_road(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y) or self.water[y, x]:
            return False
        self.zone[y, x] = Zone.NONE
        self.level[y, x] = 0
        self.road[y, x] = True
        return True

    def set_zone(self, x: int, y: int, zone: Zone) -> bool:
        if not self.in_bounds(x, y) or self.water[y, x] or self.road[y, x]:
            return False
        if self.zone[y, x] != zone:
            self.zone[y, x] = zone
            # parks are fully "built"; other zones start as empty lots
            self.level[y, x] = 1 if zone == Zone.PARK else 0
        return True

    def bulldoze(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        self.road[y, x] = False
        self.zone[y, x] = Zone.NONE
        self.level[y, x] = 0
        return True

    def line(self, x0: int, y0: int, x1: int, y1: int):
        """Grid cells on a straight line (Bresenham), for drag-painting."""
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            yield x0, y0
            if (x0, y0) == (x1, y1):
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    # --- terrain -----------------------------------------------------------
    def generate_terrain(self) -> None:
        """A meandering river plus a lake, so there is something to design around."""
        h, w = self.height, self.width
        self.water[:] = False
        x = w * self.rng.uniform(0.3, 0.7)
        for y in range(h):
            x += self.rng.normal(0, 0.8)
            x = float(np.clip(x, 4, w - 5))
            self.water[y, int(x) - 1 : int(x) + 1] = True
        cx, cy, r = self.rng.integers(10, w - 10), self.rng.integers(8, h - 8), self.rng.integers(3, 6)
        yy, xx = np.ogrid[:h, :w]
        self.water |= (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r

    # --- queries -----------------------------------------------------------
    def neighbors4(self, x: int, y: int):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny

    def population(self) -> int:
        return int(self.level[self.zone == Zone.RESIDENTIAL].sum()) * 5

    # --- persistence -------------------------------------------------------
    def save(self, path: str) -> None:
        data = {
            "width": self.width, "height": self.height, "tick": self.tick,
            "water": self.water.astype(int).tolist(),
            "road": self.road.astype(int).tolist(),
            "zone": self.zone.tolist(), "level": self.level.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: str) -> "World":
        with open(path) as f:
            d = json.load(f)
        w = cls(d["width"], d["height"])
        w.tick = d["tick"]
        w.water = np.array(d["water"], dtype=bool)
        w.road = np.array(d["road"], dtype=bool)
        w.zone = np.array(d["zone"], dtype=np.int8)
        w.level = np.array(d["level"], dtype=np.int8)
        return w
