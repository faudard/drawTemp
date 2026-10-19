"""Inspect R20.C Jeanne clips in the shared Qt Quick cinematic stage.

Playback, seek and skip are pure presentation. Nothing writes to GameSession
or player slots. --list and --sample work without PySide6.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sporebound.cinematics import frame_at
from sporebound.game_project import GameProject
from sporebound.model import Content

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "sporebound/content/jeanne.json"
PROJECT = ROOT / "sporebound/content/jeanne.r20c.game.json"


def load_clips():
    content = Content.load(CONTENT)
    project = GameProject.load(PROJECT, content)
    return project, {clip["id"]: clip for clip in project.cinematics}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="List validated authored cinematic IDs (headless)")
    parser.add_argument("--sample", type=int, metavar="MILLISECONDS",
                        help="Sample a clip at a given time without Qt")
    parser.add_argument("--clip", help="Optional cinematic ID (default: first clip)")
    args = parser.parse_args(argv)
    project, clips = load_clips()
    if not clips:
        parser.error("No cinematic clips")
    if args.clip is not None and args.clip not in clips:
        parser.error("Unknown cinematic ID: " + args.clip)
    if args.list:
        for clip in clips.values():
            print(f"{clip['id']}  [{clip['trigger']['kind']}:{clip['trigger']['target']}]"
                  f"  {clip['duration_ms']}ms")
        return 0
    selected = clips[args.clip] if args.clip else next(iter(clips.values()))
    if args.sample is not None:
        from dataclasses import asdict
        print(json.dumps(asdict(frame_at(selected, args.sample)),
                         ensure_ascii=False, indent=2))
        return 0

    try:
        from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                                       QHBoxLayout, QPushButton, QComboBox,
                                       QLabel)
        from drawtemp.player.qt_cinematic import CinematicStage
    except ImportError as exc:
        parser.error("Install the Qt6 extra to preview cinematics: " + str(exc))

    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.setWindowTitle("DrawTemp · Jeanne Acte I · R20.C Cinematic Preview")
    window.resize(1050, 730)
    layout = QVBoxLayout(window)
    note = QLabel("Prévisualisation uniquement : passer/chercher n'avance jamais la campagne.")
    note.setWordWrap(True)
    layout.addWidget(note)
    select = QComboBox()
    for clip in clips.values():
        select.addItem(clip["name"], clip["id"])
    layout.addWidget(select)
    stage = CinematicStage(selected, registry=project.asset_registry(),
                           asset_root=PROJECT.parent, auto_play=False)
    layout.addWidget(stage, 1)
    controls = QHBoxLayout()
    layout.addLayout(controls)

    play = QPushButton("Lire")
    pause = QPushButton("Pause")
    restart = QPushButton("Recommencer")
    skip = QPushButton("Passer la cinématique")
    for button in (play, pause, restart, skip):
        controls.addWidget(button)
    play.clicked.connect(stage.play)
    pause.clicked.connect(stage.pause)
    restart.clicked.connect(stage.restart)

    def change_clip(index):
        stage.set_clip(clips[select.itemData(index)])
    def skip_clip():
        stage.seek(stage.clip["duration_ms"])
        stage.pause()
    select.currentIndexChanged.connect(change_clip)
    skip.clicked.connect(skip_clip)
    select.setCurrentIndex(list(clips).index(selected["id"]))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
