"""R11 Qt Quick cinematic stage shared by Player and Studio.

Headless rules/projection live elsewhere. Import this module only in a Qt app.
The stage does not apply campaign choices or tactical consequences.
"""
from pathlib import Path
import time

from PySide6.QtCore import QObject, Property, QTimer, QUrl, Signal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget, QVBoxLayout

from sporebound.audio_timeline import CinematicAudioDirector
from sporebound.cinematic_transport import CinematicTransport
from drawtemp.cinematics.projection import frame_payload


class FrameBridge(QObject):
    frameChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame = {}

    @Property("QVariantMap", notify=frameChanged)
    def frame(self):
        return self._frame

    def show_frame(self, payload):
        self._frame = payload
        self.frameChanged.emit()


class QtAudioStage:
    """Optional QtMultimedia implementation of the existing audio stage protocol.

    Missing bindings, codecs, devices or QtMultimedia do not stop cutscenes.
    Existing asset registry resolves all paths (including symlink protection).
    """
    def __init__(self, registry=None, asset_root=None):
        self.registry, self.asset_root = registry, asset_root
        self._tracks = {}
        self._cues = []
        try:
            from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
            self._media = (QMediaPlayer, QAudioOutput)
        except ImportError:
            self._media = None

    def _resolve(self, slot):
        if not self._media or self.registry is None or self.asset_root is None:
            return None
        try:
            from sporebound.model import RuleError
            spec = self.registry.binding("sound", slot)
            if spec is not None:
                return QUrl.fromLocalFile(
                    str(self.registry.resolve(spec["id"], self.asset_root)))
        except (RuleError, OSError, ValueError):
            pass
        return None

    def _player(self, slot, loop):
        uri = self._resolve(slot)
        if uri is None:
            return None
        player_class, output_class = self._media
        player, output = player_class(), output_class()
        player.setAudioOutput(output)
        player.setSource(uri)
        player.setLoops(player_class.Infinite if loop else 1)
        return player, output

    def music(self, slot):
        # Called by CinematicAudioDirector to stop a previous external score.
        pass

    def cue(self, slot):
        pair = self._player(slot, False)
        if pair is None:
            return False
        pair[1].setVolume(0.7)
        self._cues.append(pair)
        pair[0].play()
        return True

    def play_track(self, track_id, slot, *, bus="sfx", loop=False):
        if track_id in self._tracks:
            return True
        pair = self._player(slot, loop)
        if pair is None:
            return False
        self._tracks[track_id] = pair
        pair[0].play()
        return True

    def set_track_level(self, track_id, level):
        pair = self._tracks.get(track_id)
        if pair:
            pair[1].setVolume(max(0., min(1., float(level))))

    def stop_track(self, track_id):
        pair = self._tracks.pop(track_id, None)
        if pair:
            pair[0].stop()

    def pause_tracks(self):
        for player, _ in self._tracks.values():
            player.pause()
        for player, _ in self._cues:
            player.pause()

    def resume_tracks(self):
        for player, _ in self._tracks.values():
            player.play()
        for player, _ in self._cues:
            player.play()

    def stop_cues(self):
        # Transient one-shots must not outlive seek, skip or clip replacement.
        for player, _ in self._cues:
            player.stop()
        self._cues.clear()

    def close(self):
        for key in tuple(self._tracks):
            self.stop_track(key)
        self.stop_cues()


class CinematicStage(QWidget):
    """Identical Qt Quick component and source frame in Studio and Player.

    Editing is always a separate transaction; a playback tick only projects time.
    Playback speed modifies elapsed presentation time, not CT simulation.
    """
    positionChanged = Signal(int)
    finished = Signal()

    def __init__(self, clip, *, registry=None, asset_root=None,
                 auto_play=False, audio=None, parent=None):
        super().__init__(parent)
        self.clip = clip
        self.registry, self.asset_root = registry, asset_root
        self.bridge = FrameBridge(self)
        self._origin_real = time.monotonic()
        self._virtual_base = 0.0
        self._rate = 1.0
        self.transport = CinematicTransport(clip["duration_ms"],
                                             monotonic=self._virtual_now)
        self._owns_audio = audio is None
        self.audio = audio if audio is not None else QtAudioStage(registry, asset_root)
        self.director = CinematicAudioDirector(clip, self.audio)
        self._completed = False

        self.view = QQuickWidget(self)
        self.view.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.view.rootContext().setContextProperty("cinematic", self.bridge)
        qml = Path(__file__).resolve().parents[1] / "render" / "CinematicStage.qml"
        self.view.setSource(QUrl.fromLocalFile(str(qml)))
        if self.view.status() == QQuickWidget.Error:
            raise RuntimeError("; ".join(e.toString() for e in self.view.errors()))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self._tick)
        self._show(0)
        if auto_play:
            self.play()
        else:
            self.transport.pause()

    def _virtual_now(self):
        return self._virtual_base + (time.monotonic() - self._origin_real) * self._rate

    @property
    def time_ms(self):
        return self.transport.read()

    @property
    def playing(self):
        return self.transport.playing

    def set_speed(self, factor):
        if factor not in (.25, .5, 1.0, 1.5, 2.0):
            raise ValueError("Unsupported cinematic speed")
        self._virtual_base = self._virtual_now()
        self._origin_real = time.monotonic()
        self._rate = factor

    def _show(self, position):
        self.bridge.show_frame(frame_payload(
            self.clip, position, registry=self.registry, asset_root=self.asset_root))
        self.positionChanged.emit(position)

    def _tick(self):
        position = self.transport.read()
        self.director.advance(position)
        self._show(position)
        if position >= self.clip["duration_ms"]:
            self.pause()
            stop_cues = getattr(self.audio, "stop_cues", None)
            if stop_cues is not None:
                stop_cues()
            if not self._completed:
                self._completed = True
                self.finished.emit()

    def play(self):
        if self.transport.read() >= self.clip["duration_ms"]:
            self.seek(0)
        self.transport.resume()
        self.director.resume()
        self.timer.start()

    def pause(self):
        self.transport.pause()
        self.timer.stop()
        self.director.pause()
        self._show(self.transport.position_ms)

    def seek(self, position):
        was_playing = self.transport.playing
        target = self.transport.seek(int(position))
        stop_cues = getattr(self.audio, "stop_cues", None)
        if stop_cues is not None:
            stop_cues()
        self.director.seek(target)
        if not was_playing:
            # Seeking reconstructs sustained tracks, but must not make a
            # paused timeline audible until the user explicitly resumes.
            self.director.pause()
        self._show(target)
        if target < self.clip["duration_ms"]:
            self._completed = False

    def restart(self):
        self.seek(0)
        self.play()

    def checkpoint(self):
        return self.transport.checkpoint()

    def restore(self, checkpoint):
        self.pause()
        self.transport.restore(checkpoint)
        stop_cues = getattr(self.audio, "stop_cues", None)
        if stop_cues is not None:
            stop_cues()
        self.director.seek(self.transport.position_ms)
        if not checkpoint["playing"]:
            self.director.pause()
        self._show(self.transport.position_ms)
        self._completed = False
        if checkpoint["playing"]:
            self.play()

    def set_clip(self, clip):
        was_playing = self.transport.playing
        self.pause()
        self.director.stop()
        stop_cues = getattr(self.audio, "stop_cues", None)
        if stop_cues is not None:
            stop_cues()
        self.clip = clip
        self.transport = CinematicTransport(clip["duration_ms"],
                                             monotonic=self._virtual_now)
        self.director = CinematicAudioDirector(clip, self.audio)
        self._completed = False
        self._show(0)
        if was_playing:
            self.play()
        else:
            self.transport.pause()

    def closeEvent(self, event):
        self.timer.stop()
        self.director.stop()
        if self._owns_audio:
            self.audio.close()
        super().closeEvent(event)
