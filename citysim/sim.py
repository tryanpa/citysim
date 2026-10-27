"""Simulation rules: pollution, land value, road traffic and building growth.

One cell is one chunky tile: a road is 1 tile wide and zones are blocks of
tiles you drag out (think 3x3 or 4x4, like classic SimCity).

There is deliberately no money, score, demand or disasters. Zoned land simply
fills in over time, and the sim exposes how the layout affects traffic,
pollution and land value as overlay maps.
"""
from __future__ import annotations

from collections import deque

import numpy as np

from .world import MAX_LEVEL, World, Zone

HOME_PER_LEVEL = 5.0     # residents per tile per level
JOB_COMMERCIAL = 3.0     # jobs per tile per level
JOB_INDUSTRIAL = 4.0
ROAD_REACH = 3           # a tile can use a road up to this many tiles away
ROAD_CAPACITY = 60.0     # commuters per road tile before it counts as congested
LOT = 1                  # buildings grow in LOT x LOT lots


def box_blur(a: np.ndarray, r: int, passes: int = 2) -> np.ndarray:
    """Smooth with a (2r+1) box filter, repeated; edges clamp."""
    h, w = a.shape
    k = 2 * r + 1
    for _ in range(passes):
        p = np.pad(a, r, mode="edge")
        c = np.vstack([np.zeros((1, p.shape[1])), np.cumsum(p, axis=0)])
        a = (c[k:] - c[:-k]) / k
        c = np.hstack([np.zeros((h, 1)), np.cumsum(a, axis=1)])
        a = (c[:, k:] - c[:, :-k]) / k
    return a


class Simulation:
    def __init__(self, world: World):
        self.world = world
        shape = (world.height, world.width)
        self.pollution = np.zeros(shape)
        self.land_value = np.zeros(shape)
        self.traffic = np.zeros(shape)
        self.desirability = np.zeros(shape)
        self.job_access = np.zeros(shape, dtype=bool)
        self.stats: dict[str, float] = {}
        self._reach_key: tuple | None = None
        self.entry = np.full(shape, -1, dtype=np.int64)  # flat index of nearest road cell

    # --- road reach (cached; only changes when roads/water are edited) ------------
    def _update_reach(self) -> None:
        w = self.world
        key = (w.road.tobytes(), w.water.tobytes())
        if key == self._reach_key:
            return
        self._reach_key = key
        h, wd = w.height, w.width
        dist = np.full(h * wd, -1, dtype=np.int16)
        src = np.full(h * wd, -1, dtype=np.int64)
        road, water = w.road.ravel(), w.water.ravel()
        start = np.flatnonzero(road)
        dist[start], src[start] = 0, start
        q = deque(start.tolist())
        while q:
            i = q.popleft()
            if dist[i] >= ROAD_REACH:
                continue
            y, x = divmod(i, wd)
            for j, ok in ((i - wd, y > 0), (i + wd, y < h - 1), (i - 1, x > 0), (i + 1, x < wd - 1)):
                if ok and dist[j] < 0 and not water[j]:
                    dist[j], src[j] = dist[i] + 1, src[i]
                    q.append(j)
        entry = np.where(dist >= 0, src, -1).reshape(h, wd)
        entry[w.road] = -1  # road cells themselves don't hold buildings
        self.entry = entry

    # --- layers --------------------------------------------------------------
    def _update_traffic(self) -> None:
        """Send every home's commuters to the nearest job along the road graph."""
        w = self.world
        h, wd = w.height, w.width
        lvl = w.level.astype(float)
        jobs = np.where(w.zone == Zone.COMMERCIAL, lvl * JOB_COMMERCIAL, 0) \
            + np.where(w.zone == Zone.INDUSTRIAL, lvl * JOB_INDUSTRIAL, 0)
        homes = np.where(w.zone == Zone.RESIDENTIAL, lvl * HOME_PER_LEVEL, 0)
        has_entry = self.entry >= 0
        sources = np.unique(self.entry[(jobs > 0) & has_entry])

        # multi-source BFS over roads; parent points toward a job
        road = w.road.ravel()
        parent = np.full(h * wd, -1, dtype=np.int64)
        seen = np.zeros(h * wd, dtype=bool)
        seen[sources] = True
        order = sources.tolist()
        q = deque(order)
        while q:
            i = q.popleft()
            y, x = divmod(i, wd)
            for j, ok in ((i - wd, y > 0), (i + wd, y < h - 1), (i - 1, x > 0), (i + 1, x < wd - 1)):
                if ok and road[j] and not seen[j]:
                    seen[j], parent[j] = True, i
                    q.append(j)
                    order.append(j)

        hm = (homes > 0) & has_entry
        he, hv = self.entry[hm], homes[hm]
        ok = seen[he]
        load = np.bincount(he[ok], weights=hv[ok], minlength=h * wd)
        for i in reversed(order):  # accumulate flow down the BFS tree toward the jobs
            if parent[i] >= 0:
                load[parent[i]] += load[i]
        self.traffic = load.reshape(h, wd)
        self.job_access = np.zeros(h * wd, dtype=bool).reshape(h, wd)
        self.job_access[hm] = ok
        self.stats["commuters"] = float(hv[ok].sum())
        self.stats["unserved"] = float(hv[~ok].sum() + homes[(homes > 0) & ~has_entry].sum())

    def _update_environment(self) -> None:
        w = self.world
        lvl = w.level.astype(float)
        industry = np.where(w.zone == Zone.INDUSTRIAL, lvl, 0)
        commerce = np.where(w.zone == Zone.COMMERCIAL, lvl, 0)
        homes = np.where(w.zone == Zone.RESIDENTIAL, lvl, 0)
        parks = (w.zone == Zone.PARK).astype(float)

        road_smog = box_blur(self.traffic / ROAD_CAPACITY, 1) * 0.8
        self.pollution = np.clip(
            box_blur(industry, 2) * 0.6 + road_smog - box_blur(parks, 2) * 0.6, 0, 1)
        self.land_value = np.clip(
            0.35 + box_blur(parks, 2) * 0.7 + box_blur(commerce, 2) * 0.2
            + box_blur(homes, 2) * 0.05 + box_blur(w.water.astype(float), 2) * 0.3
            - self.pollution * 0.9, 0, 1)

    # --- growth --------------------------------------------------------------
    def _lot_roll(self) -> np.ndarray:
        """Random numbers shared across each LOT x LOT lot so lots grow together."""
        w = self.world
        r = w.rng.random((w.height // LOT + 1, w.width // LOT + 1))
        return np.kron(r, np.ones((LOT, LOT)))[: w.height, : w.width]

    def _update_growth(self) -> None:
        """Zoned tiles with road access slowly fill in; there is no demand to satisfy."""
        w = self.world
        has_entry = self.entry >= 0
        lvl = w.level
        congestion = np.clip(box_blur(self.traffic / ROAD_CAPACITY, 1) * 3, 0, 1)
        d = np.full(self.land_value.shape, np.nan)
        for zone in (Zone.RESIDENTIAL, Zone.COMMERCIAL, Zone.INDUSTRIAL):
            m = w.zone == zone
            if zone == Zone.INDUSTRIAL:  # industry doesn't mind pollution or traffic
                score = 0.7 - self.land_value * 0.2
            elif zone == Zone.RESIDENTIAL:
                score = 0.3 + self.land_value * 0.7 - self.pollution * 0.5 - congestion * 0.3
            else:
                score = 0.3 + self.land_value * 0.5 - congestion * 0.2
            d[m] = score[m]
        self.desirability = d

        roll = self._lot_roll()
        grow = has_entry & ~np.isnan(d) & (d > 0.3) & (roll < 0.1) & (lvl < MAX_LEVEL)
        built = (w.zone > 0) & (w.zone != Zone.PARK) & (lvl > 0)
        shrink = built & ~has_entry & (roll < 0.1)  # only if its road was removed
        w.level[grow] += 1
        w.level[shrink] -= 1

    # --- main entry ----------------------------------------------------------
    def step(self) -> None:
        self._update_reach()
        self._update_traffic()
        self._update_environment()
        self._update_growth()
        w = self.world
        w.tick += 1
        lvl = w.level.astype(float)
        self.stats.update(
            tick=w.tick, population=w.population(),
            jobs=int(np.where(w.zone == Zone.COMMERCIAL, lvl * JOB_COMMERCIAL, 0).sum()
                     + np.where(w.zone == Zone.INDUSTRIAL, lvl * JOB_INDUSTRIAL, 0).sum()),
            avg_land_value=float(self.land_value.mean()),
            avg_pollution=float(self.pollution.mean()),
            peak_traffic=float(self.traffic.max()),
        )
