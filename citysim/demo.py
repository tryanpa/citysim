"""Seed a small example city so the sandbox doesn't start blank.

Scale: 1 cell ~ 10 m, so roads are 1 cell wide and zones are 10x10 blocks.
"""
from __future__ import annotations

from .world import World, Zone


def demo_city(world: World) -> None:
    w, h = world.width, world.height
    mid, block = h // 2, 10
    for x in range(6, w - 6):
        world.build_road(x, mid)
    xs = list(range(22, w - 12, 22))
    for x in xs:
        for y in range(mid - block - 2, mid + block + 3):
            world.build_road(x, y)
    for i, x in enumerate(xs):
        zone = Zone.INDUSTRIAL if i == len(xs) - 1 else (Zone.COMMERCIAL if i % 3 == 1 else Zone.RESIDENTIAL)
        for x0 in (x - block, x + 1):  # a block on each side of the avenue
            world.set_zone_rect(x0, mid - block, x0 + block - 1, mid - 1, zone)
            world.set_zone_rect(x0, mid + 1, x0 + block - 1, mid + block, zone)
    px = xs[0] + 12
    world.set_zone_rect(px, mid + 3, px + 7, mid + 9, Zone.PARK)
