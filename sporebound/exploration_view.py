"""Lightweight Tk story staging for exploration and non-interactive cutscenes.

All drawing is derived from immutable state; this module never changes quest
flags, rewards, combat or saved positions.
"""
from math import sin


def draw_exploration(canvas, stage):
    canvas.delete("all")
    tile = 58
    ox, oy = 42, 25
    w, h = stage["width"], stage["height"]
    palette = {
        "fields": ("#334c39", "#405d42", "#688047", "#aeb26a"),
        "village": ("#554b43", "#6b5348", "#825d47", "#cf9c63"),
        "forest": ("#243e34", "#314e3a", "#426b47", "#a2af73"),
        "stone": ("#383d49", "#4d5661", "#707682", "#b7ab94"),
    }
    dark, ground, feature, gold = palette[stage["theme"]]
    canvas.configure(background=dark)
    occupied = {tuple(point["pos"]): point for point in stage["interactions"]}
    rocks = {tuple(point) for point in stage["blocked"]}
    for y in range(h):
        for x in range(w):
            px, py = ox + x * tile, oy + y * tile
            fill = dark if (x, y) in rocks else ground if (x + y) % 2 else feature
            canvas.create_rectangle(px, py, px + tile, py + tile,
                                    fill=fill, outline=dark)
            if (x, y) in rocks:
                canvas.create_rectangle(px + 9, py + 9, px + 48, py + 47,
                                        fill="#6a7466", outline="#222e2a", width=2)
                continue
            if stage["theme"] == "village" and (x, y) in {(2, 1), (5, 2), (7, 4)}:
                canvas.create_polygon(px + 7, py + 54, px + 19, py + 22,
                                      px + 30, py + 41, px + 40, py + 12,
                                      px + 51, py + 55, fill="#ca633c", outline="")
                canvas.create_polygon(px + 19, py + 54, px + 31, py + 33,
                                      px + 39, py + 54, fill="#ffc77a", outline="")
            if stage["theme"] == "fields":
                for shift in (12, 28, 43):
                    canvas.create_line(px + shift, py + 48, px + shift + 4, py + 16,
                                       fill=gold, width=2)
                    canvas.create_oval(px + shift, py + 14, px + shift + 8, py + 26,
                                       fill="#cec17c", outline="")
            point = occupied.get((x, y))
            if point:
                color = "#e1c878" if not point["visited"] else "#79bea2"
                if point["exit"]:
                    color = "#87bde2" if not stage["completed"] else "#79bea2"
                canvas.create_oval(px + 17, py + 11, px + 41, py + 35,
                                   fill=color, outline="#142a30", width=2)
                canvas.create_text(px + 29, py + 23, text="?" if not point["visited"] else "✓",
                                   fill="#24302d", font=("TkDefaultFont", 13, "bold"))
                canvas.create_text(px + 29, py + 49, text=point["title"][:11],
                                   fill="#fff5d1", font=("TkDefaultFont", 8, "bold"))
    for actor in stage.get("actors", []):
        if actor["status"] == "rescued":
            continue
        ax, ay = actor["pos"]
        sx, sy = ox + ax * tile + tile / 2, oy + ay * tile + tile / 2
        color = ("#82919a" if actor["status"] == "lost" else
                 "#f8c16f" if actor["kind"] == "civilian" else "#c5a6db")
        canvas.create_oval(sx - 13, sy - 14, sx + 13, sy + 12,
                           fill=color, outline="#172d36", width=2)
        canvas.create_text(sx, sy - 2, text=actor["name"][0],
                           fill="#24302b", font=("TkDefaultFont", 11, "bold"))
        canvas.create_text(sx, sy + 24,
                           text=actor["name"].split(",")[0][:10],
                           fill="#fff6dc", font=("TkDefaultFont", 8, "bold"))
    px, py = stage["position"]
    sx, sy = ox + px * tile + tile / 2, oy + py * tile + tile / 2
    canvas.create_oval(sx - 17, sy - 19, sx + 17, sy + 15,
                       fill="#5e7cc7", outline="#fff1ac", width=3)
    canvas.create_text(sx, sy - 2, text="J", fill="#ffffff",
                       font=("TkDefaultFont", 14, "bold"))
    canvas.create_text(ox, oy + h * tile + 20, anchor="w",
                       text="Jeanne : bleu   •   Civils : jaune   •   Témoins : violet   •   Souvenirs : or / vert   •   Sortie : bleu clair",
                       fill="#dfd5af", font=("TkDefaultFont", 10))


def draw_story_backdrop(canvas, scene_id, phase=0):
    """Procedural, optional cinematic backdrop for Jeanne's authored scenes."""
    is_jeanne = scene_id.startswith("sc_p0_")
    if not is_jeanne:
        return False
    canvas.delete("all")
    width, height = 860, 210
    fire = scene_id in ("sc_p0_fumee", "sc_p0_cendres", "sc_p0_apres_branche")
    vision = scene_id == "sc_p0_visions"
    base = "#141b2b" if vision else "#302e31" if fire else "#202d3a"
    canvas.create_rectangle(0, 0, width, height, fill=base, outline="")
    if vision:
        canvas.create_oval(305, 4, 575, 240, outline="#9290ac", width=2)
        canvas.create_oval(370, 42, 510, 182, fill="#c9c2a0", outline="#e9c98a", width=3)
        canvas.create_polygon(395, 107, 403, 76, 425, 100, 439, 64, 455, 99,
                              475, 74, 486, 107, fill="#625445", outline="#ffe1a2")
        canvas.create_text(440, 175, text="LA COURONNE  •  LE BÛCHER  •  LA BANNIÈRE",
                           fill="#e3d8be", font=("TkDefaultFont", 11, "bold"))
    else:
        canvas.create_oval(650, 18, 736, 101, fill="#aaa58a" if not fire else "#c66d44",
                           outline="")
        canvas.create_polygon(0, 168, 130, 111, 230, 155, 339, 123, 451, 165,
                              589, 129, 720, 162, 860, 135, 860, 210, 0, 210,
                              fill="#283d37" if not fire else "#352b2b", outline="")
        if fire:
            for i, center in enumerate((230, 345, 453, 560, 660)):
                roof = 120 + (i % 3) * 12
                canvas.create_polygon(center - 45, roof + 16, center, roof - 22,
                                      center + 45, roof + 16, fill="#171b20", outline="#101318")
                canvas.create_rectangle(center - 37, roof + 16, center + 37, 209,
                                        fill="#252029", outline="#111416")
                flicker = 8 * sin(phase / 3 + i)
                canvas.create_polygon(center - 20, 190, center - 7, 148 - flicker,
                                      center + 3, 173, center + 19, 137 + flicker,
                                      center + 26, 190, fill="#e87c34", outline="")
                canvas.create_polygon(center - 10, 191, center + 5, 159 + flicker,
                                      center + 13, 191, fill="#ffd18c", outline="")
                for n in range(3):
                    shift = (phase * 4 + n * 19) % 50
                    canvas.create_oval(center - 16 + n * 4, 140 - shift,
                                       center + 33 + n * 4, 161 - shift,
                                       fill="#51474a", outline="")
        else:
            for x in (120, 230, 360, 540, 680):
                canvas.create_line(x, 155, x + 6, 119, fill="#bbad70", width=3)
                canvas.create_line(x + 19, 169, x + 25, 129, fill="#bbad70", width=3)
    return True
