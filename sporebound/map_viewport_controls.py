"""Pure viewport math for the Tk map editor.

No tkinter import: geometry can be regression-tested headlessly.
Map document coordinates remain independent from scroll and zoom.
"""


MIN_TILE_SIZE = 24
MAX_TILE_SIZE = 96


def fit_zoom(current_tile_size, scene_width, scene_height,
             viewport_width, viewport_height, *, padding=24):
    """Choose a bounded tile size to fit actual rendered scene bounds.

    Works for both 2D and isometric projections because scene bounds
    come from the renderer's canvas scrollregion, not guessed tile shapes.
    """
    if scene_width <= 0 or scene_height <= 0:
        return max(MIN_TILE_SIZE, min(MAX_TILE_SIZE, int(current_tile_size)))
    available_width = max(1, viewport_width - 2 * padding)
    available_height = max(1, viewport_height - 2 * padding)
    ratio = min(available_width / scene_width,
                available_height / scene_height)
    proposed = int(current_tile_size * ratio)
    return max(MIN_TILE_SIZE, min(MAX_TILE_SIZE, proposed))


def scroll_fraction(region_min, region_max, viewport_size, point, screen_coordinate):
    """Canvas xview/yview fraction to place a world point at a screen pixel."""
    extent = region_max - region_min
    if extent <= 0 or viewport_size >= extent:
        return 0.0
    requested = (point - screen_coordinate - region_min) / extent
    return max(0.0, min(1.0, requested))
