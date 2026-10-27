"""Interactive pygame front-end."""
from __future__ import annotations

import pygame

from .render import OVERLAYS, render
from .sim import Simulation
from .world import World, Zone

TOOLS = [  # key, label, action
    (pygame.K_1, "Road", "road"), (pygame.K_2, "Residential", Zone.RESIDENTIAL),
    (pygame.K_3, "Commercial", Zone.COMMERCIAL), (pygame.K_4, "Industrial", Zone.INDUSTRIAL),
    (pygame.K_5, "Park", Zone.PARK), (pygame.K_6, "Bulldoze", "bulldoze"),
]
SPEEDS = [0, 1, 2, 4, 8]  # sim ticks per second


def apply_tool(world: World, tool, x: int, y: int) -> None:
    if tool == "road":
        world.build_road(x, y)
    elif tool == "bulldoze":
        world.bulldoze(x, y)
    else:
        world.set_zone(x, y, tool)


def run(world: World, path: str = "city.json", tile: int = 12) -> None:
    pygame.init()
    sim = Simulation(world)
    sim.step()
    hud_h = 44
    screen = pygame.display.set_mode((world.width * tile, world.height * tile + hud_h))
    pygame.display.set_caption("citysim")
    font = pygame.font.SysFont("monospace", 14)
    clock = pygame.time.Clock()
    tool, tool_name, overlay, speed_i, acc = "road", "Road", "none", 2, 0.0
    last = None  # last painted cell, for continuous drag lines
    painting = False
    running = True
    while running:
        dt = clock.tick(60) / 1000
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                for key, name, act in TOOLS:
                    if e.key == key:
                        tool, tool_name = act, name
                if e.key == pygame.K_o:
                    overlay = OVERLAYS[(OVERLAYS.index(overlay) + 1) % len(OVERLAYS)]
                elif e.key == pygame.K_SPACE:
                    speed_i = 0 if speed_i else 2
                elif e.key in (pygame.K_EQUALS, pygame.K_PLUS):
                    speed_i = min(speed_i + 1, len(SPEEDS) - 1)
                elif e.key == pygame.K_MINUS:
                    speed_i = max(speed_i - 1, 0)
                elif e.key == pygame.K_PERIOD:
                    sim.step()
                elif e.key == pygame.K_s:
                    world.save(path)
                elif e.key == pygame.K_l:
                    try:
                        loaded = World.load(path)
                    except OSError:
                        continue
                    if (loaded.width, loaded.height) == (world.width, world.height):
                        world = loaded
                        sim = Simulation(world)
                        sim.step()
                elif e.key == pygame.K_ESCAPE:
                    running = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                painting, last = True, None
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                painting = False
        if painting:
            mx, my = pygame.mouse.get_pos()
            cell = (mx // tile, my // tile)
            if my < world.height * tile and world.in_bounds(*cell):
                for x, y in world.line(*(last or cell), *cell):
                    apply_tool(world, tool, x, y)
                last = cell
        if SPEEDS[speed_i]:
            acc += dt * SPEEDS[speed_i]
            while acc >= 1:
                sim.step()
                acc -= 1
        surf = pygame.surfarray.make_surface(render(sim, overlay, tile).swapaxes(0, 1))
        screen.fill((25, 25, 28))
        screen.blit(surf, (0, 0))
        s = sim.stats
        lines = [
            f"tool: {tool_name}   overlay: {overlay}   speed: {SPEEDS[speed_i]}x   tick {world.tick}",
            f"pop {s.get('population', 0)}  jobs {s.get('jobs', 0)}  unserved {int(s.get('unserved', 0))}"
            f"  | 1-6 tools  O overlay  SPACE pause  +/- speed  . step  S save  L load",
        ]
        for i, t in enumerate(lines):
            screen.blit(font.render(t, True, (230, 230, 230)), (6, world.height * tile + 4 + i * 18))
        pygame.display.flip()
    pygame.quit()
