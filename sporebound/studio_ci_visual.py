"""Opt-in real Tk Studio screenshot evidence for GitHub pull requests.

Captures the *live application window* through the X11 compositor, including
native menus, docks and active tools. Never fakes UI from a rendered mockup.
Called only when DRAWTEMP_STUDIO_VISUAL_DIR is explicitly configured.
"""
from __future__ import annotations

from hashlib import sha256
from html import escape
import json
import os
from pathlib import Path


def capture_studio_review(*, root, canvas, notebook, work, sidebar_tabs,
                          scenery_page, studio_docks, mission_var, mission_id,
                          projection, fit_map, refresh, grid_var, start, stop,
                          battle_active, playtest_button, output):
    from PIL import ImageGrab, ImageStat

    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    root.geometry("1280x850+50+40")
    root.deiconify()
    root.update()
    notebook.select(work)
    sidebar_tabs.select(scenery_page)
    studio_docks.set_visible("explorer", True)
    studio_docks.set_visible("inspector", True)
    studio_docks.set_visible("bottom", True)
    mission_var.set(mission_id)
    root.update()
    frames = []

    def image_capture(name, projection_name, *, expected_playtest=False):
        root.update()
        window = (root.winfo_rootx(), root.winfo_rooty(),
                  root.winfo_width(), root.winfo_height())
        bounds = (canvas.winfo_rootx(), canvas.winfo_rooty(),
                  canvas.winfo_width(), canvas.winfo_height())
        assert window[2] >= 1024 and window[3] >= 720, ("small Studio", window)
        assert bounds[2] >= 250 and bounds[3] >= 180, ("clipped canvas", bounds)
        assert battle_active() == expected_playtest, "incorrect Playtest state"
        style = playtest_button.cget("style")
        assert style == (
            "Studio.Playtest.Stop.TButton" if expected_playtest
            else "Studio.Playtest.Start.TButton"), ("Playtest style", style)
        if projection_name == "2d":
            # Real textured tiles, not a flat mock Canvas: every village
            # terrain tile is drawn from the original RGBA atlas.
            assert len(canvas.find_withtag("topdown_autotile")) >= 150, (
                "2D atlas imagery missing", len(canvas.find_withtag("topdown_autotile")))
        if projection_name == "iso":
            assert not canvas.find_withtag("topdown_autotile"), "stale 2D renderer"
            assert len(canvas.find_all()) >= 100, "ISO scene not rendered"
        x, y, w, h = window
        screen = ImageGrab.grab(
            bbox=(x, y, x + w, y + h),
            xdisplay=os.environ.get("DISPLAY"),
        ).convert("RGB")
        cx, cy, cw, ch = bounds
        crop = screen.crop((cx - x, cy - y, cx - x + cw, cy - y + ch))
        contrast = ImageStat.Stat(crop.convert("L")).stddev[0]
        assert contrast > 8, (name, "blank / uniform map", contrast)
        filename = name + ".png"
        target = out / filename
        screen.save(target)
        frames.append({
            "name": name, "file": filename, "projection": projection_name,
            "playtest": expected_playtest, "window": list(window),
            "canvas": list(bounds), "canvas_items": len(canvas.find_all()),
            "image_sha256": sha256(target.read_bytes()).hexdigest(),
            "map_luma_stddev": round(contrast, 2),
            "playtest_button_style": style,
        })

    projection("2d")
    refresh()
    fit_map()
    image_capture("01-studio-2d-textures-autotiles", "2d")

    grid_var.set(True)
    refresh()
    image_capture("02-studio-2d-grid", "2d")
    grid_var.set(False)

    projection("iso")
    fit_map()
    image_capture("03-studio-iso", "iso")

    projection("2d")
    start()
    if not battle_active():
        raise AssertionError("Actual detached Playtest did not start")
    fit_map()
    image_capture("04-studio-playtest", "2d", expected_playtest=True)
    stop()

    manifest = {
        "schema": "drawtemp-studio-pr-visual-v1",
        "capture": "real Tk window via X11 ImageGrab",
        "mission": mission_id,
        "frames": frames,
        "human_approved": False,
        "reference_baseline": None,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    gallery = "\n".join(
        f'<article><h2>{escape(item["name"])}</h2>'
        f'<img alt="{escape(item["name"])}" src="{escape(item["file"])}"></article>'
        for item in frames)
    (out / "index.html").write_text(
        '<!doctype html><html lang="fr"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width">'
        '<title>DrawTemp – PR visual review</title>'
        '<style>body{font:16px system-ui;background:#eef1f5;color:#1d2837;'
        'margin:2rem auto;max-width:1600px;padding:0 1rem}'
        'main{display:grid;grid-template-columns:repeat(auto-fit,'
        'minmax(min(100%,620px),1fr));gap:1.2rem}'
        'article{background:white;border-radius:10px;padding:12px;'
        'box-shadow:0 2px 8px #0002}img{display:block;width:100%;height:auto}'
        '</style><h1>DrawTemp — captures réelles de la PR</h1>'
        '<p>Exécution Xvfb (Linux), revue graphique humaine requise. '
        'Les images sont des captures du Studio réel, pas des maquettes.</p>'
        '<main>' + gallery + '</main></html>\n',
        encoding="utf-8")
    print(f"Captured {len(frames)} Studio screenshots in {out}", flush=True)
    return manifest
