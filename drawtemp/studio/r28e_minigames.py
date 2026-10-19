"""R28.E — three independent canonical minigame starters and honest QA gates.

Three real pairs of Content/GameProject are created from R15, edited through
R1 and tested with GameSession. This is NOT certification of three runtimes:
R26 Action and R28 Classic RPG Player are not connected.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import ExportError, preflight
from drawtemp.export.templates import create_template
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession
from sporebound.model import Content, RuleError, require
from sporebound.tactical_rpg3 import authored_rules_for_document


class MiniGameError(ValueError):
    """Validation failure; no incomplete project is published."""


@dataclass(frozen=True)
class MiniGameSpec:
    key: str
    label: str
    genre: str
    template: str
    game_type: str
    description: str


MINIGAMES = (
    MiniGameSpec(
        "duel_tactique", "Duel de l'écuyer", "srpg", "tactical", "battle",
        "Une arène d'initiation à l'activation CT et au combat tactique."),
    MiniGameSpec(
        "garde_remparts", "Garde des remparts", "srpg", "blank", "battle",
        "Une carte tactique de défense, indépendante du duel."),
    MiniGameSpec(
        "choix_village", "Le choix du village", "narrative", "narrative", "story",
        "Un prologue à deux issues avec état narratif sauvegardé."),
)
_BY_KEY = {entry.key: entry for entry in MINIGAMES}


def get_minigame(key):
    if type(key) is not str or key not in _BY_KEY:
        raise MiniGameError("Mini-jeu inconnu : " + repr(key))
    return _BY_KEY[key]


def _target(destination):
    if not isinstance(destination, (str, Path)) or not str(destination).strip():
        raise MiniGameError("Destination manquante")
    path = Path(destination).expanduser().absolute()
    if path.exists() or path.is_symlink():
        raise MiniGameError("La destination existe déjà : " + str(path))
    if not path.parent.is_dir():
        raise MiniGameError("Le dossier parent doit exister : " + str(path.parent))
    return path


def preview_minigame(key, destination):
    """Filesystem-free preview; cannot overwrite an existing project."""
    spec = get_minigame(key)
    path = _target(destination)
    return {
        "id": spec.key,
        "title": spec.label,
        "genre": spec.genre,
        "runtime": spec.game_type,
        "template_r15": spec.template,
        "destination": str(path),
        "no_overwrite": True,
        "project_pair": ["game.json", "game.game.json"],
        "release_ready": False,
        "limits": (
            "Projet CT testable, mais Player graphique non certifié"
            if spec.game_type == "battle" else
            "Scènes narratives vérifiables via GameSession, sans jeu action temps réel"),
    }


def _configure(key, content, project):
    """Only known Content/GameProject fields; canonical validators own rules."""
    spec = get_minigame(key)
    project["title"] = spec.label
    project["subtitle"] = spec.description
    project["campaigns"][0]["name"] = spec.label
    mission = content["missions"][0]
    if key == "duel_tactique":
        mission["name"] = "Duel : épreuve CT"
        mission["reward"] = 125
    elif key == "garde_remparts":
        mission["name"] = "Remparts : tenir la position"
        mission["reward"] = 250
        # The R15 blank 12x12 board and tactical engine remain authoritative.
    elif key == "choix_village":
        scene = project["story"]["scenes"][0]
        scene["title"] = "La route ou la place"
        scene["text"] = "Le village appelle à l'aide. Que fait Jeanne ?"
        scene["choices"] = [
            {"id": "enter", "label": "Rejoindre les gardes",
             "effects": [{"kind": "set_flag", "flag": "r28_helped", "value": True}]},
            {"id": "observe", "label": "Observer avant de choisir",
             "effects": [{"kind": "set_flag", "flag": "r28_observed", "value": True}]},
        ]
        # The project-level narrative preset must explicitly preserve the
        # tactical mission as CT under the strict R25 scene contract.
        project["game_modes"] = {
            "version": 1, "default": {"preset": "narrative"},
            "scenes": {mission["id"]: {"preset": "srpg"}},
        }
    else:
        raise MiniGameError("Mini-jeu non pris en charge")
    return content, project


def audit_minigame(content_path, key):
    """Exercise actual R15 preflight and canonical, replay-verifiable GameSession."""
    spec = get_minigame(key)
    content_path = Path(content_path)
    report = preflight(content_path)
    if not report["passed"]:
        raise MiniGameError("Préflight échoué : " + "; ".join(report["errors"]))
    authored = AuthoringSession.open(content_path)
    pair = authored.snapshot().to_dict()
    raw_content = pair["content"]
    content = Content.from_dict(
        raw_content, rules=authored_rules_for_document(raw_content))
    project = GameProject.from_dict(pair["project"], content)
    if project.title != spec.label:
        raise MiniGameError("Le manifeste du mini-jeu ne correspond pas à sa définition")
    campaign = project.campaigns[0]["id"]
    game = GameSession.new(content, project, campaign, seed=28)
    active_scene = game.active_scene()
    if spec.game_type == "story":
        require(active_scene is not None, "Le mini-jeu narratif doit démarrer dans une scène")
        game.choose_story_option("observe")
        require(game.progress.story_flags.get("r28_observed") is True,
                "Le choix narratif n'a pas été enregistré")
        require(game.scene_profile(active_scene["id"])["combat"] == "NONE",
                "La scène narrative doit garder son profil sans combat")
    else:
        require(active_scene is None, "Un mini-jeu tactique ne doit pas bloquer sur un récit")
        mission_id = content_path.name  # unused presentation name never used as mission identity
        mission_id = next(iter(content.missions))
        game.start_mission(mission_id)
        require(game.active_battle is not None, "La mission CT ne s'est pas lancée")
        require(game.scene_profile(mission_id)["combat"] == "TACTICAL_CT",
                "Une mission CT ne doit pas se lancer en mode action")
    recorded = game.recording()
    restored = GameSession.from_recording(recorded, content, project)
    if restored.recording() != recorded:
        raise MiniGameError("Le checkpoint de session ne se restaure pas à l'identique")
    return {
        "schema": 1,
        "kind": "r28e-minigame-audit",
        "minigame": key, "genre": spec.genre,
        "content_validated": True,
        "preflight_passed": True,
        "game_session_roundtrip": True,
        "gameplay": spec.game_type,
        "checkpoint_digest": recorded["digest"],
        "author_documents_unchanged": authored.snapshot().dirty is False,
        "native_player_verified": False,
        "visual_playtest_verified": False,
        "r28_release_certified": False,
    }


def _build(key, destination):
    spec = get_minigame(key)
    # R15 performs its own staging and no-overwrite checks; we're nested
    # inside a private build directory that is never published on failure.
    project_folder = create_template(spec.template, destination)
    session = AuthoringSession.open(project_folder / "game.json")
    plan = session.preview_pair(lambda content, project: _configure(
        key, content, project), kind="r28.minigame.initialize",
        views=("workspace", "inspector"))
    session.apply(plan)
    session.save()
    audit = audit_minigame(project_folder / "game.json", key)
    return project_folder, audit


def create_minigame(key, destination):
    """Atomically publish one independent two-document project or nothing."""
    get_minigame(key)
    target = _target(destination)
    with TemporaryDirectory(prefix=".drawtemp-r28e-", dir=target.parent) as tmp:
        stage = Path(tmp) / "project"
        _build(key, stage)
        _target(target)  # recheck no external writer claimed the destination
        os.rename(stage, target)
    return target


def create_portfolio(destination):
    """Create all three projects under one directory, all-or-nothing."""
    target = _target(destination)
    with TemporaryDirectory(prefix=".drawtemp-r28e-portfolio-", dir=target.parent) as tmp:
        stage = Path(tmp) / "portfolio"
        stage.mkdir()
        for spec in MINIGAMES:
            _build(spec.key, stage / spec.key)
        # Verify all separate paired projects before publication.
        reports = [
            audit_minigame(stage / spec.key / "game.json", spec.key)
            for spec in MINIGAMES
        ]
        require(len(set(r["checkpoint_digest"] for r in reports)) == len(MINIGAMES),
                "The three minigames need distinct project checkpoints")
        _target(target)
        os.rename(stage, target)
    return target


def certification_matrix(root):
    """No decorative green release badge: report measured vs missing gates."""
    folder = Path(root)
    reports = []
    for spec in MINIGAMES:
        path = folder / spec.key / "game.json"
        try:
            evidence = audit_minigame(path, spec.key)
        except (MiniGameError, RuleError, OSError, ValueError) as exc:
            evidence = {"minigame": spec.key, "passed": False, "error": str(exc)}
        else:
            evidence["passed"] = True
        reports.append(evidence)
    tested = {row["genre"] for row in reports if row["passed"]}
    required_modes = {"srpg", "narrative", "action"}
    return {
        "kind": "r28e-certification-matrix", "schema": 1,
        "projects": reports,
        "three_independent_documents": all(row["passed"] for row in reports),
        "mode_coverage": sorted(tested),
        "missing_mode_coverage": sorted(required_modes - tested),
        "native_player_on_three_os": False,
        "gui_roundtrip_and_visual_assertions": False,
        "manual_onboarding_fr_en": False,
        "r28_10_three_genres_certified": False,
        "release_6_4_go": False,
        "go_reason": ("R25/R26 action routing, 3-OS Player bundles, GUI player "
                      "roundtrip and novice onboarding still need evidence."),
    }
