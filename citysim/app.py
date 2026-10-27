"""Interactive pygame front-end."""
from __future__ import annotations

import pygame

from .render import OVERLAYS, tile_colors
from .sim import Simulation
from .world import World, Zone

TOOLS = [  # key, label, action
    (pygame.K_1, "Road", "road"), (pygame.K_2, "Residential", Zone.RESIDENTIAL),
    (pygame.K_3, "Commercial", Zone.COMMERCIAL), (pygame.K_4, "Industrial", Zone.INDUSTRIAL),
    (pygame.K_5, "Park", Zone.PARK), (pygame.K_6, "Bulldoze", "bulldoze"),
]
SPEEDS = [0, 1, 2, 4, 8]  # sim ticks per second


def apply_rect(world: World, tool, a: tuple[int, int], b: tuple[int, int]) -> None:
    if tool == "bulldoze":
        world.bulldoze_rect(*a, *b)
    else:
        world.set_zone_rect(*a, *b, tool)


def run(world: World, path: str = "city.json", tile: int = 12) -> None:
    pygame.init()
    sim = Simulation(world)
    sim.step()
    hud_h = 62
    screen = pygame.display.set_mode((world.width * tile, world.height * tile + hud_h))
    pygame.display.set_caption("citysim")
    # draw 1 pixel per cell, then nearest-neighbour upscale: crisp chunky pixel art
    internal = pygame.Surface((world.width, world.height))
    map_size = (world.width * tile, world.height * tile)
    font = pygame.font.SysFont("monospace", 14)
    clock = pygame.time.Clock()
    tool, tool_name, overlay, speed_i, acc = "road", "Road", "none", 2, 0.0
    last = None   # last painted cell, so road drags have no gaps
    start = None  # corner of the zone / bulldoze rectangle being dragged
    painting = False

    def cell_at(pos):
        c = (pos[0] // tile, pos[1] // tile)
        return c if pos[1] < world.height * tile and world.in_bounds(*c) else None
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
                painting, last, start = True, None, cell_at(e.pos)
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                end = cell_at(e.pos)
                if painting and tool != "road" and start and end:
                    apply_rect(world, tool, start, end)
                painting, start = False, None
        if painting and tool == "road":
            cell = cell_at(pygame.mouse.get_pos())
            if cell:
                for x, y in world.line(*(last or cell), *cell):
                    world.build_road(x, y)
                last = cell
        if SPEEDS[speed_i]:
            acc += dt * SPEEDS[speed_i]
            while acc >= 1:
                sim.step()
                acc -= 1
        if internal.get_size() != (world.width, world.height):
            internal = pygame.Surface((world.width, world.height))
        pygame.surfarray.blit_array(internal, tile_colors(sim, overlay).swapaxes(0, 1))
        screen.fill((25, 25, 28))
        pygame.transform.scale(internal, map_size, screen.subsurface((0, 0, *map_size)))
        if painting and tool != "road" and start:
            cur = cell_at(pygame.mouse.get_pos()) or start
            x0, x1 = sorted((start[0], cur[0]))
            y0, y1 = sorted((start[1], cur[1]))
            pygame.draw.rect(screen, (255, 255, 255),
                             (x0 * tile, y0 * tile, (x1 - x0 + 1) * tile, (y1 - y0 + 1) * tile), 2)
            label = font.render(f"{x1 - x0 + 1} x {y1 - y0 + 1}", True, (255, 255, 255), (0, 0, 0))
            screen.blit(label, (x0 * tile, max(0, y0 * tile - 18)))
        s = sim.stats
        lines = [
            f"tool: {tool_name}   overlay: {overlay}   speed: {SPEEDS[speed_i]}x   tick {world.tick}",
            f"pop {s.get('population', 0)}  jobs {s.get('jobs', 0)}  unserved {int(s.get('unserved', 0))}"
            f"  | 1 road (drag)  2-6 zones/bulldoze (drag a rectangle)",
            "O overlay  SPACE pause  +/- speed  . step  S save  L load",
        ]
        for i, t in enumerate(lines):
            screen.blit(font.render(t, True, (230, 230, 230)), (6, world.height * tile + 4 + i * 18))
        pygame.display.flip()
    pygame.quit()
