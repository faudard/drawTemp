"""Textured orthographic map painter for the existing Tk Studio viewport.

Shares the Qt 2D starter atlas and four-quadrant AutoTiles. Presentation-only:
all painting, selection, Battle state, 2D picking and JSON stay canonical.
"""
from __future__ import annotations

from collections import defaultdict

from drawtemp.render.autotile2d import tile_key
from .iso_actor_atlas import actor_direction, actor_style
from .iso_map import SURFACE_COLORS
from .iso_structures import structure_template
from .topdown_tk_art import BoardTileIndex


def _layer_rows(visual_layers, plane):
    """Yields authored overlay cells in layer order, with their alpha masks."""
    for layer in visual_layers:
        if (layer.get("plane") != plane or not layer.get("visible", True)
                or layer.get("opacity", 100) <= 0):
            continue
        for cell in layer.get("cells", ()):
            if any(cell["mask"]):
                yield layer, cell


def draw_topdown(canvas, board, mission, units, *, cell_size, layers,
                 selected_cell, selected_tiles=(), atlas=None, props=None,
                 actors=None, objects_atlas=None, buildings=None, fortifications=None,
                 visual_layers=(), reachable=(), deploying=False, active_id=None,
                 relic=None, grid=False):
    """Draw a complete 2D scene with honest ordering: terrain, underlays,
    props/buildings/objects/actors, overlaid art and editing selection.
    No command in this function writes to a map, Battle or project.
    """
    canvas.delete("all")
    if atlas is not None:
        atlas.begin_frame()
    width, height = board.width, board.height
    canvas.configure(scrollregion=(0, 0, width * cell_size, height * cell_size))
    indexed = BoardTileIndex(board)
    shows = lambda name: layers.get(name, True)
    goal_cells = set(mission.goal)
    deploy_cells = ({tuple(p) for zone in mission.deployment
                     for p in zone["cells"]} if shows("Déploiement") else set())
    danger_cells = ({tuple(p) for obj in mission.objects
                     if obj["kind"] == "defense" and not obj.get("disabled")
                     and obj.get("charges", 2) > 0
                     for p in obj["cells"]} if shows("Objets") else set())
    reachable = set(reachable)

    # First pass: genuine RGBA terrain textures, with neighbor-aware masks.
    # One image is retained per *unique* topology, never per map cell.
    for x, y in board.cells():
        tile = board.tile((x, y))
        px, py = x * cell_size, y * cell_size
        image = None
        if shows("Terrain") and atlas is not None:
            image = atlas.terrain(tile_key(indexed, x, y), cell_size)
        if image is None:
            canvas.create_rectangle(
                px, py, px + cell_size, py + cell_size,
                fill=SURFACE_COLORS.get(tile.surface, "#889b85"),
                outline="", tags=("topdown_terrain",))
        else:
            canvas.create_image(px, py, image=image, anchor="nw",
                                tags=("topdown_terrain", "topdown_autotile"))
        # These overlays preserve the tactical information from the old
        # schematic view without replacing the textured ground with flat tiles.
        tint = None
        if tile.blocked and tile.surface not in ("water", "bridge"):
            tint = "#3d4350"
        if tile.cost > 1:
            tint = "#b59b6f"
        if tile.cover:
            tint = "#719f78"
        if tile.hazard:
            tint = "#cf6959"
        if (x, y) in deploy_cells and deploying:
            tint = "#46b9d3"
        if shows("Objectifs") and (x, y) in goal_cells:
            tint = "#dfbf56"
        if (x, y) in danger_cells:
            tint = "#e98c6e"
        if tint:
            canvas.create_rectangle(px, py, px + cell_size, py + cell_size,
                                    fill=tint, stipple="gray50", outline="",
                                    tags=("topdown_tactical_overlay",))
        # Deliberate shorelines for water/bridges (which the land-only
        # 2x2 blending rule excludes). Edges depend solely on adjacent cells.
        if shows("Terrain") and tile.surface == "water":
            edges = (((0, -1), (px, py + 1, px + cell_size, py + 1)),
                     ((1, 0), (px + cell_size - 1, py,
                               px + cell_size - 1, py + cell_size)),
                     ((0, 1), (px, py + cell_size - 1,
                               px + cell_size, py + cell_size - 1)),
                     ((-1, 0), (px + 1, py, px + 1, py + cell_size)))
            for (dx, dy), segment in edges:
                other = (x + dx, y + dy)
                if (board.contains(other) and
                        board.tile(other).surface not in ("water", "bridge")):
                    canvas.create_line(*segment, fill="#d2e8cc",
                                       width=max(2, cell_size // 17),
                                       tags=("topdown_shoreline",))
        if shows("Relief"):
            for dx, dy, line in (
                    (1, 0, (px + cell_size - 1, py,
                            px + cell_size - 1, py + cell_size)),
                    (0, 1, (px, py + cell_size - 1,
                            px + cell_size, py + cell_size - 1))):
                other = (x + dx, y + dy)
                if (board.contains(other) and
                        tile.height != board.tile(other).height):
                    canvas.create_line(*line, fill="#53646d",
                                       width=max(2, cell_size // 24),
                                       tags=("topdown_height_edge",))
        if grid:
            canvas.create_rectangle(px, py, px + cell_size, py + cell_size,
                                    fill="", outline="#62745f",
                                    tags=("topdown_grid",))
        if (x, y) in reachable:
            canvas.create_rectangle(px + 1, py + 1,
                                    px + cell_size - 1, py + cell_size - 1,
                                    outline="#32894b", width=2,
                                    tags=("topdown_reachable",))
        if shows("Relief") and tile.height:
            canvas.create_text(px + 4, py + 4, text=str(tile.height),
                               anchor="nw", fill="#192d41",
                               tags=("topdown_height",))
        if shows("Terrain") and tile.hazard:
            canvas.create_text(px + cell_size - 3, py + 4,
                               text="!", anchor="ne", fill="#7d1713",
                               tags=("topdown_hazard",))

    def painted_layers(plane):
        if atlas is None:
            return
        for layer, art in _layer_rows(visual_layers, plane):
            x, y = art["pos"]
            if not board.contains((x, y)):
                continue
            variant = (x * 17 + y * 29) & 1
            image = atlas.layer(art["material"], art["mask"], variant,
                                layer["opacity"], cell_size)
            if image is not None:
                canvas.create_image(x * cell_size, y * cell_size,
                                    image=image, anchor="nw",
                                    tags=("topdown_visual_layer",
                                          "topdown_plane_" + plane, layer["id"]))

    if shows("Décors"):
        painted_layers("below")

    # Only show a passage line when the authored target is present and valid.
    if shows("Objets"):
        for obj in mission.objects:
            if obj["kind"] != "passage":
                continue
            target = obj.get("destination")
            if target is None or len(target) != 2:
                continue
            x, y = obj["pos"]
            tx, ty = target
            canvas.create_line((x + .5) * cell_size, (y + .5) * cell_size,
                               (tx + .5) * cell_size, (ty + .5) * cell_size,
                               fill="#704ba0", width=2,
                               dash=() if obj.get("enabled", True) else (4, 3),
                               arrow="last", tags=("topdown_passage",))

    objects_by_row = defaultdict(list)
    if shows("Objets"):
        for obj in mission.objects:
            objects_by_row[obj["pos"][1]].append(obj)
    actors_by_row = defaultdict(list)
    if shows("Unités"):
        for unit in units:
            actors_by_row[unit.pos[1]].append(unit)
    structures_by_row = defaultdict(list)
    structured_footprints = set()
    if shows("Bâtiments"):
        for structure in getattr(mission, "structures", ()):
            clip = structure_template(structure["name"], structure["turns"],
                                      door_slot=structure.get("door_slot", 0))
            ax, ay = structure["anchor"]
            structures_by_row[ay + clip.height - 1].append(
                (structure, clip.width, clip.height))
            for dy in range(clip.height):
                for dx in range(clip.width):
                    structured_footprints.add((ax + dx, ay + dy))

    # Draw in increasing Y so tall transparent props remain visually coherent
    # over northern ground, and later rows can occlude their southern halves.
    for y in range(height):
        if shows("Décors"):
            for x in range(width):
                tile = board.tile((x, y))
                if not tile.feature or (x, y) in structured_footprints:
                    continue
                image = (props.sprite(tile.feature, max(20, round(cell_size * .60)))
                         if props is not None else None)
                if image is not None:
                    canvas.create_image((x + .5) * cell_size,
                                        (y + 1) * cell_size,
                                        image=image, anchor="s",
                                        tags=("topdown_decor",))
                else:
                    canvas.create_oval(
                        (x + .25) * cell_size, (y + .25) * cell_size,
                        (x + .75) * cell_size, (y + .75) * cell_size,
                        fill="#4e7654", outline="#29452d",
                        tags=("topdown_decor_fallback",))
        for structure, sw, sh in structures_by_row[y]:
            ax, ay = structure["anchor"]
            name = structure["name"]
            turns = structure["turns"]
            from .iso_building_atlas import BUILDING_FRAMES
            loader = (buildings if (name, turns % 2) in BUILDING_FRAMES
                      else fortifications)
            image = (loader.sprite(name, turns, max(12, cell_size // 2))
                     if loader is not None else None)
            cx = (ax + sw / 2) * cell_size
            bottom = (ay + sh) * cell_size
            if image is not None:
                canvas.create_image(cx, bottom, image=image, anchor="s",
                                    tags=("topdown_structure",))
            else:
                canvas.create_rectangle(ax * cell_size, ay * cell_size,
                                        (ax + sw) * cell_size, bottom,
                                        outline="#544e49", width=3,
                                        tags=("topdown_structure_fallback",))
                canvas.create_text(cx, (ay + sh / 2) * cell_size,
                                   text=name[:9],
                                   tags=("topdown_structure_fallback",))
        for obj in objects_by_row[y]:
            x, oy = obj["pos"]
            image = (objects_atlas.sprite(obj["kind"], cell_size)
                     if objects_atlas is not None else None)
            cx, bottom = (x + .5) * cell_size, (oy + 1) * cell_size
            if image is not None:
                canvas.create_image(cx, bottom, image=image, anchor="s",
                                    tags=("topdown_object",))
            else:
                canvas.create_rectangle(cx - 7, bottom - 22,
                                        cx + 7, bottom - 8,
                                        fill="#9e79bd", outline="#6b438d",
                                        tags=("topdown_object_fallback",))
                canvas.create_text(cx, bottom - 15, text=obj["kind"][:2],
                                   fill="#251236",
                                   tags=("topdown_object_fallback",))
        for unit in actors_by_row[y]:
            x, uy = unit.pos
            cx, bottom = (x + .5) * cell_size, (uy + 1) * cell_size
            color = "#3b82c4" if unit.team == "player" else "#c45a51"
            if not unit.alive:
                color = "#7e838a"
            canvas.create_oval(cx - cell_size * .28, bottom - cell_size * .22,
                               cx + cell_size * .28, bottom - 1,
                               fill=color, outline="#e7ecef" if unit.id == active_id
                               else "", width=2,
                               tags=("topdown_actor_shadow",))
            image = (actors.sprite(actor_style(unit), actor_direction(unit),
                                   0, cell_size)
                     if actors is not None else None)
            if image is not None:
                canvas.create_image(cx, bottom, image=image, anchor="s",
                                    tags=("topdown_actor",))
            else:
                canvas.create_text(cx, bottom - cell_size * .55,
                                   text=unit.name[:3],
                                   fill="#101b27",
                                   tags=("topdown_actor_fallback",))
            if active_id == unit.id:
                canvas.create_rectangle(x * cell_size + 2, uy * cell_size + 2,
                                        (x + 1) * cell_size - 2,
                                        (uy + 1) * cell_size - 2,
                                        outline="#fbe085", width=2,
                                        tags=("topdown_active",))

    if relic is not None and shows("Objectifs"):
        x, y = relic
        canvas.create_text((x + .5) * cell_size, (y + .5) * cell_size,
                           text="✦", fill="#9a6607",
                           font=("TkDefaultFont", 16, "bold"),
                           tags=("topdown_relic",))

    # Above-plane painted art really does cover the actors; the selection
    # highlight is deliberately drawn last so authoring remains operable.
    if shows("Décors"):
        painted_layers("above")
    for sx, sy in sorted(selected_tiles):
        canvas.create_rectangle(
            sx * cell_size + 3, sy * cell_size + 3,
            (sx + 1) * cell_size - 3, (sy + 1) * cell_size - 3,
            outline="#1f6e9a", width=2, tags=("selection",))
    if selected_cell is not None and board.contains(selected_cell):
        x, y = selected_cell
        canvas.create_rectangle(x * cell_size + 2, y * cell_size + 2,
                                (x + 1) * cell_size - 2,
                                (y + 1) * cell_size - 2,
                                outline="#2456bd", width=2,
                                tags=("selection",))


__all__ = ["draw_topdown", "_layer_rows"]
