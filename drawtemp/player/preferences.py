"""R12.8/R12.9 independent, versioned Qt Player input and UI preferences.

This file is intentionally headless. Preferences are never persisted in
GameSession checkpoints, avoiding rule/replay and save-format changes.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import tempfile


class PreferenceError(ValueError):
    """Invalid profile, keybinding, or preferences document."""


# Stable action IDs shared by the Qt interface and the headless tests.
ACTION_ROWS = (
    ("save", "Sauvegarder", "global"),
    ("pause", "Pause / menu", "global"),
    ("explore_up", "Explorer : haut", "exploration"),
    ("explore_down", "Explorer : bas", "exploration"),
    ("explore_left", "Explorer : gauche", "exploration"),
    ("explore_right", "Explorer : droite", "exploration"),
    ("battle_up", "Cible : haut", "battle"),
    ("battle_down", "Cible : bas", "battle"),
    ("battle_left", "Cible : gauche", "battle"),
    ("battle_right", "Cible : droite", "battle"),
    ("battle_move", "Déplacer", "battle"),
    ("battle_attack", "Attaquer", "battle"),
    ("battle_end", "Terminer le tour", "battle"),
)
CONTEXT = {action: context for action, _, context in ACTION_ROWS}
LABELS = {action: label for action, label, _ in ACTION_ROWS}
PROFILES = ("azerty", "qwerty")
ARROWS = {
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
}
KEY_CHOICES = (
    "Up", "Down", "Left", "Right", "Z", "Q", "S", "D", "W", "A",
    "E", "R", "F", "M", "C", "X", "I", "J", "K", "L",
    "Space", "Return", "Escape", "F5", "F6", "F7", "F8",
    "Ctrl+S", "Ctrl+L", "Ctrl+M",
)
DEFAULT_DISPLAY = {
    "text_scale": 1.0,
    "high_contrast": False,
    "show_grid": True,
    "show_heights": False,
    "fullscreen": False,
}
DEFAULT_BINDINGS = {
    "save": "F5", "pause": "Escape",
    "explore_up": "Z", "explore_down": "S",
    "explore_left": "Q", "explore_right": "D",
    "battle_up": "Up", "battle_down": "Down",
    "battle_left": "Left", "battle_right": "Right",
    "battle_move": "M", "battle_attack": "A", "battle_end": "Space",
}


def initial_settings():
    azerty = dict(DEFAULT_BINDINGS)
    qwerty = dict(DEFAULT_BINDINGS, explore_up="W", explore_left="A")
    return {
        "version": 1, "active_profile": "azerty",
        "profiles": {"azerty": azerty, "qwerty": qwerty},
        "display": deepcopy(DEFAULT_DISPLAY),
    }


def _validate_bindings(bindings):
    if type(bindings) is not dict or set(bindings) != set(CONTEXT):
        raise PreferenceError("L'ensemble des commandes est requis")
    for action, key in bindings.items():
        if type(key) is not str or key not in KEY_CHOICES:
            raise PreferenceError("Touche non prise en charge : " + str(key))
        if key in ARROWS and action.endswith(("_up", "_down", "_left", "_right")):
            if action.rsplit("_", 1)[-1] != ARROWS[key]:
                raise PreferenceError("Les flèches gardent leur direction")
        elif key in ARROWS:
            raise PreferenceError("Flèche réservée aux déplacements")
    for context in ("exploration", "battle"):
        keys = [key for action, key in bindings.items() if CONTEXT[action] in ("global", context)]
        if len(keys) != len(set(keys)):
            raise PreferenceError("Raccourci déjà utilisé dans ce contexte")


def validate(settings):
    if type(settings) is not dict or set(settings) != {
        "version", "active_profile", "profiles", "display"
    } or type(settings["version"]) is not int or settings["version"] != 1:
        raise PreferenceError("Version de préférences incompatible (attendu : 1)")
    if settings["active_profile"] not in PROFILES:
        raise PreferenceError("Profil clavier inconnu")
    if type(settings["profiles"]) is not dict or set(settings["profiles"]) != set(PROFILES):
        raise PreferenceError("Profils clavier manquants")
    for profile in PROFILES:
        _validate_bindings(settings["profiles"][profile])
    display = settings["display"]
    if type(display) is not dict or set(display) != set(DEFAULT_DISPLAY):
        raise PreferenceError("Options graphiques incomplètes")
    for key in ("high_contrast", "show_grid", "show_heights", "fullscreen"):
        if type(display[key]) is not bool:
            raise PreferenceError(key + " doit être un booléen")
    scale = display["text_scale"]
    if type(scale) not in (int, float) or not 0.85 <= scale <= 1.35:
        raise PreferenceError("Taille des textes hors limites")


class PlayerPreferences:
    """Atomic and detached preference store, scoped to the Player save directory."""

    def __init__(self, path):
        self.path = Path(path)
        self._data = initial_settings()
        self.warning = ""
        self._invalid = False
        if self.path.exists():
            try:
                if self.path.stat().st_size > 65536:
                    raise PreferenceError("Fichier de préférences trop volumineux")
                data = json.loads(self.path.read_text(encoding="utf-8"))
                validate(data)
            except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
                self.warning = "Préférences invalides : réglages par défaut chargés (" + str(exc) + ")"
                self._invalid = True
            else:
                self._data = data

    def view(self):
        data = deepcopy(self._data)
        profile = data["active_profile"]
        return {
            "profile": profile, "profiles": list(PROFILES),
            "bindings": data["profiles"][profile],
            "rows": [
                {"action": action, "label": label, "context": context,
                 "key": data["profiles"][profile][action]}
                for action, label, context in ACTION_ROWS
            ],
            "keyChoices": list(KEY_CHOICES),
            "display": data["display"],
        }

    def binding(self, action):
        if action not in CONTEXT:
            raise PreferenceError("Commande inconnue")
        return self._data["profiles"][self._data["active_profile"]][action]

    def resolve(self, key, context):
        """Translate a portable Qt key sequence without changing game state."""
        if context not in ("exploration", "battle", "dialogue", "campaign", "result", "title"):
            return ""
        if not isinstance(key, str):
            return ""
        if key == "Esc":
            key = "Escape"
        if key == "Enter":
            key = "Return"
        bindings = self._data["profiles"][self._data["active_profile"]]
        for action in ("save", "pause"):
            if key == bindings[action]:
                return action
        if context not in ("exploration", "battle"):
            return ""
        for action, selected in bindings.items():
            if CONTEXT[action] == context and selected == key:
                return action
        # Arrow keys stay accessible for spatial navigation even on AZERTY
        # and QWERTY. They cannot be stolen by another action.
        if key in ARROWS:
            return ("explore_" if context == "exploration" else "battle_") + ARROWS[key]
        return ""

    def profile(self, profile):
        if profile not in PROFILES:
            raise PreferenceError("Profil clavier inconnu")
        data = deepcopy(self._data)
        data["active_profile"] = profile
        self._commit(data)

    def rebind(self, action, key):
        if action not in CONTEXT:
            raise PreferenceError("Commande inconnue")
        if type(key) is not str:
            raise PreferenceError("Touche non reconnue")
        data = deepcopy(self._data)
        data["profiles"][data["active_profile"]][action] = key
        self._commit(data)

    def reset(self):
        data = deepcopy(self._data)
        profile = data["active_profile"]
        data["profiles"][profile] = initial_settings()["profiles"][profile]
        self._commit(data)

    def set_display(self, name, value):
        if name not in DEFAULT_DISPLAY:
            raise PreferenceError("Option inconnue")
        data = deepcopy(self._data)
        data["display"][name] = value
        self._commit(data)

    def _commit(self, candidate):
        validate(candidate)
        self._persist(candidate)
        self._data = candidate
        self.warning = ""
        self._invalid = False

    def _persist(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self._invalid and self.path.exists():
            # Preserve the original corrupt/incompatible file for diagnosis.
            backup = self.path.with_name(self.path.name + ".invalid")
            if backup.exists():
                raise PreferenceError("Une sauvegarde .invalid existe déjà")
            with backup.open("xb") as stream:
                stream.write(self.path.read_bytes())
        filename = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=self.path.parent,
                                             prefix=".player-preferences-",
                                             suffix=".tmp", delete=False,
                                             encoding="utf-8") as stream:
                filename = stream.name
                json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(filename, self.path)
        finally:
            if filename is not None:
                Path(filename).unlink(missing_ok=True)
