"""R75.A assisted narrative proposals: deterministic, detached, explicitly approved.

Uses GameProject.story, StoryBook and R1 AuthoringSession; never a second
source of truth or an implicit write. No network service or executable content.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from drawtemp.sdk.authoring import AuthoringPlan, AuthoringSession
from sporebound.campaign import Campaign
from sporebound.model import Content, RuleError
from sporebound.narrative import StoryBook, _id
from sporebound.game_project import GameProject
from sporebound.tactical_rpg3 import authored_rules_for_document

SCHEMA_VERSION = 1
MAX_SCENES = 64
MAX_PATH_STATES = 1024
MAX_PATH_DEPTH = 64


class NarrativeAssistError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def reject(code, message):
    raise NarrativeAssistError(code, message)


def _safe_id(value, name):
    try:
        _id(value, name)
    except RuleError as exc:
        reject("invalid_id", str(exc))


def validate_proposal(raw):
    """Strict, versioned review contract; canonical validation happens later."""
    if not isinstance(raw, dict) or set(raw) != {
            "version", "id", "source", "hook", "entry_scene", "scenes", "endings"}:
        reject("invalid_proposal", "Unexpected fields or missing proposal fields")
    if type(raw["version"]) is not int or raw["version"] != SCHEMA_VERSION:
        reject("invalid_version", "Unsupported R75 proposal version")
    _safe_id(raw["id"], "Proposal id")
    _safe_id(raw["entry_scene"], "Entry scene")
    source = raw["source"]
    if not isinstance(source, dict) or set(source) != {
            "kind", "attribution", "license", "rights", "redistribution_allowed"}:
        reject("invalid_rights", "Provenance and rights declaration required")
    if (source["kind"] not in ("manual", "offline_template", "imported") or
            source["rights"] not in ("original", "licensed") or
            type(source["redistribution_allowed"]) is not bool or
            not source["redistribution_allowed"] or
            any(not isinstance(source[field], str) or
                not 0 < len(source[field].strip()) <= 240
                for field in ("attribution", "license"))):
        reject("invalid_rights", "Explicit redistribution permission required")
    hook = raw["hook"]
    if not isinstance(hook, dict) or set(hook) != {"kind", "id"} or (
            hook["kind"] not in ("entry_scenes", "after_mission")):
        reject("invalid_hook", "Only campaign and mission hooks are supported")
    _safe_id(hook["id"], "Hook id")
    scenes = raw["scenes"]
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= MAX_SCENES:
        reject("scene_budget", "Expected 1..64 scenes")
    if any(not isinstance(s, dict) or not isinstance(s.get("id"), str)
           for s in scenes):
        reject("invalid_scene", "Each scene needs an id")
    ids = [scene["id"] for scene in scenes]
    if len(ids) != len(set(ids)) or raw["entry_scene"] not in ids:
        reject("invalid_scene", "Duplicate ids or missing entry")
    endings = raw["endings"]
    if (not isinstance(endings, list) or not 1 <= len(endings) <= 12 or
            any(not isinstance(e, str) for e in endings) or
            len(endings) != len(set(endings)) or not set(endings) <= set(ids)):
        reject("invalid_endings", "Expected distinct, declared terminal scenes")
    for scene in scenes:
        if set(scene) != {"id", "title", "speaker", "text", "choices"}:
            reject("invalid_scene", "Noncanonical scene fields")
        if not isinstance(scene["choices"], list):
            reject("invalid_choice", "Expected a list of choices")
        for choice in scene["choices"]:
            if not isinstance(choice, dict) or not {"id", "label"} <= set(choice) <= {
                    "id", "label", "when", "next_scene", "effects"}:
                reject("invalid_choice", "Noncanonical choice fields")
            if "next_scene" in choice and choice["next_scene"] not in ids:
                reject("external_link", "Proposal cannot link to or edit other narratives")
            effects = choice.get("effects", [])
            if not isinstance(effects, list) or any(
                    not isinstance(effect, dict) or
                    effect.get("kind") not in ("set_flag", "add_flag")
                    for effect in effects):
                reject("unsafe_effect", "Only declarative flag effects are supported")
    return deepcopy(raw)


def _candidate(project, proposal):
    project = deepcopy(project)
    hook = proposal["hook"]
    if hook["kind"] == "entry_scenes" and hook["id"] not in {
            campaign["id"] for campaign in project["campaigns"]}:
        reject("unknown_hook", "Unknown campaign")
    story = project.setdefault("story", {})
    existing = {scene["id"] for scene in story.get("scenes", [])}
    if existing & {scene["id"] for scene in proposal["scenes"]}:
        reject("scene_conflict", "Scene id already used")
    mapping = story.setdefault(hook["kind"], {})
    if hook["id"] in mapping:
        reject("hook_conflict", "Refusing to overwrite an existing story link")
    mapping[hook["id"]] = proposal["entry_scene"]
    story.setdefault("scenes", []).extend(deepcopy(proposal["scenes"]))
    return project


def _coverage(story, content, campaigns, proposal):
    """Bounded exhaustive paths from a clean, isolated Campaign state.

    External mission completion, gold and arbitrary prior flags are not
    explored. This is a concrete witness check, not all-save certification.
    """
    book = StoryBook(story, content, campaigns)
    state = Campaign(unlocked=[])
    state.story_started = True
    state.story_digest = book.digest
    state.story_pending = proposal["entry_scene"]
    scenes = {scene["id"]: scene for scene in proposal["scenes"]}
    visited_scenes, visited_choices, endings = set(), set(), {}
    count = 0

    def explore(progress, trace):
        nonlocal count
        count += 1
        if count > MAX_PATH_STATES or len(trace) > MAX_PATH_DEPTH:
            reject("coverage_budget", "Path count/depth exceeded the audit budget")
        scene = book.active_scene(progress)
        if scene is None or scene["id"] not in scenes:
            reject("invalid_path", "Path escaped reviewed scenes")
        visited_scenes.add(scene["id"])
        for choice in book.choices(progress):
            visited_choices.add((scene["id"], choice["id"]))
            steps = trace + ((scene["id"], choice["id"]),)
            try:
                after = book.choose(progress, choice["id"])
            except RuleError as exc:
                reject("unplayable_choice", str(exc))
            if after.story_pending:
                explore(after, steps)
            else:
                endings.setdefault(scene["id"], steps)

    explore(state, ())
    remaining = set(scenes) - visited_scenes
    if remaining:
        reject("unreachable_scene", "Unreachable scenes: " + ", ".join(sorted(remaining)))
    all_choices = {(s["id"], c["id"]) for s in proposal["scenes"]
                   for c in s["choices"]}
    if all_choices - visited_choices:
        reject("unreachable_choice", "Unreachable choices in reviewed graph")
    if set(endings) != set(proposal["endings"]):
        reject("unreachable_ending", "Actual endings differ from declared endings")
    return tuple((end, endings[end]) for end in sorted(endings))


@dataclass(frozen=True)
class NarrativeReview:
    proposal_id: str
    revision: int
    proposal_sha256: str
    source: dict
    hook: dict
    added_scenes: tuple[str, ...]
    ending_paths: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    approval_required: bool = True
    gameplay_certified: bool = False

    def to_dict(self):
        return {
            "proposal_id": self.proposal_id, "revision": self.revision,
            "proposal_sha256": self.proposal_sha256,
            "source": deepcopy(self.source), "hook": deepcopy(self.hook),
            "added_scenes": list(self.added_scenes),
            "ending_paths": [
                {"ending": end, "choices": [list(step) for step in path]}
                for end, path in self.ending_paths],
            "approval_required": True, "applied": False,
            "gameplay_certified": False,
        }


class NarrativeAssistController:
    """Preview/review/approve against a single canonical editor transaction."""

    def __init__(self, session: AuthoringSession):
        if not isinstance(session, AuthoringSession):
            reject("invalid_session", "Expected an owning AuthoringSession")
        self.session = session
        self.invalidate()

    def preview(self, raw):
        self.invalidate()
        proposal = validate_proposal(raw)
        before = self.session.snapshot().to_dict()
        project = _candidate(before["project"], proposal)
        plan = self.session.preview_project(
            lambda original: _candidate(original, proposal),
            kind="r75-reviewed-narrative")
        content = Content.from_dict(
            before["content"], rules=authored_rules_for_document(before["content"]))
        canonical = GameProject.from_dict(project, content)
        paths = _coverage(canonical.story, content, canonical.campaigns, proposal)
        digest = sha256(json.dumps(
            proposal, sort_keys=True, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        review = NarrativeReview(
            proposal["id"], before["revision"], digest,
            deepcopy(proposal["source"]), deepcopy(proposal["hook"]),
            tuple(scene["id"] for scene in proposal["scenes"]), paths)
        self._plan, self._review = plan, review
        return review

    def apply(self, review: NarrativeReview, *, approved=False):
        if self._plan is None or self._review is not review:
            reject("stale_review", "Review is stale, foreign or already consumed")
        if approved is not True:
            reject("approval_required", "Human approval must be explicit")
        plan = self._plan
        self.invalidate()
        return self.session.apply(plan)

    def invalidate(self):
        self._plan: AuthoringPlan | None = None
        self._review: NarrativeReview | None = None


def three_endings_template(mission_id: str, *, prefix="r75"):
    """Offline five-scene example with real persistent branch consequences."""
    _safe_id(mission_id, "Mission id")
    _safe_id(prefix, "Prefix")

    def key(value):
        result = prefix + "_" + value
        _safe_id(result, "Scene/flag id")
        return result

    offer, fork = key("offer"), key("decision")
    rescue, pact, depart = key("rescue"), key("pact"), key("depart")
    route, outcome = key("route"), key("outcome")

    def write(name, value):
        return {"kind": "set_flag", "flag": name, "value": value}

    def choice(ident, label, *, target="", condition=None, effects=None):
        row = {"id": ident, "label": label, "effects": effects or []}
        if target:
            row["next_scene"] = target
        if condition is not None:
            row["when"] = condition
        return row

    def scene(ident, title, text, choices):
        return {"id": ident, "title": title, "speaker": "Narrateur",
                "text": text, "choices": choices}

    return {
        "version": 1, "id": key("three_endings"),
        "source": {
            "kind": "offline_template",
            "attribution": "DrawTemp R75 built-in offline example",
            "license": "original-example", "rights": "original",
            "redistribution_allowed": True},
        "hook": {"kind": "after_mission", "id": mission_id},
        "entry_scene": offer,
        "scenes": [
            scene(offer, "Le choix du village", "Un village demande de l'aide.", [
                choice("help", "Secourir", target=fork,
                       effects=[write(route, 1)]),
                choice("talk", "Négocier", target=fork,
                       effects=[write(route, 2)]),
                choice("leave", "Partir", target=fork,
                       effects=[write(route, 3)]),
            ]),
            scene(fork, "Les conséquences", "Votre décision change l'avenir.", [
                choice("save", "Reconstruire", target=rescue,
                       condition={"flag": route, "eq": 1}),
                choice("peace", "Sceller un accord", target=pact,
                       condition={"flag": route, "eq": 2}),
                choice("fallback", "Continuer sa route", target=depart),
            ]),
            scene(rescue, "La reconstruction", "Le village est sauvé.", [
                choice("end", "Fin", effects=[write(outcome, "rescue")])]),
            scene(pact, "La trêve", "Une paix fragile s'installe.", [
                choice("end", "Fin", effects=[write(outcome, "pact")])]),
            scene(depart, "Le départ", "Le héros s'éloigne.", [
                choice("end", "Fin", effects=[write(outcome, "depart")])]),
        ],
        "endings": [rescue, pact, depart],
    }
