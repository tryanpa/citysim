import argparse

from .demo import demo_city
from .sim import Simulation
from .world import World


def main() -> None:
    p = argparse.ArgumentParser(prog="citysim", description="Gameplay-free city sandbox")
    p.add_argument("--size", type=int, nargs=2, default=(80, 60), metavar=("W", "H"))
    p.add_argument("--seed", type=int)
    p.add_argument("--load", help="load a saved city (json)")
    p.add_argument("--demo", action="store_true", help="start with an example street grid")
    p.add_argument("--png", help="run headless, write a PNG snapshot and exit")
    p.add_argument("--ticks", type=int, default=300, help="ticks to simulate with --png")
    p.add_argument("--overlay", default="none")
    a = p.parse_args()

    world = World.load(a.load) if a.load else World(*a.size, seed=a.seed)
    if not a.load:
        world.generate_terrain()
    if a.demo or (a.png and not a.load):
        demo_city(world)

    if a.png:
        from PIL import Image
        from .render import render
        sim = Simulation(world)
        for _ in range(a.ticks):
            sim.step()
        Image.fromarray(render(sim, a.overlay)).save(a.png)
        print({k: round(v, 2) if isinstance(v, float) else v for k, v in sim.stats.items()})
    else:
        from .app import run
        run(world)


main()
