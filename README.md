# citysim

A city design sandbox in Python, like SimCity without the gameplay: no money,
score or goals. You lay out roads and zones, and the simulation reacts.

## Setup

```
pip install -r requirements.txt
```

## Run

From the repo root:

```
python3 run.py --demo        # start with an example street grid
python3 run.py               # blank map with a river and a lake
python3 -m citysim --demo    # equivalent
```

Options: `--size W H` (default 80 60), `--seed N`, `--load city.json`, `--tile PX` (pixels per cell).
Headless snapshot: `python3 run.py --png out.png --ticks 300 --overlay traffic`
(overlays: `land value`, `pollution`, `traffic`, `desirability`).

Don't run `citysim/app.py` directly; it is part of a package and uses relative imports.

## Controls

| Key | Action |
| --- | --- |
| `1`-`6` | Road, residential, commercial, industrial, park, bulldoze |
| Mouse drag | Road tool: draw roads. Zone, park and bulldoze tools: drag a rectangle (its size is shown) |
| `O` | Cycle overlays |
| `Space` | Pause / resume |
| `+` / `-` | Change speed |
| `.` | Advance one tick |
| `S` / `L` | Save / load `city.json` |
| `Esc` | Quit |

## Scale

A chunky pixel-art tile map (default 80x60 tiles). Roads are 1 tile wide; zones are rectangles you
drag out, typically around 3x3. A tile can use any road within 3 tiles. Roads can cross water (bridges).

## What it simulates

This is a sandbox for leisurely city building: no money, demand, goals or disasters.

- **Growth**: zoned tiles next to a road slowly fill in (levels 0-3). Nothing is required to make them grow.
- **Pollution**: produced by industry and traffic; reduced by parks. Affects how nice homes are.
- **Land value**: raised by parks, water and shops; lowered by pollution.
- **Traffic**: each home sends commuters along the road network to its nearest job. Overlays show the
  load; homes with no road route to a job count as "unserved".

## Layout

- `citysim/world.py`: grid state, editing, save/load
- `citysim/sim.py`: simulation rules
- `citysim/render.py`: rasterises the map (used by the window and PNG export)
- `citysim/app.py`: pygame interface
- `citysim/demo.py`: example starter city
