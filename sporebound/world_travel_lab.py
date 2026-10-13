"""3.7.24F: side-effect-free journey simulation for World Map Studio.

Uses the *real* GameSession, StoryBook conditions and WorldJourney cursor.
Only a private in-memory progress record is modified. Author mode grants
the initially selected route nodes, not every possible fork.
"""
from copy import deepcopy

from .game_session import GameSession
from .model import require
from .world_travel import (AT, GOAL, PENDING, REVERSE, STEP, VIA,
                           _roads, _route)

TRAVEL_FLAGS = {AT, GOAL, VIA, STEP, REVERSE, PENDING}
MAX_STEPS_PER_RUN = 160 * 8


def campaign_delta(before, after):
    """Readable canonical campaign effects, excluding cursor bookkeeping."""
    result = []
    if before.gold != after.gold:
        result.append(f"Or : {before.gold} → {after.gold} ({after.gold - before.gold:+d})")
    for key in sorted(set(before.inventory) | set(after.inventory)):
        old, new = before.inventory.get(key, 0), after.inventory.get(key, 0)
        if old != new:
            result.append(f"Objet {key} : {old} → {new}")
    for key in sorted(set(before.story_flags) | set(after.story_flags)):
        if key in TRAVEL_FLAGS or key.startswith("world_evt_"):
            continue
        old, new = before.story_flags.get(key), after.story_flags.get(key)
        if old != new:
            result.append(f"Flag {key} : {old!r} → {new!r}")
    for mid in after.unlocked:
        if mid not in before.unlocked:
            result.append("Mission débloquée : " + mid)
    for mid in after.completed:
        if mid not in before.completed:
            result.append("Mission terminée : " + mid)
    for hid in sorted(set(after.heroes) - set(before.heroes)):
        result.append("Héros recruté : " + hid)
    for entry in after.story_history[len(before.story_history):]:
        result.append(f"Décision : {entry['scene']} / {entry['choice']}")
    return result


class WorldTravelLab:
    """Interactive, deterministic route preview with a hard step budget."""

    def __init__(self, content, project, campaign_id, start, destination, *,
                 author_mode=True, progress=None):
        self.session = GameSession.new(content, project, campaign_id)
        self.author_mode = bool(author_mode)
        self.start = start
        self.target = destination
        self.log = []
        world = self.session.project.world
        positions = {node["mission"] for node in world.get("nodes", [])}
        require(start in positions and destination in positions and
                start != destination, "Choisir deux lieux distincts sur la carte")
        if progress is not None:
            # The author may preview consequences from a real Studio Campaign
            # without ever altering that original Campaign.
            self.session.progress = deepcopy(progress)
            self.session.story.initialize(self.session.progress, campaign_id)
        working = self.session.progress
        if progress is None and working.story_pending:
            # Route preview starts after campaign introduction; this is a
            # sandbox-only skip, explicitly reported and never persisted.
            self.log.append("Introduction ignorée pour la simulation : "
                            + working.story_pending)
            working.story_pending = ""
        require(not working.story_pending and not working.story_flags.get(PENDING),
                "Résoudre les scènes narratives avant de simuler le voyage")
        if author_mode:
            roads = _roads(self.session.content, positions, positions)
            path = _route(roads, start, destination)
            require(bool(path), "Aucune route canonique entre ces deux lieux")
            for mid in path:
                if mid not in working.unlocked and mid not in working.completed:
                    working.unlocked.append(mid)
            self.log.append("Mode auteur : accès temporaire aux étapes de " +
                            " → ".join(path) + " (simulation seulement)")
        for key in (AT, GOAL, VIA, STEP, REVERSE, PENDING):
            working.story_flags.pop(key, None)
        working.story_flags[AT] = start
        self.baseline = deepcopy(working)
        self.session.world_destination(destination)
        self.log.append(f"Départ : {start} → {destination}")
        self._log_state()

    @property
    def progress(self):
        return self.session.progress

    def _log_state(self):
        state = self.session.world_state()
        return state

    def snapshot(self):
        """Read-only report for GUI; caller may mutate the returned value."""
        state = self.session.world_state()
        scene = self.session.active_scene()
        changes = campaign_delta(self.baseline, self.progress)
        return {
            "world": deepcopy(state),
            "scene": deepcopy(scene),
            "choices": self.session.available_choices() if scene else [],
            "changes": changes, "log": list(self.log),
            "gold": self.progress.gold,
            "mode": "auteur" if self.author_mode else "campagne",
            "finished": not state["traveling"] and scene is None,
        }

    def step(self):
        require(self.session.active_scene() is None,
                "Choisir la réponse à la rencontre avant de poursuivre")
        before = self.session.world_state()
        require(before["traveling"], "Voyage déjà terminé")
        after = self.session.world_advance()
        scene = self.session.active_scene()
        if scene is not None:
            self.log.append(f"Rencontre : {scene['title']} ({scene['id']}) "
                            f"à {after['at']} → {after['via']}, pas {after['step']}/8")
        elif after["at"] != before["at"]:
            self.log.append("Lieu atteint : " + after["at"])
        if not after["traveling"]:
            self.log.append("Trajet terminé à " + after["at"])
        return self.snapshot()

    def run_to_stop(self, max_steps=MAX_STEPS_PER_RUN):
        require(type(max_steps) is int and 1 <= max_steps <= MAX_STEPS_PER_RUN,
                "Limite de simulation invalide")
        for _ in range(max_steps):
            state = self.session.world_state()
            if self.session.active_scene() or not state["traveling"]:
                break
            self.step()
        else:
            self.log.append(f"Simulation suspendue à la limite de {max_steps} pas")
        return self.snapshot()

    def choose(self, choice_id):
        scene = self.session.active_scene()
        require(scene is not None, "Aucune décision en attente")
        permitted = {row["id"]: row for row in self.session.available_choices()}
        require(choice_id in permitted, "Choix indisponible")
        before = deepcopy(self.progress)
        self.session.choose_story_option(choice_id)
        self.log.append("Choix : " + permitted[choice_id]["label"])
        for change in campaign_delta(before, self.progress):
            self.log.append("  " + change)
        state = self.session.world_state()
        if state["reversing"]:
            self.log.append("Retour au carrefour avant direction : " + state["goal"])
        elif state["traveling"]:
            self.log.append("Reprise vers " + state["goal"])
        return self.snapshot()

    def destination(self, mission_id):
        state = self.session.world_state()
        require(not state["traveling"] and not self.session.active_scene(),
                "Terminer le segment en cours avant une nouvelle destination")
        self.session.world_destination(mission_id)
        self.log.append(f"Nouveau trajet : {state['at']} → {mission_id}")
        return self.snapshot()
