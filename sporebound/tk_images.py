"""Shared bounded whole-frame Tk resizing, imported without initializing Tk."""

def nearest_scale_factors(source_size, target_size):
    """Small integer zoom/subsample ratio approximating a target pixel size.

    Tk's photo copy with -zoom a -subsample b samples the SOURCE at
    b-pixel steps before magnification. It only repeats a small source
    corner for large PNGs. A separate magnification step is required.
    """
    if source_size < 1 or target_size < 1:
        raise ValueError("Image dimensions must be positive")
    candidates = []
    # Bound temporary images (one axis <= 2048px) while allowing
    # precise resizing of small 64px atlas sprites at high camera zoom.
    max_zoom = max(1, min(16, 2048 // source_size))
    for zoom in range(1, max_zoom + 1):
        estimated = max(1, round(source_size * zoom / target_size))
        for subsample in range(max(1, estimated - 2), estimated + 3):
            output = (source_size * zoom + subsample - 1) // subsample
            candidates.append((abs(output - target_size), zoom, subsample))
    _, zoom, subsample = min(candidates)
    return zoom, subsample


def resize_photo(photo, width, height, *, master):
    """Enlarge before sampling so every part of the frame survives reduction."""
    if (photo.width(), photo.height()) == (width, height):
        return photo
    import tkinter as tk
    zx, sx = nearest_scale_factors(photo.width(), width)
    zy, sy = nearest_scale_factors(photo.height(), height)
    intermediate = photo.zoom(zx, zy)
    sampled = intermediate.subsample(sx, sy)
    sw, sh = sampled.width(), sampled.height()
    result = tk.PhotoImage(master=master, width=width, height=height)
    x, y = max(0, (sw-width)//2), max(0, (sh-height)//2)
    result.tk.call(str(result), 'copy', str(sampled),
                   '-from', x, y, x+min(sw, width), y+min(sh, height),
                   '-to', max(0, (width-sw)//2), max(0, (height-sh)//2))
    return result


def crop_scaled(source, region, size, *, master):
    """Crop before zooming: adjacent atlas frames cannot bleed into the result."""
    import tkinter as tk
    x, y, width, height = region
    frame = tk.PhotoImage(master=master, width=width, height=height)
    frame.tk.call(str(frame), 'copy', str(source),
                  '-from', x, y, x+width, y+height, '-to', 0, 0)
    return resize_photo(frame, *size, master=master)
