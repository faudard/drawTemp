"""Opt-in R11 Qt editor/player entry point; the legacy launcher is unchanged."""
import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp 5.0 — Qt Cinematic Studio")
    parser.add_argument("--content", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--mode", choices=("studio", "player"), default="studio")
    parser.add_argument("--clip", help="Stable cinematic ID to preview in Player")
    parser.add_argument("--smoke", action="store_true", help="Create a Qt window and exit")
    args = parser.parse_args(argv)
    if sys.version_info[:2] != (3, 12):
        parser.error("The 5.0 Qt 6 preview is qualified on Python 3.12 only")
    try:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import (QApplication, QLabel, QHBoxLayout, QMainWindow,
                                       QPushButton, QSlider, QVBoxLayout, QWidget)
    except ImportError as exc:
        parser.error('Install Qt with python -m pip install ".[qt6]": ' + str(exc))

    from sporebound.__main__ import DEFAULT_GAME_CONTENT
    from sporebound.model import Content
    from sporebound.game_project import GameProject
    from drawtemp.cinematics.document import CinematicDocument, jeanne_intro
    from drawtemp.player.qt_cinematic import CinematicStage
    from drawtemp.studio.qt_cinematic import CinematicEditor

    content_path = args.content or DEFAULT_GAME_CONTENT
    project_path = args.project or content_path.with_suffix(".game.json")
    content = Content.load(content_path)
    project = (GameProject.load(project_path, content) if project_path.is_file()
               else GameProject.default(content))
    app = QApplication.instance() or QApplication([sys.argv[0]])
    if args.mode == "studio":
        document = CinematicDocument(project, content, source_path=project_path)
        window = CinematicEditor(document)
    else:
        clips = [clip for clip in project.cinematics if args.clip in (None, clip["id"])]
        if args.clip and not clips:
            parser.error("Unknown cinematic ID: " + args.clip)
        clip = clips[0] if clips else jeanne_intro(project.campaigns[0]["id"])
        window = QMainWindow()
        window.setWindowTitle("DrawTemp 5.0 — Player / " + clip["name"])
        body = QWidget()
        layout = QVBoxLayout(body)
        stage = CinematicStage(clip, registry=project.asset_registry(),
                               asset_root=project_path.parent, auto_play=True)
        layout.addWidget(stage)
        controls = QHBoxLayout()
        button = QPushButton("Pause")
        def toggle():
            if stage.playing:
                stage.pause()
                button.setText("Lire")
            else:
                stage.play()
                button.setText("Pause")
        button.clicked.connect(toggle)
        controls.addWidget(button)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(0, clip["duration_ms"])
        slider.sliderMoved.connect(stage.seek)
        stage.positionChanged.connect(slider.setValue)
        controls.addWidget(slider)
        restart = QPushButton("Recommencer")
        restart.clicked.connect(stage.restart)
        controls.addWidget(restart)
        stage.finished.connect(lambda: button.setText("Lire"))
        layout.addLayout(controls)
        window.setCentralWidget(body)
        window.resize(1040, 680)

    window.show()
    if args.smoke:
        QTimer.singleShot(300, app.quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
