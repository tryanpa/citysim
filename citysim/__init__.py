"""citysim: a gameplay-free city design sandbox.

Imports are lazy so `citysim.terrain` (pure Python) can be used without numpy.
"""

__all__ = ["World", "Zone", "Simulation"]


def __getattr__(name):
    if name in ("World", "Zone"):
        from . import world
        return getattr(world, name)
    if name == "Simulation":
        from .sim import Simulation
        return Simulation
    raise AttributeError(name)
