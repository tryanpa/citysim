"""Simulation rules: pollution, land value, road traffic and building growth.

There is deliberately no money, score or goals: the sim only reacts to how
the city is laid out, and exposes the results as overlay maps.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .world import MAX_LEVEL, World, Zone

HOME_PER_LEVEL, JOB_COMMERCIAL, JOB_INDUSTRIAL = 5, 3, 4


def blur(a: np.ndarray, passes: int = 1) -> np.ndarray:
    """Cheap diffusion: average of a cell and its 4 neighbours (edges clamp)."""
    for _ in range(passes):
        p = np.pad(a, 1, mode="edge")
        a = (p[1:-1, 1:-1] * 2 + p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 6
    return a


class Simulation:
    def __init__(self, world: World):
        self.world = world
        shape = (world.height, world.width)
        self.pollution = np.zeros(shape)
        self.land_value = np.zeros(shape)
        self.traffic = np.zeros(shape)
        self.desirability = np.zeros(shape)
        self.stats: dict[str, float] = {}

    # --- helpers -------------------------------------------------------------
    def _road_access(self) -> np.ndarray:
        r = self.world.road
        a = np.zeros_like(r)
        a[1:] |= r[:-1]; a[:-1] |= r[1:]; a[:, 1:] |= r[:, :-1]; a[:, :-1] |= r[:, 1:]
        return a

    def _components(self) -> np.ndarray:
        """Label connected road networks (0 = no road)."""
        w = self.world
        label = np.zeros((w.height, w.width), dtype=np.int32)
        n = 0
        for y, x in zip(*np.nonzero(w.road)):
            if label[y, x]:
                continue
            n += 1
            label[y, x] = n
            q = deque([(x, y)])
            while q:
                cx, cy = q.popleft()
                for nx, ny in w.neighbors4(cx, cy):
                    if w.road[ny, nx] and not label[ny, nx]:
                        label[ny, nx] = n
                        q.append((nx, ny))
        return label

    def _adjacent_roads(self, x: int, y: int):
        return [(nx, ny) for nx, ny in self.world.neighbors4(x, y) if self.world.road[ny, nx]]

    # --- layers --------------------------------------------------------------
    def _update_environment(self) -> None:
        w = self.world
        lvl = w.level.astype(float)
        industry = np.where(w.zone == Zone.INDUSTRIAL, lvl, 0)
        commerce = np.where(w.zone == Zone.COMMERCIAL, lvl, 0)
        homes = np.where(w.zone == Zone.RESIDENTIAL, lvl, 0)
        parks = (w.zone == Zone.PARK).astype(float)

        road_smog = blur(self.traffic / (self.traffic.max() + 1e-9), 2) * 0.4
        self.pollution = np.clip(blur(industry, 4) * 3.0 + road_smog - blur(parks, 3) * 1.5, 0, 1)

        water_bonus = blur(w.water.astype(float), 3) * 0.4
        self.land_value = np.clip(
            0.35 + blur(parks, 3) * 1.6 + blur(commerce, 3) * 0.5 + blur(homes, 3) * 0.15
            + water_bonus - self.pollution * 0.9, 0, 1)

    def _update_traffic(self, comp: np.ndarray) -> None:
        """Send every home's commuters to its nearest job along the road graph."""
        w = self.world
        self.traffic[:] = 0
        job_tiles = {}
        for zone, per in ((Zone.COMMERCIAL, JOB_COMMERCIAL), (Zone.INDUSTRIAL, JOB_INDUSTRIAL)):
            for y, x in zip(*np.nonzero((w.zone == zone) & (w.level > 0))):
                for r in self._adjacent_roads(x, y):
                    job_tiles[r] = job_tiles.get(r, 0) + per * int(w.level[y, x])
        # multi-source BFS from job-adjacent roads; parent points toward a job
        parent = {r: None for r in job_tiles}
        q = deque(parent)
        while q:
            cx, cy = q.popleft()
            for nx, ny in w.neighbors4(cx, cy):
                if w.road[ny, nx] and (nx, ny) not in parent:
                    parent[(nx, ny)] = (cx, cy)
                    q.append((nx, ny))
        commuters = unserved = 0
        for y, x in zip(*np.nonzero((w.zone == Zone.RESIDENTIAL) & (w.level > 0))):
            n = HOME_PER_LEVEL * int(w.level[y, x])
            entry = next((r for r in self._adjacent_roads(x, y) if r in parent), None)
            if entry is None:
                unserved += n
                continue
            commuters += n
            cur = entry
            while cur is not None:
                self.traffic[cur[1], cur[0]] += n
                cur = parent[cur]
        self.stats["commuters"] = commuters
        self.stats["unserved"] = unserved

    # --- growth --------------------------------------------------------------
    def _update_growth(self, comp: np.ndarray) -> None:
        w = self.world
        access = self._road_access()
        homes = np.where(w.zone == Zone.RESIDENTIAL, w.level, 0).sum()
        jobs_c = np.where(w.zone == Zone.COMMERCIAL, w.level, 0).sum() * JOB_COMMERCIAL
        jobs_i = np.where(w.zone == Zone.INDUSTRIAL, w.level, 0).sum() * JOB_INDUSTRIAL
        pop = homes * HOME_PER_LEVEL
        # demand: each sector wants the others to exist; start-up bias keeps the first lots alive
        demand = {
            Zone.RESIDENTIAL: np.clip(((jobs_c + jobs_i + 8) - pop) / 20, -1, 1),
            Zone.COMMERCIAL: np.clip((pop * 0.5 + 4 - jobs_c) / 20, -1, 1),
            Zone.INDUSTRIAL: np.clip((pop * 0.4 + 4 - jobs_i) / 20, -1, 1),
        }
        congestion = np.clip(blur(self.traffic, 2) / 60.0, 0, 1)
        d = np.zeros_like(self.land_value)
        d[:] = np.nan
        for zone, dem in demand.items():
            m = w.zone == zone
            if zone == Zone.INDUSTRIAL:  # industry doesn't mind pollution, dislikes expensive land
                score = 0.4 + dem * 0.6 - self.land_value * 0.3 - congestion * 0.3
            elif zone == Zone.RESIDENTIAL:
                score = self.land_value * 0.7 + dem * 0.5 - self.pollution * 0.4 - congestion * 0.3
            else:
                score = self.land_value * 0.4 + dem * 0.5 + congestion * 0.0 - congestion * 0.2
            d[m] = score[m]
        self.desirability = d
        buildable = access & ~np.isnan(d) & (w.zone != Zone.PARK)
        roll = w.rng.random(d.shape)
        grow = buildable & (d > 0.3) & (roll < 0.3) & (w.level < MAX_LEVEL)
        shrink = (w.zone > 0) & (w.zone != Zone.PARK) & (w.level > 0) & (
            ~access | (np.nan_to_num(d, nan=1) < 0.05)) & (roll < 0.08)
        w.level[grow] += 1
        w.level[shrink] -= 1

    # --- main entry ----------------------------------------------------------
    def step(self) -> None:
        comp = self._components()
        self._update_traffic(comp)
        self._update_environment()
        self._update_growth(comp)
        self.world.tick += 1
        w = self.world
        self.stats.update(
            tick=w.tick, population=w.population(),
            jobs=int(np.where(w.zone == Zone.COMMERCIAL, w.level, 0).sum() * JOB_COMMERCIAL
                     + np.where(w.zone == Zone.INDUSTRIAL, w.level, 0).sum() * JOB_INDUSTRIAL),
            avg_land_value=float(self.land_value.mean()),
            avg_pollution=float(self.pollution.mean()),
            peak_traffic=float(self.traffic.max()),
        )
