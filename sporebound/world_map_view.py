"""Shared isometric-inspired parchment world-map renderer (Studio + Player).

Rendering and hit testing only. World coordinates are presentation pixels and
never replace tactical tile coordinates or the Mission.next_missions graph.
"""
from .world_map import world_hit_test

THEMES = {
    "parchment": ("#efe2c4", "#d3bea1", "#826b4b", "#735945", "#c7d3b1"),
    "kingdom": ("#dce9dd", "#bdd3ba", "#486b57", "#3a5b48", "#b3c7dd"),
    "forest": ("#d9e4cd", "#b6caaa", "#44654b", "#355741", "#b8d3ca"),
    "winter": ("#e5eaf1", "#cad9e6", "#58718e", "#47637d", "#b9d2e5"),
}
STATUS_COLORS = {
    "locked": ("#9d9e9c", "#e8e8e4"),
    "available": ("#34856d", "#f6efcf"),
    "completed": ("#537eb0", "#e4f3ff"),
}


def draw_world_map(canvas, projection, *, selected=""):
    """Paint deterministic background, actual campaign links and map nodes."""
    width, height = projection["width"], projection["height"]
    bg, terrain, ink, outline, water = THEMES[projection["theme"]]
    canvas.delete("all")
    canvas.configure(background=bg, scrollregion=(0, 0, width, height))
    canvas.create_rectangle(7, 7, width-7, height-7,
                            outline=outline, width=3, tags=("world_background",))
    # Geographical texture is explicitly decorative; it does not define
    # traversable roads or add implicit narrative edges.
    for x in range(70, width, 95):
        canvas.create_line(x, 16, x, height-16, fill=terrain,
                           dash=(3, 12), tags=("world_background",))
    for y in range(62, height, 95):
        canvas.create_line(16, y, width-16, y, fill=terrain,
                           dash=(3, 12), tags=("world_background",))
    canvas.create_oval(width-150, 25, width-42, 133,
                       fill=water, outline=outline, width=2,
                       tags=("world_background",))
    canvas.create_line(width-96, 43, width-96, 115,
                       fill=outline, width=2, tags=("world_background",))
    canvas.create_line(width-132, 79, width-60, 79,
                       fill=outline, width=2, tags=("world_background",))
    canvas.create_text(40, 28, text="LE MONDE", anchor="nw",
                       font=("TkDefaultFont", 16, "bold"), fill=ink,
                       tags=("world_background",))
    positions = {n["mission"]: n for n in projection["nodes"]}
    for source, target in projection["edges"]:
        x1, y1 = positions[source]["x"], positions[source]["y"]
        x2, y2 = positions[target]["x"], positions[target]["y"]
        canvas.create_line(x1, y1, x2, y2, fill=outline, width=3,
                           arrow="last", dash=(7, 4),
                           tags=("world_route",))
    for node in projection["nodes"]:
        mid = node["mission"]
        x, y = node["x"], node["y"]
        primary, text = STATUS_COLORS[node["status"]]
        is_selected = mid == selected
        border = "#e0a54b" if is_selected else outline
        canvas.create_oval(x-24, y-24, x+24, y+24,
                           fill=primary, outline=border,
                           width=5 if is_selected else 2,
                           tags=("world_node", "world_node_" + mid))
        symbol = ("✓" if node["status"] == "completed" else
                  "●" if node["status"] == "available" else "×")
        canvas.create_text(x, y-1, text=symbol,
                           fill=text, font=("TkDefaultFont", 17, "bold"),
                           tags=("world_node", "world_node_" + mid))
        canvas.create_text(x, y+35, text=node["label"][:28],
                           fill=ink, font=("TkDefaultFont", 10, "bold"),
                           tags=("world_label", "world_node_" + mid))
        if node["region"]:
            canvas.create_text(x, y+51, text=node["region"][:28],
                               fill=outline, font=("TkDefaultFont", 9),
                               tags=("world_label", "world_node_" + mid))
    return len(projection["nodes"])


def pick_world_mission(canvas, projection, event):
    return world_hit_test(
        projection, (canvas.canvasx(event.x), canvas.canvasy(event.y)))
