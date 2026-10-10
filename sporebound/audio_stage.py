"""Optional audio playback driven by engine events, never by game rules.

pygame-ce supplies WAV/OGG playback when installed. Missing audio, devices or
bindings leave a fully playable silent client.
"""
from pathlib import Path

from .model import RuleError


class AudioStage:
    def __init__(self, registry=None, asset_root=None, *, effects_volume=70, music_volume=70):
        self.registry = registry
        self.asset_root = Path(asset_root) if asset_root is not None else None
        self.effects_volume = effects_volume / 100
        self.music_volume = music_volume / 100
        self._mixer = None
        self._sounds = {}
        self._music = None
        self._seen = {}

    def _start(self):
        if self._mixer is None:
            try:
                from pygame import mixer
                if not mixer.get_init():
                    mixer.init()
                self._mixer = mixer
            except (ImportError, OSError, RuntimeError):
                return False
        return True

    def _path(self, slot):
        if self.registry is None or self.asset_root is None:
            return None
        spec = self.registry.binding("sound", slot)
        return self.registry.resolve(spec["id"], self.asset_root) if spec else None

    def cue(self, slot):
        try:
            path = self._path(slot)
            if path is None or not self._start():
                return False
            if str(path) not in self._sounds:
                self._sounds[str(path)] = self._mixer.Sound(str(path))
            sound = self._sounds[str(path)]
            sound.set_volume(self.effects_volume)
            sound.play()
            return True
        except (RuleError, OSError, RuntimeError, ValueError):
            return False

    def music(self, slot):
        if slot == self._music:
            return
        try:
            path = self._path(slot)
            if self._mixer is not None:
                self._mixer.music.stop()
            self._music = slot
            if path is not None and self._start():
                self._mixer.music.load(str(path))
                self._mixer.music.set_volume(self.music_volume)
                self._mixer.music.play(-1)
        except (RuleError, OSError, RuntimeError, ValueError):
            self._music = None

    def observe(self, battle):
        """Play only appended events for a stable battle id, not every redraw."""
        if battle is None:
            return
        identity = battle.battle_id
        count = len(battle.events)
        before = self._seen.get(identity, count)
        # First observation never replays preexisting events from disk.
        for event in battle.events[before:]:
            self.cue(event["kind"])
        self._seen[identity] = count

    def close(self):
        if self._mixer is not None:
            self._mixer.music.stop()
        self._sounds.clear()
