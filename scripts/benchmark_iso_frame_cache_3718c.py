"""Measure live Tk ISO frame cost on authored 32/64/128-square boards.

Example:
  xvfb-run -a python3 scripts/benchmark_iso_frame_cache_3718c.py --frames 5

Printed timings are environment-specific observations, never game budgets.
Includes two modes: full scene repaint (fresh immutable frame each sample),
and identical-frame MotionDirector pose updates with static layers cached.
"""
import argparse
from dataclasses import replace
from statistics import median
from time import perf_counter

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.authoring import add_blank_mission
from sporebound.engine import Battle
from sporebound.iso_battle_view import IsoBattleCanvas
from sporebound.model import Content
from sporebound.presentation import Camera, battle_frame
from sporebound.visual_motion import ActorPose


def percentile(values, q):
    values = sorted(values)
    return values[min(len(values)-1, int((len(values)-1)*q+.5))]


def measure(size, frames):
    import tkinter as tk
    root = tk.Tk()
    try:
        root.geometry('800x540')
        canvas = tk.Canvas(root, width=780, height=480)
        canvas.pack()
        root.update()
        content = Content.from_dict(add_blank_mission(
            Content.load(DEFAULT_CONTENT).to_dict(),
            'iso_benchmark', 'Performance ISO', size, size))
        battle = Battle(content, 'iso_benchmark', seed=10)
        frame = battle_frame(battle, (1, 1))
        camera = Camera(48, 0, 0)
        renderer = IsoBattleCanvas(canvas)
        # Measure vector geometry without disk/PNG or OS-dependent image scaling.
        for atlas in (renderer.terrain, renderer.props, renderer.buildings,
                      renderer.fortifications):
            atlas._unavailable = True
        renderer.draw(battle, frame, camera)
        actor = battle.units[0]
        x, y = actor.pos
        full, cached = [], []
        for i in range(frames):
            pose = {actor.id: ActorPose(x+(.02*i), y, 'move', 'east')}
            start = perf_counter()
            renderer.draw(battle, replace(frame), camera, poses=pose)
            full.append((perf_counter()-start)*1000)
        renderer.draw(battle, frame, camera)
        for i in range(frames):
            pose = {actor.id: ActorPose(x+(.02*i), y, 'move', 'east')}
            start = perf_counter()
            renderer.draw(battle, frame, camera, poses=pose)
            cached.append((perf_counter()-start)*1000)
        return {'size': size, 'frames': frames,
                'full_p50_ms': round(median(full), 3),
                'full_p95_ms': round(percentile(full, .95), 3),
                'cached_p50_ms': round(median(cached), 3),
                'cached_p95_ms': round(percentile(cached, .95), 3),
                'rebuilds': renderer._scene_rebuilds,
                'actor_only': renderer._actor_only_frames}
    finally:
        root.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sizes', default='32,64,128')
    parser.add_argument('--frames', type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.frames <= 100:
        parser.error('--frames must be 1..100')
    for size in (int(s.strip()) for s in args.sizes.split(',')):
        if size not in (32, 64, 128):
            parser.error('supported board sizes are 32,64,128')
        print(measure(size, args.frames), flush=True)


if __name__ == '__main__':
    main()
