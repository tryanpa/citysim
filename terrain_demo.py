"""Standalone terrain viewer: pygame + the pure-Python generator in citysim/terrain.py.

    python3 terrain_demo.py [seed]

R = random seed, Left/Right = previous/next seed, Esc = quit.
"""
import random
import sys

import pygame

from citysim import terrain

# --- Render & resolution pipeline ---------------------------------------------
# The world is drawn 1 pixel per cell on a small internal surface, then scaled up
# with nearest-neighbour (pygame.transform.scale) to fill the window: sharp, chunky
# retro pixels, and only SCALE**2 times fewer pixels to generate and draw.
WINDOW_SIZE = (768, 512)
SCALE = 4
INTERNAL_SIZE = (WINDOW_SIZE[0] // SCALE, WINDOW_SIZE[1] // SCALE)


def draw_terrain(surface: pygame.Surface, biome_map: list[list[int]]) -> None:
    """Paint biome ids onto the internal surface, one flat palette colour per pixel."""
    pixels = bytearray()
    for row in biome_map:
        for biome in row:
            pixels += bytes(terrain.PALETTE[biome])
    surface.blit(pygame.image.frombuffer(bytes(pixels), surface.get_size(), "RGB"), (0, 0))


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randrange(10_000)
    pygame.init()
    window = pygame.display.set_mode(WINDOW_SIZE)
    internal = pygame.Surface(INTERNAL_SIZE)
    dirty, running = True, True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    seed, dirty = random.randrange(10_000), True
                elif event.key in (pygame.K_RIGHT, pygame.K_LEFT):
                    seed, dirty = seed + (1 if event.key == pygame.K_RIGHT else -1), True
        if dirty:
            draw_terrain(internal, terrain.generate_biome_map(*INTERNAL_SIZE, seed))
            pygame.transform.scale(internal, WINDOW_SIZE, window)  # nearest-neighbour upscale
            pygame.display.set_caption(f"terrain seed {seed}  (R random, arrows step)")
            pygame.display.flip()
            dirty = False
        pygame.time.wait(30)
    pygame.quit()


if __name__ == "__main__":
    main()
