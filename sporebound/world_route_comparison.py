"""3.7.24G — Compare alternative world journeys from one identical checkpoint.

The lab's GameSession/StoryBook remain the only authority for travel and
consequences. Every scenario is a deep-copied sandbox; nothing is persisted.
"""
from copy import deepcopy

from .model import RuleError, require
from .world_travel_lab import TRAVEL_FLAGS, WorldTravelLab

MAX_COMPARISON_PATHS = 8


def _public_flags(progress):
    return {key: value for key, value in progress.story_flags.items()
            if key not in TRAVEL_FLAGS and not key.startswith("world_evt_")}


def _format_value(value):
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    return str(value)


class WorldRouteComparison:
    """Immutable source fork, bounded isolated branches and result matrix."""

    def __init__(self, lab):
        require(isinstance(lab, WorldTravelLab),
                "Le comparateur demande un simulateur de voyage")
        scene = lab.session.active_scene()
        require(scene is not None and bool(lab.session.available_choices()),
                "Marquer un embranchement pendant une rencontre")
        self.checkpoint = deepcopy(lab)
        self.origin = lab.session.recording()["digest"]
        self.scene_id = scene["id"]
        self.variants = {}
        self.failures = []

    def fork(self):
        """Return an independent, checkpoint-identical simulation branch."""
        clone = deepcopy(self.checkpoint)
        clone._comparison_origin = self.origin
        return clone

    def record(self, name, lab):
        require(isinstance(name, str) and bool(name.strip())
                and len(name.strip()) <= 70,
                "Nom de parcours attendu (1 à 70 caractères)")
        name = name.strip()
        require(name not in self.variants, "Nom de parcours déjà enregistré")
        require(len(self.variants) < MAX_COMPARISON_PATHS,
                "Au maximum huit parcours comparables")
        require(isinstance(lab, WorldTravelLab) and
                getattr(lab, "_comparison_origin", None) == self.origin,
                "Ce parcours ne provient pas de l'embranchement commun")
        require(lab.session.campaign_id == self.checkpoint.session.campaign_id,
                "Campagne différente de l'embranchement")
        # Capture an immutable snapshot; subsequent changes to the working
        # lab must not rewrite already recorded scenario outcomes.
        self.variants[name] = deepcopy(lab)
        return self.matrix()

    def checkout(self, name):
        require(name in self.variants, "Parcours enregistré introuvable")
        return deepcopy(self.variants[name])

    def compare_choices(self):
        """Try each currently available choice up to the bounded path budget.

        Each choice is executed by the normal StoryBook/GameSession, followed
        by a deterministic run to the next encounter or destination. Rejected
        options remain visible as failures, but never affect other branches.
        """
        self.failures = []
        added = []
        for index, choice in enumerate(self.checkpoint.session.available_choices()):
            if len(self.variants) >= MAX_COMPARISON_PATHS:
                break
            name = str(index + 1) + ". " + choice["label"][:58]
            if name in self.variants:
                continue
            candidate = self.fork()
            try:
                candidate.choose(choice["id"])
                candidate.run_to_stop()
                self.record(name, candidate)
                added.append(name)
            except RuleError as exc:
                self.failures.append({"choice": choice["id"], "reason": str(exc)})
        return {"added": added, "failures": deepcopy(self.failures),
                "matrix": self.matrix()}

    def matrix(self):
        """Aligned values from one shared baseline, not independent runs."""
        checkpoint = self.checkpoint.progress
        names = list(self.variants)
        outcomes = [self.variants[name] for name in names]
        flags = sorted(set(_public_flags(checkpoint)).union(
            *(_public_flags(lab.progress) for lab in outcomes)))
        inventory = sorted(set(checkpoint.inventory).union(
            *(lab.progress.inventory for lab in outcomes)))
        unlocked = sorted(set(checkpoint.unlocked).union(
            *(lab.progress.unlocked for lab in outcomes)))
        completed = sorted(set(checkpoint.completed).union(
            *(lab.progress.completed for lab in outcomes)))
        def row(name, getter):
            return {"metric": name, "values": [getter(lab) for lab in outcomes]}
        rows = [
            row("Lieu", lambda lab: lab.session.world_state()["at"]),
            row("Destination", lambda lab: lab.session.world_state()["goal"] or "—"),
            row("Situation", lambda lab: (
                "Dialogue : " + lab.session.active_scene()["id"]
                if lab.session.active_scene() else
                "En route" if lab.session.world_state()["traveling"] else "Arrivé")),
            row("Or / variation", lambda lab: (
                f"{lab.progress.gold} ({lab.progress.gold - checkpoint.gold:+d})")),
            row("Choix depuis embranchement", lambda lab: " → ".join(
                entry["choice"] for entry in lab.progress.story_history[
                    len(checkpoint.story_history):]) or "—"),
            row("Rencontres déclenchées", lambda lab: str(sum(
                key.startswith("world_evt_") and value is True and
                checkpoint.story_flags.get(key) is not True
                for key, value in lab.progress.story_flags.items()))),
            row("Nouvelles missions", lambda lab: ", ".join(
                mid for mid in lab.progress.unlocked
                if mid not in checkpoint.unlocked) or "—"),
        ]
        for key in flags:
            before = _public_flags(checkpoint).get(key)
            if any(_public_flags(lab.progress).get(key) != before for lab in outcomes):
                rows.append(row("Flag : " + key, lambda lab, key=key:
                                _format_value(_public_flags(lab.progress).get(key))))
        for key in inventory:
            before = checkpoint.inventory.get(key, 0)
            if any(lab.progress.inventory.get(key, 0) != before for lab in outcomes):
                rows.append(row("Objet : " + key, lambda lab, key=key:
                                str(lab.progress.inventory.get(key, 0))))
        for key in unlocked:
            if any((key in lab.progress.unlocked) != (key in checkpoint.unlocked)
                   for lab in outcomes):
                rows.append(row("Accessible : " + key, lambda lab, key=key:
                                "oui" if key in lab.progress.unlocked else "non"))
        for key in completed:
            if any((key in lab.progress.completed) != (key in checkpoint.completed)
                   for lab in outcomes):
                rows.append(row("Terminée : " + key, lambda lab, key=key:
                                "oui" if key in lab.progress.completed else "non"))
        return {"scene": self.scene_id, "names": names, "rows": rows,
                "failures": deepcopy(self.failures)}

    def detail(self, name):
        """Read-only branch audit trail and consequences for a selected path."""
        require(name in self.variants, "Parcours enregistré introuvable")
        lab = self.variants[name]
        return {
            "name": name,
            "log": list(lab.log[len(self.checkpoint.log):]),
            "changes": lab.snapshot()["changes"],
            "state": deepcopy(lab.session.world_state()),
        }
