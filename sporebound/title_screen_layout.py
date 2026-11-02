"""Shared responsive bounds for Player title screen and Studio drag preview.

Positions are normalized top-left coordinates against the *current* viewport.
Each movable element retains its legacy size; smaller windows clamp it inside
the visible surface. Defaults preserve the original geometry byte-for-byte.
"""
ELEMENTS = ("logo", "title", "subtitle", "continue", "new", "load",
            "campaign_action", "options", "quit", "campaign", "footer")
CARD_KEYS = ("continue", "new", "load", "campaign_action", "options", "quit")


def default_boxes(width, height, layout):
    """Return semantic hit rectangles for the stock cinematic title menu."""
    x = layout["menu_x"] + (12 if layout["compact"] else 21)
    x1 = layout["menu_x"] + layout["menu_width"]
    head_w = x1 - x - 9
    cy = x + head_w / 2
    top = max(19, round(height * (.075 if not layout["compact"] else .045)))
    logo_h = 28 if layout["compact"] else 38
    title_top = top + (22 if layout["compact"] else 32)
    subtitle_top = top + (62 if layout["compact"] else 111)
    title_h = 40 if layout["compact"] else 64
    subtitle_h = 23
    boxes = {
        "logo": (cy - 25, top, cy + 25, top + logo_h),
        "title": (x, title_top, x + head_w, title_top + title_h),
        "subtitle": (x, subtitle_top, x + head_w, subtitle_top + subtitle_h),
        "campaign": tuple(layout["campaign"]),
        "footer": (layout["menu_x"], layout["footer_y"],
                   layout["menu_x"] + layout["menu_width"],
                   layout["footer_y"] + layout["footer_height"]),
    }
    boxes.update(zip(CARD_KEYS, (tuple(rect) for rect in layout["cards"])))
    return boxes


def relocate(rect, x, y, width, height):
    """Move a rectangle while preserving its dimensions and visibility."""
    x0, y0, x1, y1 = rect
    w, h = x1 - x0, y1 - y0
    new_x = min(max(0.0, float(x)), max(0.0, width - w))
    new_y = min(max(0.0, float(y)), max(0.0, height - h))
    return (new_x, new_y, new_x + w, new_y + h)


def resolve_boxes(width, height, layout, positions=None):
    """Apply optional normalized placements without changing legacy layouts."""
    result = default_boxes(width, height, layout)
    for key, xy in (positions or {}).items():
        if key in result:
            result[key] = relocate(result[key], xy[0] * width, xy[1] * height,
                                   width, height)
    return result


def placement(rect, width, height):
    """Store a dragged rectangle's top-left as normalized [x, y]."""
    return [round(rect[0] / width, 5), round(rect[1] / height, 5)]
