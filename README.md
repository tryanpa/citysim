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

Options: `--size W H` (default 160 110), `--seed N`, `--load city.json`, `--tile PX` (pixels per cell).
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

One cell is about 10 m. Roads are 1 cell wide; zones are rectangles you drag out, typically around
10x10 cells. Buildings grow in 2x2 lots, and a lot can use any road within 5 cells. Roads can cross water (bridges).

## What it simulates

- **Growth**: zoned lots next to a road grow or shrink between levels 0-3 based on desirability.
- **Pollution**: produced by industry and traffic; reduced by parks.
- **Land value**: raised by parks, water and shops; lowered by pollution.
- **Traffic**: each home sends commuters along the road network to its nearest job. Homes with no road route to a job count as "unserved".
- **Demand**: residential, commercial and industrial zones each need the other two.

## Layout

- `citysim/world.py`: grid state, editing, save/load
- `citysim/sim.py`: simulation rules
- `citysim/render.py`: rasterises the map (used by the window and PNG export)
- `citysim/app.py`: pygame interface
- `citysim/demo.py`: example starter city
