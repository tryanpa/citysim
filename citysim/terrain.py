"""Pure-Python terrain generation: seedable fractal noise and a strict biome matrix.

No third-party imports at all (no numpy, no noise/scipy), so it runs anywhere
and instantly at city-builder map sizes. Pygame is only needed by whoever
draws the result.

Pipeline
    FractalNoise (elevation) ─┐
                              ├─> biome_at(e, m) ─> grid of biome ids ─> PALETTE
    FractalNoise (moisture)  ─┘
"""
from __future__ import annotations

import math
import random

# --- Biome ids (used as indices into PALETTE) ---------------------------------
DEEP_WATER, SHALLOW_WATER, SAND, PLAINS, FOREST, HILLS, MOUNTAINS = range(7)

# --- Explicit palette: one flat colour per biome, no gradients ----------------
COLOR_DEEP_WATER = (28, 72, 140)
COLOR_SHALLOW_WATER = (56, 122, 192)
COLOR_SAND = (222, 205, 142)      # coastline
COLOR_PLAINS = (124, 170, 88)
COLOR_FOREST = (52, 112, 62)
COLOR_HILLS = (152, 140, 98)
COLOR_MOUNTAINS = (128, 128, 136)
PALETTE = (COLOR_DEEP_WATER, COLOR_SHALLOW_WATER, COLOR_SAND, COLOR_PLAINS,
           COLOR_FOREST, COLOR_HILLS, COLOR_MOUNTAINS)
BIOME_NAMES = ("deep water", "shallow water", "sand", "plains", "forest", "hills", "mountains")

# --- Strict elevation thresholds ------------------------------------------------
# Elevation and moisture are rank-equalised over the whole map (see _equalise), so
# these numbers are the share of the map below each level: any seed gives the same
# balanced mix of ~14% deep water ... ~52% flatland ... ~10% mountains.
DEEP_LEVEL = 0.14       # below: deep water
SHALLOW_LEVEL = 0.22    # below: shallow water
SAND_LEVEL = 0.26       # below: coastline sand
FLAT_LEVEL = 0.78       # below: flatland (plains / forest)
HILLS_LEVEL = 0.90      # below: hills, above: mountains
# Moisture only matters inside the flatland band (SAND_LEVEL..FLAT_LEVEL).
FOREST_MOISTURE = 0.60  # moisture above this turns plains into forest (~40% of flatland)

# --- Noise shape: low frequency + low persistence = wide, contiguous land -----
BASE_FREQUENCY = 2.0    # noise cycles across the map's longer side
OCTAVES = 4
PERSISTENCE = 0.45
LACUNARITY = 2.0
MOISTURE_FREQUENCY = 3.0  # forest masses are a bit smaller than continents


class FractalNoise:
    """Seedable fractal value noise (fBm): octaves of smooth lattice noise.

    Each octave doubles the frequency (`lacunarity`) and scales the amplitude
    by `persistence`, so a low persistence keeps the large shapes dominant.
    `sample()` returns a value in 0..1.
    """

    def __init__(self, seed, frequency: float = BASE_FREQUENCY, octaves: int = OCTAVES,
                 persistence: float = PERSISTENCE, lacunarity: float = LACUNARITY):
        rng = random.Random(seed)  # str/int seeds are both deterministic
        self.frequency, self.octaves = frequency, octaves
        self.persistence, self.lacunarity = persistence, lacunarity
        perm = list(range(256))
        rng.shuffle(perm)
        self._perm = perm * 2                       # doubled so lookups never wrap
        self._values = [rng.random() for _ in range(256)]
        # a random offset per octave stops the octaves lining up at the origin
        self._offsets = [(rng.uniform(0, 256), rng.uniform(0, 256)) for _ in range(octaves)]

    def _lattice(self, ix: int, iy: int) -> float:
        """Pseudo-random value at an integer lattice point (hashed via the permutation table)."""
        return self._values[self._perm[self._perm[ix & 255] + (iy & 255)]]

    def _value_noise(self, x: float, y: float) -> float:
        ix, iy = math.floor(x), math.floor(y)
        fx, fy = x - ix, y - iy
        fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)  # smoothstep fade
        top = self._lattice(ix, iy) + (self._lattice(ix + 1, iy) - self._lattice(ix, iy)) * fx
        bot = self._lattice(ix, iy + 1) + (self._lattice(ix + 1, iy + 1) - self._lattice(ix, iy + 1)) * fx
        return top + (bot - top) * fy

    def sample(self, x: float, y: float) -> float:
        """Fractal noise at (x, y) in 'cycles'; returns 0..1."""
        total = norm = 0.0
        amplitude, freq = 1.0, self.frequency
        for ox, oy in self._offsets:
            total += amplitude * self._value_noise(x * freq + ox, y * freq + oy)
            norm += amplitude
            amplitude *= self.persistence
            freq *= self.lacunarity
        return total / norm


def _equalise(values: list[float]) -> list[float]:
    """Replace each value by its rank (0..1) so the thresholds hit fixed map shares.

    Low-frequency noise has only a few big features, so raw values vary a lot from
    seed to seed (one seed might be nearly all sea). Ranking keeps the shapes but
    fixes how much of the map falls in each band.
    """
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    last = max(1, len(values) - 1)
    for position, index in enumerate(order):
        ranks[index] = position / last
    return ranks


def biome_at(elevation: float, moisture: float) -> int:
    """The strict biome matrix: elevation picks the band, moisture only refines flatland."""
    if elevation < DEEP_LEVEL:
        return DEEP_WATER
    elif elevation < SHALLOW_LEVEL:
        return SHALLOW_WATER
    elif elevation < SAND_LEVEL:
        return SAND
    elif elevation < FLAT_LEVEL:
        # Moisture is only consulted here, on the plains, so forests form their own
        # organic masses instead of hugging the foot of the mountains.
        if moisture > FOREST_MOISTURE:
            return FOREST
        return PLAINS
    elif elevation < HILLS_LEVEL:
        return HILLS
    return MOUNTAINS


def make_noise_fields(seed: int) -> tuple[FractalNoise, FractalNoise]:
    """Two completely separate noise fields (different seed streams) for elevation and moisture."""
    elevation = FractalNoise(f"elevation:{seed}", BASE_FREQUENCY)
    moisture = FractalNoise(f"moisture:{seed}", MOISTURE_FREQUENCY)
    return elevation, moisture


def generate_biome_map(width: int, height: int, seed: int) -> list[list[int]]:
    """Return `height` rows of `width` biome ids for the given seed."""
    elevation_noise, moisture_noise = make_noise_fields(seed)
    scale = 1.0 / max(width, height)  # resolution-independent: same shapes at any map size
    cells = [(x, y) for y in range(height) for x in range(width)]
    elevation = _equalise([elevation_noise.sample(x * scale, y * scale) for x, y in cells])
    moisture = _equalise([moisture_noise.sample(x * scale, y * scale) for x, y in cells])
    return [[biome_at(elevation[y * width + x], moisture[y * width + x]) for x in range(width)]
            for y in range(height)]
