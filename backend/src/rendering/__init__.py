"""Rendering: predictions drawn onto real imagery.

Separate from `api/` because it is not a transport concern, and separate from `models/`
because it computes nothing — it only draws what those produced. Nothing in here
generates imagery; see plume_map's docstring for why that distinction is load-bearing.
"""

from .plume_map import frame_times, load_basemap, render

__all__ = ["frame_times", "load_basemap", "render"]
