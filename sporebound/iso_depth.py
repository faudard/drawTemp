"""Projection and depth ordering shared by the isometric authoring/play scene.

Pure functions: no Tk dependency, no Battle access, no game-state mutations.
"""
from math import floor


def visual_position(actor, poses=None):
    """Select a cosmetic MotionDirector pose or authoritative board position."""
    # Legacy presentation tests can use anonymous unit-like objects. An ID
    # is required only to look up an optional animated pose, not for cutaway.
    pose = (poses or {}).get(getattr(actor, 'id', None))
    return (float(pose.x), float(pose.y)) if pose is not None else tuple(actor.pos)


def visual_height(board, xy):
    """Bilinear interpolation of authored tactical heights for animated feet.

    Samples only existing board cells. It never affects collision or physics.
    """
    x, y = xy
    x = max(0., min(board.width-1., x))
    y = max(0., min(board.height-1., y))
    x0, y0 = int(floor(x)), int(floor(y))
    x1, y1 = min(board.width-1, x0+1), min(board.height-1, y0+1)
    tx, ty = x-x0, y-y0
    h00, h10 = board.tile((x0, y0)).height, board.tile((x1, y0)).height
    h01, h11 = board.tile((x0, y1)).height, board.tile((x1, y1)).height
    return ((h00*(1-tx)+h10*tx)*(1-ty)
            + (h01*(1-tx)+h11*tx)*ty)


def visual_center(geo, actor, poses=None):
    """Project a fractional pose to a continuous isometric screen location."""
    x, y = visual_position(actor, poses)
    return (geo.origin_x+(x-y)*geo.half_width,
            geo.origin_y+(x+y)*geo.half_height
            -visual_height(geo.board, (x, y))*geo.step)


def actor_depth(actor, poses=None):
    """Depth is measured at the feet rather than at the actor's sprite top."""
    x, y = visual_position(actor, poses)
    return x+y


def architecture_depth(building):
    """A building is composited at the foremost part of its ground footprint."""
    return max(x+y for x, y in building.cells)


def depth_order(instances, units, poses=None):
    """Return back-to-front Canvas groups, independently of widget ordering."""
    groups = [(architecture_depth(building), 0, i,
               'architecture_instance_' + str(i))
              for i, building in enumerate(instances)]
    groups.extend((actor_depth(actor, poses), 1, i,
                   'iso_actor_unit_' + str(i))
                  for i, actor in enumerate(units))
    return tuple(tag for _, _, _, tag in sorted(groups))


def cutaway_intersects(instance, actor, poses=None):
    """Expose roofs while the animated footprint crosses the interior.

    Inclusive fractional overlap avoids one-frame roof flashes at doorways.
    """
    if not getattr(actor, 'alive', True):
        return False
    x, y = visual_position(actor, poses)
    width, height = actor.footprint
    return any(x < cx+1 and x+width > cx and y < cy+1 and y+height > cy
               for cx, cy in instance.cells)
