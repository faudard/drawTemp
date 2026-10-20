"""R50.B: exercise the actual headless PlayerController on an authored project.

The PlayerController is the same save/intent facade used by the GUI. This is
not an onscreen QML/Qt test, an R15 native export or a release certification.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from drawtemp.export.r15 import preflight
from drawtemp.sdk.authoring import AuthoringSession
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.player_controller import PlayerController
from sporebound.tactical_rpg3 import authored_rules_for_document


class PlayerJourneyError(ValueError):
    pass


def check_player_journey(content_path: str | Path, *, kind: str) -> dict:
    """Read both validated documents and execute/save/reload a real Player intent.

    Project files are never mutated. Saves use a temporary isolated profile.
    Only known R28 minigame variants are supported, never a cosmetic genre
    conversion. The PlayerController owns all persistence and transactions.
    """
    if kind not in ("duel_tactique", "choix_village"):
        raise PlayerJourneyError("No R50.B PlayerController journey for: " + str(kind))
    path = Path(content_path)
    companion = path.with_name(path.stem + ".game.json")
    before_content = sha256(path.read_bytes()).hexdigest()
    before_project = sha256(companion.read_bytes()).hexdigest()

    report = preflight(path)
    if not report["passed"]:
        raise PlayerJourneyError("R15 preflight failed: " + "; ".join(report["errors"]))
    authored = AuthoringSession.open(path)
    pair = authored.snapshot().to_dict()
    content_document = pair["content"]
    content = Content.from_dict(
        content_document, rules=authored_rules_for_document(content_document))
    project = GameProject.from_dict(pair["project"], content)
    campaign = project.campaigns[0]["id"]

    with TemporaryDirectory(prefix="drawtemp-r50b-player-") as temp:
        profile = Path(temp) / "player-profile.json"
        player = PlayerController(content, project, profile)
        player.new_game(campaign, 1, seed=50)
        if kind == "duel_tactique":
            mission = next(iter(content.missions))
            player.start_mission(mission)
            if player.session.active_battle is None:
                raise PlayerJourneyError("CT battle did not start through Player")
            gameplay = "tactical-mission-start"
        else:
            player.choose_story_option("observe")
            if player.session.progress.story_flags.get("r28_observed") is not True:
                raise PlayerJourneyError("Player story choice was not committed")
            gameplay = "narrative-choice-committed"
        expected = player.session.recording()
        save = player.path_for(campaign, 1)
        if not save.is_file():
            raise PlayerJourneyError("PlayerController did not write a checkpoint")
        saved_bytes = save.read_bytes()
        reader = PlayerController(content, project, profile)
        reader.load_game(campaign, 1)
        if reader.session.recording() != expected:
            raise PlayerJourneyError("Player reload does not reproduce the checkpoint")
        if kind == "duel_tactique" and reader.session.active_battle is None:
            raise PlayerJourneyError("Player reload lost the tactical battle")
        if kind == "choix_village" and not reader.session.progress.story_flags.get(
                "r28_observed"):
            raise PlayerJourneyError("Player reload lost the narrative consequence")
        # A second load is read-only and must not silently rewrite the save.
        if save.read_bytes() != saved_bytes:
            raise PlayerJourneyError("Player reload rewrote the saved checkpoint")
        digest = expected["digest"]

    if sha256(path.read_bytes()).hexdigest() != before_content:
        raise PlayerJourneyError("Player modified the authored Content")
    if sha256(companion.read_bytes()).hexdigest() != before_project:
        raise PlayerJourneyError("Player modified the authored GameProject")
    return {
        "kind": "drawtemp-r50b-headless-player-journey",
        "schema": 1,
        "minigame": kind,
        "gameplay": gameplay,
        "preflight_passed": True,
        "player_controller_new_game": True,
        "player_intent_persisted": True,
        "player_save_reload_equal": True,
        "authored_documents_unchanged": True,
        "checkpoint_digest": digest,
        "qt_onscreen_verified": False,
        "native_player_verified": False,
        "clean_machine_export_verified": False,
        "release_9_0_certified": False,
    }
