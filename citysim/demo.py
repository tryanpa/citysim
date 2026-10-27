"""Seed a small example city so the sandbox doesn't start blank."""
from __future__ import annotations

from .world import World, Zone


def demo_city(world: World) -> None:
    w, h = world.width, world.height
    mid = h // 2
    for x in range(4, w - 4):
        world.build_road(x, mid)
    for x in range(10, w - 10, 12):
        for y in range(6, h - 6):
            world.build_road(x, y)
    for x in range(4, w - 4):
        for dy in (-1, 1, -2, 2):
            y = mid + dy
            if abs(dy) == 1:
                zone = Zone.RESIDENTIAL if (x // 12) % 2 == 0 else Zone.COMMERCIAL
            else:
                zone = Zone.INDUSTRIAL if x > w * 0.7 else Zone.RESIDENTIAL
            world.set_zone(x, y, zone)
    for x in range(14, 20):
        for y in range(mid + 4, mid + 8):
            world.set_zone(x, y, Zone.PARK)
