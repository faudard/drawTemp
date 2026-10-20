"""Unified campaign, story and tactical lifecycle. No UI or new combat rules."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import hashlib
import json

from .ai import play_activation
from .campaign import Campaign
from .campaign_flow import (available_missions as flow_available_missions,
                            inspect_campaign as flow_inspect_campaign,
                            settle as settle_campaign_flow, verify_save as verify_flow_save)
from .engine import Battle
from .exploration import Exploration
from .world_travel import PENDING, WorldJourney
from .fronts import MultiFrontSession
from .model import RuleError, require
from .narrative import StoryBook
from .rules import default_rules
from .storage import write_json


def digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def gameplay_project_digest(project):
    """Fingerprint game-affecting project data, not decorative world positions.

    Legacy projects without a world preserve their exact original digest.
    Adding/moving map pins cannot invalidate a persisted Campaign checkpoint.
    Other story, campaign, asset and gameplay fields remain strictly verified.
    """
    manifest = project.to_dict()
    world = manifest.pop("world", {})
    # Decorative positions remain save-compatible, but authored encounters
    # affect gameplay and must invalidate incompatible checkpoints.
    if world.get("events"):
        manifest["world_events"] = world["events"]
    return digest(manifest)


class IncompatibleSaveError(RuleError):
    """A verified save belongs to other content, project or gameplay rules.

    Identity changes are never coerced, reconstructed or replayed with new
    rules. A future migration must be opt-in and independently verified.
    """

    def __init__(self, dimension, saved, running):
        def fingerprint(value):
            return value[:12] if isinstance(value, str) and len(value) == 64 else digest(value)[:12]

        self.dimension = dimension
        super().__init__(
            f"Save incompatible ({dimension}): recorded={fingerprint(saved)}, "
            f"current={fingerprint(running)}. Reopen with the original "
            "content/project/rules or run a validated, explicit migration. "
            "The replay has not been modified."
        )


class GameSession:
    """Compose Campaign, StoryBook, Battle and MultiFrontSession.

    This uses a new explicit session save format. Existing PlayerSession slots
    and historical battle/multi-front replay formats are untouched.
    """
    VERSION = 1
    FRONT_BATTLE_GROUPS = ("battles", "rescue_battles", "pursuit_battles", "recovery_battles")

    def __init__(self, content, project, campaign_id, *, seed=1, rules=None):
        if rules is None:
            from .event_pages import has_pages
            from .logic_variables import has_logic_variables
            from .logic_vertical_objective import has_slice_objective
            from .tactical_rpg3 import authored_rules_for_document
            raw = content.to_dict()
            rules = (authored_rules_for_document(raw)
                     if has_pages(raw) or has_logic_variables(raw) or has_slice_objective(raw)
                     else default_rules())
        self.rules = rules
        content.validate(rules=self.rules)
        project.validate(content)
        require(project.campaign(campaign_id) is not None, "Unknown campaign")
        require(type(seed) is int, "Invalid seed")
        self.content, self.project = deepcopy(content), deepcopy(project)
        self.campaign_id, self.seed = campaign_id, seed
        self.story = StoryBook(project.story, content, project.campaigns)
        self.exploration = Exploration(project.exploration, project.story)
        self.progress = project.new_game(campaign_id, content)
        from .classic_party import EXTENSION as PARTY_EXTENSION, ClassicParty
        party = self.project.extensions.get(PARTY_EXTENSION)
        config = (party["data"]["campaigns"].get(campaign_id)
                  if party is not None else None)
        self._classic_party = ClassicParty(config) if config is not None else None
        from .party_orchestration import PartyOrchestration
        orchestration = (party["data"].get("orchestration")
                         if config is not None else None)
        self._party_orchestration = (PartyOrchestration(orchestration, config,
                                                             campaign_id=campaign_id,
                                                             campaigns=party["data"]["campaigns"])
                                     if orchestration is not None else None)
        # Only initial new-game construction seeds these items. Loaded saves
        # replace Campaign through verified replay, never replenish stock.
        if config is not None:
            self.progress.inventory.update(
                deepcopy(party["data"].get("starting_inventory", {})))
        self._rpg_encounter = None  # R41.B2 opt-in, GameSession owns combat
        if self._classic_party is not None:
            for hero_id in self._classic_party.members:
                self.progress.hero(hero_id)  # canonical R8 HeroProgress, not a second RPG database
        from .scene_router import SceneRouter
        self.scene_router = SceneRouter(self.project.scene_routes, self.content, self.project)
        # R44.E: validate/compile the authored graph once per immutable project.
        # World state itself is still only in Campaign.story_flags and R25 routes.
        from .world_graph44 import EXTENSION as WORLDGRAPH_EXTENSION, WorldGraph
        atlas_spec = self.project.extensions.get(WORLDGRAPH_EXTENSION)
        self._world_graph = (WorldGraph(
            atlas_spec["data"], self.content, self.project)
            if atlas_spec is not None else None)
        self.route_scene = self.scene_router.start
        self.route_history = []
        self._route_starting = False
        # Opt-in per-scene movement journal; absent in all legacy recordings.
        self._rt_origin = None
        self._rt_position = None
        self._rt_journal = None
        self._platform = None  # R32 opt-in side-view adapter, never CT.
        self._action = None  # R50.B opt-in R26 rules, recorded inside GameSession.
        self._action_settlements = []  # Verifiable one-shot Campaign credits.
        # R34.C is opt-in, versioned and owned by this GameSession.
        from .roguelite import EXTENSION as ROGUELITE_EXTENSION, RogueliteRun
        run_spec = self.project.extensions.get(ROGUELITE_EXTENSION)
        self._roguelite = (RogueliteRun(
            run_spec["data"], content=self.content, project=self.project)
            if run_spec is not None else None)
        # R35.A: optional clock owned by this session, not by the renderer.
        from .living_world import EXTENSION, LivingWorld
        spec = self.project.extensions.get(EXTENSION)
        self._living_world = (
            LivingWorld(spec["data"],
                        set(self.project.exploration) | set(self.content.missions),
                        exploration=self.project.exploration,
                        item_ids=set(self.content.equipment))
            if spec is not None else None)
        # R46.A is strictly opt-in: existing CT/replays omit this state.
        from .cinematic_pro import EXTENSION as CINEMATIC_PRO_EXTENSION, CinematicProRuntime
        self._cinematic_pro = (
            CinematicProRuntime(self.project)
            if CINEMATIC_PRO_EXTENSION in self.project.extensions else None)
        # R37.B: opt-in AI memory belongs to the canonical session, not a
        # parallel engine or the renderer. Legacy projects remain unchanged.
        from .advanced_ai import EXTENSION as ADVANCED_AI_EXTENSION, AdvancedAI
        ai_spec = self.project.extensions.get(ADVANCED_AI_EXTENSION)
        self._advanced_ai = (
            AdvancedAI(ai_spec["data"],
                       living_world=spec["data"] if spec is not None else None,
                       content=self.content)
            if ai_spec is not None else None)
        # R55: canonical GameSession-owned economy, opt-in for authored projects.
        from .system_design import EXTENSION as SYSTEMS_EXTENSION, SystemEconomy
        system_spec = self.project.extensions.get(SYSTEMS_EXTENSION)
        from .settlement_management import EXTENSION as SETTLEMENT_EXTENSION
        settlement_spec = self.project.extensions.get(SETTLEMENT_EXTENSION)
        self._systems = (
            SystemEconomy(
                system_spec["data"],
                set(self.project.exploration) | set(self.content.missions),
                settlement=(settlement_spec["data"]
                            if settlement_spec is not None else None))
            if system_spec is not None else None)
        # R62.A opt-in farms share R35 time and Campaign inventory.
        from .farming_life import EXTENSION as FARM_EXTENSION, FarmingLife
        farm_spec = self.project.extensions.get(FARM_EXTENSION)
        known_items = set(self.content.equipment)
        if system_spec is not None:
            known_items.update(row["id"] for row in system_spec["data"]["resources"])
        self._farming = (FarmingLife(farm_spec["data"],
                                     set(self.project.exploration), known_items)
                         if farm_spec is not None else None)
        # R62.B.2: the R35 clock and NPC schedules remain authoritative.
        from .relationship_life import (EXTENSION as SOCIAL_EXTENSION,
                                        RelationshipLife)
        social_spec = self.project.extensions.get(SOCIAL_EXTENSION)
        world_data = spec["data"] if spec is not None else None
        social_npcs = {row["id"] for row in world_data["npcs"]} if world_data else set()
        social_activities = ({row["id"]: {stop["activity"] for stop in row["schedule"]}
                              for row in world_data["npcs"]} if world_data else {})
        self._relationships = (
            RelationshipLife(social_spec["data"], social_npcs, known_items,
                             npc_activities=social_activities)
            if social_spec is not None else None)
        # R63: GameSession owns the optional survival journal and needs.
        from .survival import EXTENSION as SURVIVAL_EXTENSION, SurvivalRuntime
        survival_spec = self.project.extensions.get(SURVIVAL_EXTENSION)
        self._survival = (
            SurvivalRuntime(survival_spec["data"], set(self.project.exploration),
                            exploration=self.project.exploration)
            if survival_spec is not None else None)
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()
        from .world_streaming import EXTENSION as STREAM_EXTENSION, WorldStreamState
        stream_spec = self.project.extensions.get(STREAM_EXTENSION)
        self._stream_world = (
            WorldStreamState(stream_spec["data"], self.project)
            if stream_spec is not None else None)
        self.siege_id = None  # Optional authored siege identity; old slots omit it.
        # Project-owned narrative choices; no mutation of Battle's replay log.
        self.tactical_story_pending = ""
        self.tactical_story_queue = []

    @classmethod
    def new(cls, content, project, campaign_id, **kwargs):
        return cls(content, project, campaign_id, **kwargs)

    @property
    def mode(self):
        return "fronts" if self.fronts is not None else (
            "battle" if self.battle is not None else (
                "rpg" if self._rpg_encounter is not None else "campaign"))

    @property
    def active_battle(self):
        if self.fronts is not None:
            if self.fronts.recovery_battles:
                return self.fronts.recovery_battles[
                    sorted(self.fronts.recovery_battles)[0]]
            return self.fronts.active
        return self.battle

    def active_scene(self):
        return self.story.active_scene(self.progress)

    def narrative_state(self):
        """Read-only R42 projection of typed flags from canonical Campaign."""
        from .narrative_state_r42 import state_snapshot
        return state_snapshot(self.project.story, self.progress)

    def narrative_line(self):
        """Read-only saved v2 dialogue cursor for Player, campaign or CT."""
        if self.project.story.get('schema_version') != 2:
            return None
        scene = (self.tactical_scene() if self.tactical_story_pending
                 else self.active_scene())
        if scene is None:
            return None
        from .narrative_playback_r42 import current_line
        return current_line(self.progress, scene)

    def advance_narrative_line(self):
        """Commit one presentation-only line step to the existing Campaign save."""
        require(self.project.story.get('schema_version') == 2,
                'Multi-line dialogue requires narrative v2')
        scene = (self.tactical_scene() if self.tactical_story_pending
                 else self.active_scene())
        require(scene is not None, 'No dialogue to advance')
        from .narrative_playback_r42 import advance_line
        return advance_line(self.progress, scene)

    def _require_narrative_line_complete(self):
        if self.project.story.get('schema_version') == 2:
            line = self.narrative_line()
            require(line is not None and line['complete'],
                    'Read all dialogue lines before choosing')

    def scene_profile(self, scene_id=None):
        """Read the canonical project profile without changing CT state."""
        if scene_id is not None:
            known = (set(self.content.missions)
                     | set(self.project.exploration)
                     | set(self.story.scenes))
            require(type(scene_id) is str and scene_id in known,
                    "Unknown game mode scene")
        from .game_modes import resolve_scene_profile
        return resolve_scene_profile(self.project.game_modes, scene_id)

    def party_state(self):
        """Detached R41 roster selection; HeroProgress/inventory stay in Campaign."""
        require(self._classic_party is not None,
                "This campaign has no RPG_TURN party configured")
        return self._classic_party.snapshot()

    def _party_edit_allowed(self):
        require(self._classic_party is not None
                and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R41 party changes require an idle campaign without dialogue")

    def party_recruit(self, hero_id):
        """One transaction across party membership and existing HeroProgress."""
        self._party_edit_allowed()
        candidate = deepcopy(self._classic_party)
        candidate.recruit(hero_id)
        progress = deepcopy(self.progress)
        progress.hero(hero_id)
        self.progress, self._classic_party = progress, candidate
        return self.party_state()

    def party_set_active(self, hero_ids):
        """Change active/reserve assignment without cloning hero stats/items."""
        self._party_edit_allowed()
        candidate = deepcopy(self._classic_party)
        candidate.set_active(hero_ids)
        orchestration = (deepcopy(self._party_orchestration)
                         if self._party_orchestration is not None else None)
        if orchestration is not None:
            orchestration.activate(candidate.active)
        self._classic_party, self._party_orchestration = candidate, orchestration
        return self.party_state()

    def party_orchestration_state(self, *, combat="RPG_TURN"):
        """Detached leader/formation and available cooperative capability IDs."""
        require(self._party_orchestration is not None,
                "R53 orchestration is not configured")
        state = self._party_orchestration.snapshot()
        state["eligible_combos"] = self._party_orchestration.eligible_combos(combat)
        state["pause_policy"] = self._party_orchestration.pause_policy
        return state

    def party_hybrid_state(self):
        """R53.C: read-only cross-mode projection from three canonical owners.

        Campaign has no persistent per-hero HP/MP. Such values are reported
        only during an actual RPG or CT encounter; never synthesize them on
        exploration or pretend they survived a mode transition.
        """
        require(self._party_orchestration is not None and self.scene_router.enabled,
                "R53 hybrid view needs routed party orchestration")
        mode = self.mode
        require(mode in ("campaign", "rpg", "battle"),
                "R53 hybrid projection does not support multi-front battles")
        authored = self._party_orchestration.snapshot()
        if mode == "rpg":
            live = {a["id"]: a for a in self._rpg_encounter.view()["actors"]
                    if a["team"] == "party"}
            phase = "RPG_TURN"
        elif mode == "battle":
            live = {u.id: u for u in self.battle.units if u.team == "player"}
            phase = "TACTICAL_CT"
        else:
            live = {}
            phase = ("EXPLORATION" if self.route_scene in self.project.exploration
                     else "ROUTE_TRANSIT")
        rows = []
        for uid, slot in zip(authored["active"], authored["formation"]):
            actor = live.get(uid)
            rows.append({
                "id": uid, "leader": uid == authored["leader"],
                "formation": slot,
                "xp": self.progress.heroes[uid].xp,
                "hp": actor["hp"] if mode == "rpg" and actor is not None
                      else actor.hp if actor is not None else None,
                "mp": actor["mp"] if mode == "rpg" and actor is not None
                      else actor.mp if actor is not None else None,
                "vitals_source": phase if actor is not None else "unavailable",
            })
        return {
            "phase": phase, "scene": self.route_scene,
            "history": list(self.route_history),
            "members": rows,
            "campaign_inventory": deepcopy(self.progress.inventory),
            "campaign_gold": self.progress.gold,
            "party_pause_policy": self._party_orchestration.pause_policy,
            "active_combos": (self._rpg_encounter.available_combos()
                              if mode == "rpg" else []),
        }

    def party_switch_leader(self, hero_id):
        self._party_edit_allowed()
        require(self._party_orchestration is not None, "R53 orchestration disabled")
        candidate = deepcopy(self._party_orchestration)
        candidate.switch_leader(hero_id)
        self._party_orchestration = candidate
        return self.party_orchestration_state()

    def party_set_formation(self, slots):
        self._party_edit_allowed()
        require(self._party_orchestration is not None, "R53 orchestration disabled")
        candidate = deepcopy(self._party_orchestration)
        candidate.set_formation(slots)
        self._party_orchestration = candidate
        return self.party_orchestration_state()

    def rpg_available(self):
        """Discover only eligible, authored RPG encounters (no implicit routing)."""
        from .classic_party import EXTENSION
        spec = self.project.extensions.get(EXTENSION)
        if (spec is None or self._classic_party is None
                or self.mode != "campaign"
                or self.progress.story_pending or self.tactical_story_pending):
            return []
        catalogue = spec["data"].get("encounters", {})
        return sorted(eid for eid, row in catalogue.items()
                      if (not self.scene_router.enabled
                          or (self.route_scene == row["scene"]
                              and self.route_scene in self.project.exploration))
                      and not self.progress.story_flags.get("r41_" + eid, False))

    def rpg_start(self, encounter_id):
        """Begin RPG_TURN combat at the current routed exploration checkpoint."""
        from .classic_encounter import ClassicEncounter
        require(type(encounter_id) is str and encounter_id in self.rpg_available(),
                "R41 encounter unavailable or already rewarded")
        require(self._rt_journal is None and self._platform is None,
                "R41 encounter cannot overlap a realtime/platform episode")
        from .classic_party import EXTENSION
        config = self.project.extensions[EXTENSION]["data"]["encounters"][encounter_id]
        require(self.scene_profile(config["scene"])["combat"] == "RPG_TURN",
                "R41 encounter is not in an RPG_TURN scene")
        if self.scene_router.enabled:
            require(self.route_scene == config["scene"]
                    and self.route_scene in self.project.exploration,
                    "R41 encounter must start in its authored route scene")
        candidate = ClassicEncounter(
            encounter_id, config, self._classic_party.active,
            self.content, self.progress.inventory,
            hero_progress=self.progress.heroes,
            combo_specs=(self._party_orchestration.rpg_combo_specs()
                         if self._party_orchestration is not None else None))
        self._rpg_encounter = candidate
        return self.rpg_state()

    def rpg_state(self):
        require(self._rpg_encounter is not None, "No active RPG_TURN encounter")
        return self._rpg_encounter.view()

    def rpg_action(self, action):
        """One atomic R41 action, including campaign potion consumption."""
        require(self.mode == "rpg", "No active RPG_TURN encounter")
        candidate = deepcopy(self._rpg_encounter)
        candidate.command(deepcopy(action))
        progress = deepcopy(self.progress)
        progress.inventory = deepcopy(candidate.inventory)
        self.progress, self._rpg_encounter = progress, candidate
        return self.rpg_state()

    def rpg_finish(self):
        """Exit a resolved encounter; victory rewards settle once in Campaign."""
        require(self.mode == "rpg" and self._rpg_encounter.result is not None,
                "Resolve RPG_TURN combat before returning to campaign")
        candidate = deepcopy(self.progress)
        encounter = self._rpg_encounter
        flag = "r41_" + encounter.id
        if encounter.result == "victory":
            require(not candidate.story_flags.get(flag, False),
                    "R41 encounter reward was already settled")
            require(candidate.gold + encounter.reward_gold <= 1000000,
                    "R41 reward exceeds campaign gold cap")
            candidate.story_flags[flag] = True
            candidate.gold += encounter.reward_gold
            for uid in encounter.party:
                candidate.hero(uid).xp += 50
        self.progress = candidate
        self._rpg_encounter = None
        return {"id": encounter.id, "result": encounter.result,
                "gold": candidate.gold}

    def rpg_quest_state(self):
        """Read a single template quest from canonical GameProject + Campaign.

        No independent quest state, rewards register or private save extension:
        all progress derives from R41 victory flags and the R9 story flag ledger.
        """
        from .classic_party import EXTENSION
        spec = self.project.extensions.get(EXTENSION)
        quest = spec["data"].get("quest") if spec is not None else None
        if quest is None or self._classic_party is None:
            return None
        flags = self.progress.story_flags
        cleared = [eid for eid in quest["encounters"]
                   if flags.get("r41_" + eid) is True]
        flag = "r41_quest_" + self.campaign_id
        claimed = flags.get(flag) is True
        ready = (not claimed and len(cleared) == len(quest["encounters"])
                 and self.mode == "campaign"
                 and not self.progress.story_pending
                 and (not self.scene_router.enabled
                      or self.route_scene == quest["return_scene"]))
        return {"title": quest["title"], "completed": claimed,
                "cleared": cleared, "required": list(quest["encounters"]),
                "return_scene": quest["return_scene"],
                "ready": ready, "reward_gold": quest["reward_gold"],
                "reward_item": quest["reward_item"],
                "reward_quantity": quest["reward_quantity"]}

    def rpg_claim_quest(self):
        """Exactly-once story reward; atomic, save/replay stable and routed."""
        quest = self.rpg_quest_state()
        require(quest is not None and quest["ready"],
                "R41 quest requires two victories and a return to the village")
        candidate = deepcopy(self.progress)
        flag = "r41_quest_" + self.campaign_id
        require(flag not in candidate.story_flags,
                "R41 quest has already been claimed")
        require(candidate.gold + quest["reward_gold"] <= 1000000,
                "Quest gold exceeds campaign bounds")
        existing = candidate.inventory.get(quest["reward_item"], 0)
        require(type(existing) is int and 0 <= existing
                and existing + quest["reward_quantity"] <= 1000000,
                "Quest item reward exceeds campaign bounds")
        candidate.story_flags[flag] = True
        candidate.gold += quest["reward_gold"]
        candidate.inventory[quest["reward_item"]] = (
            existing + quest["reward_quantity"])
        self.progress = candidate
        return self.rpg_quest_state()

    def roguelite_state(self):
        """Detached run/meta snapshot; never expose mutable gameplay state."""
        require(self._roguelite is not None, "R34 roguelite is not configured")
        return self._roguelite.snapshot()

    def _roguelite_action(self, kind, value=None):
        require(self._roguelite is not None and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R34 run commands require an active campaign without combat/dialogue")
        return self._roguelite.action(kind, value)

    def roguelite_move(self, room_id):
        return self._roguelite_action("move", room_id)

    def roguelite_claim(self):
        return self._roguelite_action("claim")

    def roguelite_die(self):
        return self._roguelite_action("die")

    def roguelite_restart(self):
        return self._roguelite_action("restart")

    def roguelite_checkpoint(self):
        return self._roguelite_action("checkpoint")

    def world_stream_state(self):
        """Read-only projection of opt-in R54 world state."""
        require(self._stream_world is not None, "R54 world is not configured")
        return self._stream_world.view()

    def world_stream_event(self, event_id, entity_id, before, after):
        """Apply one persistent compare-and-swap entity event without rewards."""
        require(self._stream_world is not None and self.mode == "campaign",
                "R54 world events require an active exploration campaign")
        return self._stream_world.apply(event_id, entity_id, before, after)


    def cinematic_pro_state(self):
        """Detached cursor/once-only ledger for the canonical R11 timeline."""
        require(self._cinematic_pro is not None,
                "R46 cinematic cues are not enabled in this project")
        return self._cinematic_pro.snapshot()

    def _cinematic_pro_action(self):
        require(self._cinematic_pro is not None and self.mode == "campaign",
                "R46 cinematic commands require an enabled campaign session")
        return self._cinematic_pro

    def cinematic_pro_start(self, clip_id):
        return self._cinematic_pro_action().start(clip_id, self.progress)

    def cinematic_pro_advance(self, elapsed_ms):
        return self._cinematic_pro_action().advance(elapsed_ms, self.progress)

    def cinematic_pro_pause(self):
        return self._cinematic_pro_action().pause()

    def cinematic_pro_resume(self):
        return self._cinematic_pro_action().resume()

    def cinematic_pro_seek(self, position_ms):
        # Seeking is presentation-only; it cannot grant quest flags or loot.
        return self._cinematic_pro_action().seek(position_ms)

    def cinematic_pro_skip(self):
        return self._cinematic_pro_action().skip(self.progress)

    def system_state(self):
        """Read a detached snapshot of the R55 resource economy."""
        require(self._systems is not None, "R55 systems not configured")
        return self._systems.snapshot()

    def system_preview(self, ticks=1):
        require(self._systems is not None, "R55 systems not configured")
        return self._systems.preview(ticks)

    def system_advance(self, ticks=1):
        require(self._systems is not None and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R55 economy requires campaign mode without pending dialogue")
        return self._systems.advance(ticks)

    def system_trade(self, merchant_id, action, quantity, transaction_id):
        """Transfer resources with canonical Campaign inventory and currency."""
        require(self._systems is not None and self.mode == "campaign"
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R55 trading requires routed exploration without dialogue")
        return self._systems.trade(
            self.progress, self.route_scene, merchant_id, action,
            quantity, transaction_id)

    def system_fulfill(self, quest_id):
        require(self._systems is not None and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R55 quest delivery requires active campaign without dialogue")
        return self._systems.fulfill(self.progress, quest_id)

    def settlement_state(self):
        """R61.A settlement view; stocks remain owned by R55 SystemEconomy."""
        require(self._systems is not None, "R61 settlement not configured")
        return self._systems.settlement_state()

    def settlement_build(self, building_id, receipt_id):
        require(self._systems is not None and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R61 construction requires an unblocked campaign")
        return self._systems.settlement_build(building_id, receipt_id)

    def settlement_assign(self, resident_id, building_id, receipt_id):
        require(self._systems is not None and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R61 workforce changes require an unblocked campaign")
        return self._systems.settlement_assign(
            resident_id, building_id, receipt_id)

    def farming_state(self, scene=None):
        """R62 detached plot, weather and animal view, including off-focus scenes."""
        require(self._farming is not None, "R62 farming not configured")
        return self._farming.view(scene=scene)

    def _farming_command(self, kind, target, receipt_id, *, crop=None):
        require(self._farming is not None and self._living_world is not None
                and self.mode == "campaign" and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R62 farming requires routed exploration without dialogue")
        authored = (self._farming.plots.get(target) if kind in ("plant", "harvest")
                    else self._farming.animals.get(target))
        require(authored is not None and authored["scene"] == self.route_scene,
                "R62 target must be in the active scene")
        # Compute every change privately; a failed command cannot alter the
        # farm, Campaign inventory or any other canonical session component.
        staged = deepcopy(self._farming)
        change = staged.command(kind, target, receipt_id, crop=crop)
        if change is None:
            return False
        item, delta = change
        existing = self.progress.inventory.get(item, 0)
        from .farming_life import MAX_ITEM_QUANTITY
        require(type(existing) is int and 0 <= existing <= MAX_ITEM_QUANTITY
                and 0 <= existing + delta <= MAX_ITEM_QUANTITY,
                "R62 insufficient inventory or capacity")
        self.progress.inventory[item] = existing + delta
        self._farming = staged
        return True

    def farming_plant(self, plot_id, crop_id, receipt_id):
        return self._farming_command("plant", plot_id, receipt_id, crop=crop_id)

    def farming_harvest(self, plot_id, receipt_id):
        return self._farming_command("harvest", plot_id, receipt_id)

    def farming_feed(self, animal_id, receipt_id):
        return self._farming_command("feed", animal_id, receipt_id)

    def farming_collect(self, animal_id, receipt_id):
        return self._farming_command("collect", animal_id, receipt_id)

    def relationship_state(self, npc=None):
        """Detached deterministic affinities and cooldowns for Player/Studio."""
        require(self._relationships is not None, "R62 relationships not configured")
        return self._relationships.view(npc)

    def _relationship_command(self, kind, npc_id, receipt_id, *, item=None):
        require(self._relationships is not None and self._living_world is not None
                and self.mode == "campaign" and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "R62 social action requires routed exploration without dialogue")
        definition = self._relationships.definitions.get(npc_id)
        require(definition is not None, "R62 social NPC is not authored")
        pose = self._living_world.npc_pose(npc_id, self.progress.story_flags)
        require(pose["scene"] == self.route_scene
                and pose["activity"] != "unavailable",
                "R62 social NPC is unavailable in the player's scene")
        # R35 positioned NPCs require adjacency; legacy schedule-only NPCs
        # have no position and keep their existing scene-level interaction.
        if pose.get("pos") is not None:
            player = self.route_state().get("position")
            require(type(player) in (list, tuple) and len(player) == 2
                    and sum(abs(player[i] - pose["pos"][i]) for i in range(2)) <= 1,
                    "R62 social NPC is not within interaction reach")
        activity = pose["activity"]
        require(kind != "talk" or definition["talk_activity"] in ("any", activity),
                "R62 social NPC is not available for conversation")
        staged = deepcopy(self._relationships)
        debit = staged.command(kind, npc_id, receipt_id, item=item)
        if debit is None:
            return False
        resource, delta = debit
        if delta:
            from .farming_life import MAX_ITEM_QUANTITY
            existing = self.progress.inventory.get(resource, 0)
            require(type(existing) is int and 0 <= existing <= MAX_ITEM_QUANTITY
                    and 0 <= existing + delta <= MAX_ITEM_QUANTITY,
                    "R62 social gift needs a canonical owned inventory item")
            self.progress.inventory[resource] = existing + delta
        self._relationships = staged
        return True

    def relationship_talk(self, npc_id, receipt_id):
        return self._relationship_command("talk", npc_id, receipt_id)

    def relationship_gift(self, npc_id, item_id, receipt_id):
        return self._relationship_command("gift", npc_id, receipt_id, item=item_id)

    def survival_state(self):
        """R63 detached survival projection; Campaign owns item balances."""
        require(self._survival is not None, "Survival is not configured")
        return self._survival.snapshot()

    def survival_condition(self):
        """R63.C derived failure/recovery status, no persisted shadow state."""
        require(self._survival is not None, "Survival is not configured")
        return self._survival.condition()

    def _survival_preflight(self):
        require(self._survival is not None and self.mode == "campaign"
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "Survival actions require routed exploration without dialogue")

    def survival_advance(self, ticks=1):
        self._survival_preflight()
        return self._survival.advance(ticks)

    def _survival_near(self, row):
        """Placed resources/refuges require the canonical campaign position."""
        if "pos" not in row:
            return
        location = self.route_state().get("position")
        require(type(location) in (list, tuple) and len(location) == 2
                and all(type(v) in (int, float) for v in location)
                and abs(location[0] - row["pos"][0])
                  + abs(location[1] - row["pos"][1]) <= 1,
                "Survival target is not within interaction reach")

    def survival_gather(self, node_id, transaction_id):
        self._survival_preflight()
        row = self._survival.nodes.get(node_id)
        if row is not None:
            self._survival_near(row)
        return self._survival.gather(
            self.progress, self.route_scene, node_id, transaction_id)

    def survival_craft(self, recipe_id, transaction_id):
        self._survival_preflight()
        return self._survival.craft(
            self.progress, self.route_scene, recipe_id, transaction_id)

    def survival_rest(self, shelter_id, transaction_id):
        self._survival_preflight()
        row = self._survival.shelters.get(shelter_id)
        if row is not None:
            self._survival_near(row)
        return self._survival.rest(
            self.progress, self.route_scene, shelter_id, transaction_id)

    def survival_eat(self, food_id, transaction_id):
        self._survival_preflight()
        return self._survival.eat(
            self.progress, self.route_scene, food_id, transaction_id)

    def living_world_state(self, scene=None):
        """R35.A detached schedule projection, including off-focus scenes."""
        require(self._living_world is not None, "Living world is not configured")
        return self._living_world.view(self.progress.story_flags, scene=scene)

    def living_world_advance(self, ticks=1):
        """Explicit exploration-only clock advance (cutscenes/travel/fast-forward)."""
        require(self._living_world is not None and self.mode == "campaign"
                and not self.progress.story_pending,
                "Living-world clock is paused outside exploration")
        result = self._living_world.advance(ticks)
        if self._farming is not None:
            self._farming.sync(self._living_world.day)
        if self._relationships is not None:
            self._relationships.sync(self._living_world.day)
        return result

    def living_world_reputation_event(self, faction, delta, event_id):
        """Apply an idempotent, explicit faction event to the session checkpoint."""
        require(self._living_world is not None,
                "Living world is not configured")
        return self._living_world.adjust_reputation(faction, delta, event_id)

    def living_world_finish_daily_quest(self, quest_id):
        """Award canonical Campaign gold exactly once per day and quest."""
        require(self._living_world is not None and self.mode == "campaign"
                and not self.progress.story_pending,
                "Daily quests require an active exploration session")
        return self._living_world.finish_daily_quest(quest_id, self.progress)

    def living_world_timeline(self, *, scene=None, limit=512):
        """Read-only R35 authoring diagnostics, never advances simulation."""
        require(self._living_world is not None, "Living world is not configured")
        from .living_world_diagnostics import timeline
        return timeline(self._living_world, self.progress.story_flags,
                        scene=scene, limit=limit)

    def living_world_trade(self, shop_id, item_id, action, quantity,
                           transaction_id):
        """Atomic buy/sell in canonical Campaign inventory and currency."""
        require(self._living_world is not None
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "Trading requires active exploration without a pending dialogue")
        return self._living_world.transact(
            self.progress, self.progress.story_flags, self.route_scene,
            shop_id, item_id, action, quantity, transaction_id)

    def living_world_craft(self, recipe_id, quantity, transaction_id):
        """R45.A atomic crafting in canonical Campaign gold and inventory."""
        require(self._living_world is not None
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending,
                "Crafting requires exploration without pending dialogue")
        return self._living_world.craft(
            self.progress, self.progress.story_flags, self.route_scene,
            recipe_id, quantity, transaction_id)

    def ai_state(self, actor_id=None):
        """R37.B detached, opt-in memory inspection (no tactical mutation)."""
        require(self._advanced_ai is not None, "R37 advanced AI is not enabled")
        return self._advanced_ai.state(actor_id)

    def _ai_suspicion(self, actor_id):
        value = self._advanced_ai.state(actor_id)["values"].get("suspicion", 0)
        require(type(value) is int and 0 <= value <= 3,
                "R37 suspicion must be an integer in 0..3")
        return value

    def ai_boss_preview(self, director_id):
        """R37.E: project-authored presentation of an actual CT boss encounter.

        No second phase counter, no imaginary reinforcements and no implicit
        execution. Battle remains authoritative for all triggers/telegraphs.
        """
        require(self._advanced_ai is not None,
                "R37 advanced AI is not enabled")
        catalog = self._advanced_ai.spec.get("boss_directors", [])
        require(type(director_id) is str, "Invalid R37 director ID")
        director = next((row for row in catalog
                         if row["id"] == director_id), None)
        require(director is not None, "Unknown R37 boss director")
        require(self.mode == "battle" and self.battle is not None
                and self.battle.mission.id == director["mission"],
                "R37 boss director requires its own active CT encounter")
        from .ai_boss_director import preview_boss_director
        return preview_boss_director(self.battle, director)

    def ai_boss_replay_audit(self, director_id, *, command_budget=512):
        """R37.E3 certified preview from actual, bounded official Battle replay.

        No separate command history, simulated phase progression or write.
        A mismatch in tactical state OR boss signals fails closed.
        """
        require(type(command_budget) is int
                and 1 <= command_budget <= 512,
                "R37 boss audit requires a 1..512 command budget")
        current = self.ai_boss_preview(director_id)
        require(self.battle is not None
                and len(self.battle.commands) <= command_budget,
                "R37 boss audit exceeds its bounded command budget")
        from .engine import Battle
        from .ai_boss_director import preview_boss_director
        director = next(row for row in
                        self._advanced_ai.spec["boss_directors"]
                        if row["id"] == director_id)
        restored = Battle.replay(self.battle.recording(), rules=self.rules)
        require(restored.digest() == self.battle.digest(),
                "R37 boss audit found CT state replay divergence")
        reproduced = preview_boss_director(restored, director)
        require(current == reproduced,
                "R37 boss audit found telegraph/phase divergence")
        return {
            "version": 1, "director_id": director_id,
            "mission": self.battle.mission.id,
            "battle_digest": self.battle.digest(),
            "preview_digest": current["digest"],
            "commands_checked": len(self.battle.commands),
            "verified": True,
            "phase_events": deepcopy(current["observed_phase_events"]),
        }

    def ai_squad_preview(self, squad_id):
        """R37.D3 — direct same-scene radio sharing and role proposals only.

        Positions and signal strength are taken from canonical R35 projections
        and each actor's verified sensor/blackboard. No secondary NPC state,
        full-map omniscience or implicit gameplay command execution.
        """
        require(self._advanced_ai is not None,
                "R37 advanced AI is not enabled")
        from .ai_squad import coordinate_squad
        agents = sorted((
            row for row in self._advanced_ai.agents.values()
            if row.get("squad", {}).get("id") == squad_id),
            key=lambda row: row["id"])
        require(agents, "Unknown R37 authored squad")
        require(self.mode == "campaign" and self._living_world is not None
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending,
                "R37 squad requires active routed exploration")
        stage = self.exploration.state(self.progress, self.route_scene)
        require(not stage["completed"], "R37 squad scene is completed")
        members = []
        for agent in agents:
            actor_id = agent["id"]
            pose = self._living_world.npc_pose(
                actor_id, self.progress.story_flags)
            if pose["scene"] != self.route_scene or pose.get("pos") is None:
                continue
            perception = self.ai_perception_preview(actor_id)["perception"]
            values = self._advanced_ai.state(actor_id)["values"]
            fresh = perception["signal"]
            if fresh in ("seen", "heard"):
                known = list(perception["target"])
                signal = fresh
            elif (self._ai_suspicion(actor_id) > 0
                  and values.get("last_known_scene") == self.route_scene
                  and all(name in values
                          for name in ("last_known_x", "last_known_y"))):
                known = [values["last_known_x"], values["last_known_y"]]
                signal = "memory"
            else:
                known = None
                signal = "none"
            members.append({
                "actor_id": actor_id, "pos": list(pose["pos"]),
                "role": agent["squad"]["role"],
                "radio_range": agent["squad"]["radio_range"],
                "signal": signal, "known_pos": known,
            })
        require(members, "No R37 squad members are present in this scene")
        return coordinate_squad(stage, squad_id, members,
                                scene=self.route_scene,
                                tick=self._living_world.ticks)

    def ai_squad_share(self, squad_id):
        """Explicit atomic broadcast of *fresh* sightings to in-range peers.

        Each recipient is written at most once per world tick. The regular
        R37.B journal replay is the source of persistence; CT remains opt-out.
        """
        report = self.ai_squad_preview(squad_id)
        recipients = [
            row for row in report["members"]
            if row["shared_from"] is not None and
            row["received_signal"] in ("seen", "heard")]
        require(recipients, "R37 squad has no deliverable fresh radio signals")
        tick = report["tick"]
        for row in recipients:
            require(not any(
                event["actor_id"] == row["actor_id"]
                and event["tick"] == tick
                and "squad_source" in event["changes"]
                for event in self._advanced_ai.history),
                "R37 squad already notified an actor this tick")
        writes = []
        for row in sorted(recipients, key=lambda item: item["actor_id"]):
            signal = row["received_signal"]
            known = row["known_pos"]
            writes.append({
                "actor_id": row["actor_id"],
                "changes": {
                    "alert": True, "suspicion": 3 if signal == "seen" else 2,
                    "last_known_x": known[0], "last_known_y": known[1],
                    "last_known_scene": report["scene"],
                    "squad_source": row["shared_from"], "squad_signal": signal,
                },
            })
        saved = self._advanced_ai.remember_batch(writes, tick=tick)
        return {"preview": report, "delivered": [
            {"actor_id": row["actor_id"], "source": row["shared_from"]}
            for row in recipients], "blackboards": saved}

    def ai_decision_context(self, actor_id):
        """Derive observable facts from canonical CT or R35 exploration state.

        Never trust client-supplied facts for authoritative decision previews.
        No new AI simulation clock, LOS claims or campaign mutations.
        """
        require(self._advanced_ai is not None, "R37 advanced AI is not enabled")
        agent = self._advanced_ai.agent(actor_id)
        if agent["mode"] == "ct":
            require(self.mode == "battle" and self.battle is not None,
                    "CT AI requires an active tactical battle")
            actor = self.battle.unit(actor_id)
            require(actor.alive, "CT AI actor is not alive")
            from .model import distance
            opponents = sorted((unit for unit in self.battle.units
                                if unit.alive and unit.team != actor.team),
                               key=lambda unit: unit.id)
            facts = {"hp": actor.hp, "has_opponents": bool(opponents)}
            if opponents:
                facts["distance"] = min(distance(actor.pos, foe.pos)
                                        for foe in opponents)
            tick = self.battle.tick
        else:
            require(self.mode == "campaign" and self._living_world is not None
                    and self.scene_router.enabled
                    and self.route_scene in self.project.exploration
                    and not self.progress.story_pending,
                    "Realtime AI requires an active R35 exploration scene")
            pose = self._living_world.npc_pose(actor_id, self.progress.story_flags)
            same_scene = pose["scene"] == self.route_scene
            facts = {"activity": pose["activity"], "same_scene": same_scene}
            if same_scene and pose.get("pos") is not None:
                player = self.exploration.state(
                    self.progress, self.route_scene)["position"]
                npc = pose["pos"]
                facts["distance"] = abs(npc[0] - player[0]) + abs(npc[1] - player[1])
            tick = self._living_world.ticks
            if "squad" in agent:
                preview = self.ai_squad_preview(agent["squad"]["id"])
                own = next((row for row in preview["members"]
                            if row["actor_id"] == actor_id), None)
                if own is not None:
                    facts.update({
                        "squad_alert": own["known_pos"] is not None,
                        "squad_role": own["role"],
                        "squad_intent": own["intent"],
                        "squad_reachable": own["reachable"],
                    })
            if "sensor" in agent:
                memory = self._advanced_ai.state(actor_id)["values"]
                if same_scene and pose.get("pos") is not None:
                    perception = self.ai_perception_preview(actor_id)["perception"]
                    facts.update({
                        "enemy_visible": perception["visible"],
                        "noise_heard": perception["heard"],
                        "alert": perception["alert"],
                        "target_reachable": perception["reachable"],
                    })
                else:
                    facts.update({
                        "enemy_visible": False, "noise_heard": False,
                        "alert": self._ai_suspicion(actor_id) > 0,
                        "target_reachable": False,
                    })
        board = self._advanced_ai.state(actor_id)
        require(board["updated_tick"] <= tick,
                "R37 blackboard is newer than the canonical game clock")
        return {"schema_version": 1, "actor_id": actor_id,
                "mode": agent["mode"], "tick": tick,
                "seed": self.seed, "facts": facts}

    def ai_decision_preview(self, actor_id):
        """Read-only R37 policy explanation. Never invoke Battle.execute."""
        context = self.ai_decision_context(actor_id)
        return self._advanced_ai.preview(context)

    def ai_perception_preview(self, actor_id):
        """R37.D sensor from R35 NPC, canonical hero cell and verified R25 input.

        Does not dispatch combat moves, infer LOS from Manhattan distance,
        advance world time or mutate NPC memory.
        """
        require(self._advanced_ai is not None,
                "R37 advanced AI is not enabled")
        agent = self._advanced_ai.agent(actor_id)
        require(agent["mode"] == "realtime" and "sensor" in agent,
                "R37 perception requires an authored realtime sensor")
        require(self.mode == "campaign" and self._living_world is not None
                and self.scene_router.enabled
                and self.route_scene in self.project.exploration
                and not self.progress.story_pending,
                "R37 perception requires active routed exploration")
        stage = self.exploration.state(self.progress, self.route_scene)
        require(not stage["completed"], "R37 perception scene is completed")
        pose = self._living_world.npc_pose(actor_id, self.progress.story_flags)
        require(pose["scene"] == self.route_scene
                and pose.get("pos") is not None,
                "R37 NPC is not positioned in the player's scene")
        memory = self._advanced_ai.state(actor_id)["values"]
        prior = None
        if self._ai_suspicion(actor_id) > 0:
            if (memory.get("last_known_scene") == self.route_scene
                    and "last_known_x" in memory
                    and "last_known_y" in memory):
                prior = [memory["last_known_x"], memory["last_known_y"]]
        movement = False
        if self._rt_journal is not None:
            journal = self._rt_journal.recording()
            if journal["inputs"]:
                latest = journal["inputs"][-1]
                command = latest["command"]
                movement = (
                    latest["tick"] == self._rt_journal.tick
                    and latest["source"] == "hero"
                    and command["kind"] == "move"
                    and (command["dx"] != 0 or command["dy"] != 0))
        from .ai_perception import perceive_grid
        report = perceive_grid(stage, pose["pos"], stage["position"],
                               agent["sensor"], movement=movement,
                               remembered=prior)
        return {"actor_id": actor_id, "scene": self.route_scene,
                "tick": self._living_world.ticks, "perception": report}

    def ai_observe(self, actor_id):
        """Commit one explicit observation per actor/world tick to R37 ledger.

        Suspicion persists for three authored observations after sight and
        two after sound. Each later explicit observation without a signal
        decreases it once; there is no implicit frame-driven countdown.
        """
        report = self.ai_perception_preview(actor_id)
        tick = report["tick"]
        observation = report["perception"]
        require(not any(
            row["actor_id"] == actor_id and row["tick"] == tick
            and "observation_kind" in row["changes"]
            for row in self._advanced_ai.history),
            "R37 AI already observed this actor at this world tick")
        memory = self._advanced_ai.state(actor_id)["values"]
        signal = observation["signal"]
        suspicion = (3 if signal == "seen" else 2 if signal == "heard"
                     else max(0, self._ai_suspicion(actor_id) - 1))
        changes = {"suspicion": suspicion, "alert": suspicion > 0,
                   "observation_kind": signal,
                   "heard_noise": observation["heard"]}
        if signal != "none":
            changes["last_known_x"] = observation["target"][0]
            changes["last_known_y"] = observation["target"][1]
            changes["last_known_scene"] = report["scene"]
        updated = self._advanced_ai.remember(actor_id, changes, tick=tick)
        return {"observation": report, "blackboard": updated}

    def ai_remember(self, actor_id, changes):
        """Journal bounded R35 NPC memory against its authoritative world tick.

        CT policy inspection is supported; writable CT memory awaits an
        encounter-scoped replay adapter in R37.C to avoid tick-reset hazards.
        """
        context = self.ai_decision_context(actor_id)
        require(context["mode"] == "realtime",
                "CT memory writes require a future encounter-scoped adapter")
        require(type(changes) is dict and not (
                set(changes) & {
                    "squad_source", "squad_signal",
                    "last_known_scene", "observation_kind"}),
                "R37 sensor and squad provenance must come from observation APIs")
        return self._advanced_ai.remember(actor_id, changes,
                                          tick=context["tick"])

    def route_destinations(self):
        """R25 portals currently reachable by the Player, no alternate graph."""
        if (not self.scene_router.enabled or self.mode != "campaign"
                or self.progress.story_pending or self.tactical_story_pending):
            return []
        from .narrative import matches
        result = []
        for row in self.scene_router.links.values():
            if (row["source"] != self.route_scene
                    or ("when" in row and not matches(row["when"], self.progress))):
                continue
            scene = row["destination"]
            title = (self.project.exploration[scene]["title"]
                     if scene in self.project.exploration
                     else self.content.missions[scene].name)
            result.append({"id": row["id"], "destination": scene,
                           "title": title})
        return result

    def route_state(self):
        """Return the active exploration state from canonical Campaign flags."""
        require(self.scene_router.enabled, "Scene routing is not enabled")
        require(self.route_scene in self.project.exploration,
                "Current route is not an exploration scene")
        return self.exploration.state(self.progress, self.route_scene)

    def route_interact(self, point_id):
        """R25 routed exploration uses the canonical interaction flag ledger."""
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending
                and self.route_scene in self.project.exploration,
                "Routed exploration interactions require an active scene")
        return self.exploration.interact(self.progress, self.route_scene, point_id)

    def route_world_interact(self, object_id):
        """R44.C: activate a declared world object via canonical exploration.

        Only an existing non-exit interaction can change a world flag.
        GameSession remains the sole state owner and rollback authority.
        This is opt-in; historical R25/CT games are completely unchanged.
        """
        graph = self._world_graph
        require(graph is not None and self.scene_router.enabled
                and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending
                and self.route_scene in self.project.exploration,
                "R44: active routed exploration and WorldGraph required")
        require(type(object_id) is str, "R44: invalid object identifier")
        entry = next((row for row in graph.raw["objects"]
                      if row["scene"] == self.route_scene and row["id"] == object_id),
                     None)
        require(entry is not None and entry["kind"] in ("chest", "door", "switch"),
                "R44: object is not an activatable exploration interaction")
        point = next((row for row in self.project.exploration[self.route_scene]
                      ["interactions"] if row["id"] == object_id), None)
        require(point is not None and point["exit"] is False,
                "R44: persistent objects must use an authored non-exit hotspot")
        flag = entry["flag"]
        activated = self.progress.story_flags.get(flag, False)
        require(type(activated) is bool, "R44: invalid persistent object flag")
        # Resolve position/proximity even for a repeated action.
        stage = self.route_state()
        require(sum(abs(a - b) for a, b in zip(stage["position"], point["pos"])) <= 1,
                "R44: move closer to activate the object")
        if activated:
            return {"id": object_id, "world_flag": flag,
                    "already_activated": True, "finished": False}
        previous = deepcopy(self.progress)
        try:
            # This object is already verified as a non-exit authored hotspot.
            # Completed atlas regions remain explorable on return; legacy R25
            # interactions still reject completed scenes by default.
            result = self.exploration.interact(
                self.progress, self.route_scene, object_id, allow_completed=True)
            self.progress.story_flags[flag] = True
            return {**result, "world_flag": flag, "already_activated": False}
        except Exception:
            self.progress = previous
            raise

    def route_world_transition(self, link_id):
        """R44: enforce an atlas exit hotspot before delegating to SceneRouter.

        This opt-in action does not bypass the R25 route condition or mission
        lifecycle. It records only the canonical R25 history in the checkpoint.
        """
        require(type(link_id) is str and self._world_graph is not None,
                "R44: configured atlas portal required")
        require(self.mode == "campaign"
                and self.route_scene in self.project.exploration,
                "R44: travel requires active routed exploration")
        portal = self._world_graph.inspect_portal(
            self.route_scene, link_id, self.progress)
        position = self.route_state()["position"]
        require(sum(abs(a - b) for a, b in zip(position, portal["source"])) <= 1,
                "R44: approach the authored exit before traveling")
        return self.route_transition(link_id)

    def route_move(self, dx, dy):
        """Legacy cardinal exploration remains available before free movement starts."""
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and self._rt_journal is None,
                "Resolve encounter or free movement before cardinal movement")
        return self.exploration.move(
            self.progress, self.route_scene, dx, dy,
            allow_completed=self._world_graph is not None)

    def route_realtime_state(self):
        """Detached subcell position for Player/Studio; no Qt dependency."""
        from .fixed_realtime import FreeMovement
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and self.route_scene in self.project.exploration
                and self.scene_profile(self.route_scene)["movement"] == "FREE_REALTIME",
                "No active free movement scene")
        stage = self.exploration.state(self.progress, self.route_scene)
        require(not stage["completed"], "Exploration stage already completed")
        movement = FreeMovement(stage)
        position = (list(self._rt_position) if self._rt_position is not None
                    else movement.center(stage["position"]))
        return {"scene": self.route_scene, "position": position,
                "cell": movement.cell(position),
                "tick": self._rt_journal.tick if self._rt_journal else 0}

    def route_realtime_step(self, dx=0, dy=0):
        """Apply exactly one fixed simulation tick; no wall-clock delta accepted.

        A failed command leaves both the journal and Campaign unchanged.
        The FixedTickJournal is local to the active exploration scene.
        """
        from .fixed_clock import FixedTickJournal
        from .fixed_realtime import FreeMovement
        require(self._platform is None and self._action is None,
                "Cannot mix R25 and R26/R32 movement")
        current = self.route_realtime_state()
        require(type(dx) is int and type(dy) is int
                and dx in (-1, 0, 1) and dy in (-1, 0, 1),
                "Invalid free movement input")
        if self._living_world is not None:
            self._living_world.preflight(1)
        # Preview the canonical systems tick before mutating Campaign position
        # or movement replay. A rejected economy budget leaves both unchanged.
        staged_system = deepcopy(self._systems) if self._systems is not None else None
        if staged_system is not None:
            staged_system.advance(1)
        # R63 uses the same fixed frame and staged transaction as R55.
        staged_survival = deepcopy(self._survival) if self._survival is not None else None
        if staged_survival is not None:
            staged_survival.advance(1)
        scene = current["scene"]
        movement = FreeMovement(self.project.exploration[scene])
        origin = (list(self._rt_origin) if self._rt_origin is not None
                  else list(current["position"]))
        # A private journal copy makes input submission and step atomic even
        # if a handler, digest, or validation unexpectedly fails.
        journal = (deepcopy(self._rt_journal) if self._rt_journal is not None
                   else FixedTickJournal(rate=60, seed=self.seed))
        pos = list(current["position"])
        journal.submit(journal.tick + 1, "hero",
                       {"kind": "move", "dx": dx, "dy": dy})
        def handler(tick, commands):
            nonlocal pos
            for event in commands:
                require(event["source"] == "hero", "Unknown free movement source")
                cmd = event["command"]
                require(set(cmd) == {"kind", "dx", "dy"}
                        and cmd["kind"] == "move",
                        "Invalid free movement command")
                pos = movement.advance(pos, cmd["dx"], cmd["dy"])
            return {"scene": scene, "position": list(pos)}
        snapshot = journal.step(handler)
        from .exploration import _key
        cell = movement.cell(snapshot["position"])
        self.progress.story_flags[_key(scene, "pos")] = ",".join(map(str, cell))
        self._rt_origin, self._rt_position, self._rt_journal = (
            origin, snapshot["position"], journal)
        if self._living_world is not None:
            self._living_world.advance(1)
            if self._farming is not None:
                self._farming.sync(self._living_world.day)
            if self._relationships is not None:
                self._relationships.sync(self._living_world.day)
        if staged_system is not None:
            self._systems = staged_system
        if staged_survival is not None:
            self._survival = staged_survival
        return self.route_realtime_state()

    def route_action_state(self):
        """Read an R26 combat snapshot for the active routed action scene."""
        from .action_runtime import ActionRuntime
        from .action_scene_adapter import authored_action_scene
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending
                and self.route_scene in self.project.exploration
                and self._rt_journal is None and self._platform is None,
                "R26 combat requires a routed, idle action exploration scene")
        scene = authored_action_scene(self.project, self.route_scene)
        from .action_settlement import settlement_keys
        done, _ = settlement_keys(self.route_scene)
        require(self.progress.story_flags.get(done) is not True,
                "R26 combat already settled; reward replay is one-shot")
        return (self._action.snapshot() if self._action is not None else
                ActionRuntime(scene).snapshot())

    def route_action_step(self, command):
        """Run exactly one deterministic R26 tick, committed by PlayerController.

        The action journal is an opt-in field of canonical GameSession, not
        a separate save slot. Invalid commands never mutate this session.
        """
        from .action_runtime import ActionRuntime
        from .action_scene_adapter import authored_action_scene
        self.route_action_state()
        scene = authored_action_scene(self.project, self.route_scene)
        runtime = self._action
        if runtime is None:
            runtime = ActionRuntime(scene)
        else:
            require(runtime.scene == scene, "Action scene changed during gameplay")
        events = runtime.step(command)
        self._action = runtime
        return {"state": runtime.snapshot(), "events": events}

    def route_action_settle(self, link_id):
        """Settle a genuine R26 victory and cross an R25 route atomically."""
        from .action_settlement import (
            MAX_SETTLEMENTS, settlement_keys, victory_coins,
        )
        require(self._action is not None and self.mode == "campaign" and
                len(self._action_settlements) < MAX_SETTLEMENTS,
                "No active R26 combat or settlement capacity exhausted")
        source = self.route_scene
        done, coin_flag = settlement_keys(source)
        require(done not in self.progress.story_flags and
                coin_flag not in self.progress.story_flags,
                "R26 combat rewards have already been paid")
        coins = victory_coins(self._action)
        require(self.progress.gold + coins <= 1000000000,
                "R26 reward exceeds the campaign gold budget")
        route = self.scene_router.destination(source, link_id, self.progress)
        require(route["source"] == source, "R26 exit must start in action scene")
        record = {
            "version": 1, "scene": source, "link": link_id,
            "route_index": len(self.route_history),
            "coin": coins, "runtime": self._action.recording(),
        }
        before = deepcopy((
            self.progress, self.battle, self.fronts, self.finalized,
            self.settled_fronts, self.siege_id, self.route_scene,
            self.route_history, self.tactical_story_pending,
            self.tactical_story_queue, self._rt_origin, self._rt_position,
            self._rt_journal, self._platform, self._action,
            self._action_settlements,
        ))
        try:
            self.progress.gold += coins
            self.progress.story_flags[done] = True
            self.progress.story_flags[coin_flag] = coins
            self._action_settlements.append(record)
            self._action = None
            moved = self.route_transition(link_id)
            return {"route": moved, "coins_awarded": coins,
                    "campaign_gold": self.progress.gold,
                    "settled_scene": source}
        except Exception:
            (self.progress, self.battle, self.fronts, self.finalized,
             self.settled_fronts, self.siege_id, self.route_scene,
             self.route_history, self.tactical_story_pending,
             self.tactical_story_queue, self._rt_origin, self._rt_position,
             self._rt_journal, self._platform, self._action,
             self._action_settlements) = before
            raise

    def _platform_definition(self):
        """Resolve geometry only for a routed free-movement authored scene."""
        from .physics_scenes import EXTENSION
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending
                and self.route_scene in self.project.exploration
                and self.scene_profile(self.route_scene)["movement"] == "FREE_REALTIME"
                and self._rt_journal is None
                and self._action is None,
                "Physics requires an active routed free-movement scene")
        extension = self.project.extensions.get(EXTENSION, {})
        authored = extension.get("data", {}).get("scenes", {}).get(self.route_scene)
        require(authored is not None, "Scene has no R32 physics definition")
        return authored

    def _platform_flag(self, collider):
        payload = (self.route_scene + ":" + collider).encode("utf-8")
        return "r32_open_" + hashlib.sha256(payload).hexdigest()[:24]

    def _metroidvania_abilities(self):
        """R33 authored grants resolved exclusively from earned Campaign flags."""
        spec = self.project.extensions.get("drawtemp.metroidvania")
        if spec is None:
            return frozenset()
        graph = spec["data"]
        abilities = set(graph["starting_capabilities"])
        for pickup in graph["pickups"]:
            if self.progress.story_flags.get("r33_pickup_" + pickup["id"]) is True:
                abilities.update(pickup["grants"])
        return frozenset(abilities)

    def _metroidvania_air_jumps(self):
        """One opt-in R33 ability in canonical Campaign flags, never CT."""
        return int("double_jump" in self._metroidvania_abilities())

    def _metroidvania_collect(self, events):
        """Accept a pickup only when the real R32 trigger was entered."""
        spec = self.project.extensions.get("drawtemp.metroidvania")
        if spec is None:
            return
        room = self.route_scene
        candidates = {p["id"] for p in spec["data"]["pickups"] if p["room"] == room}
        entered = {event["collider"] for event in events
                   if event["kind"] == "trigger_enter"}
        for pickup in candidates & entered:
            self.progress.story_flags["r33_pickup_" + pickup] = True
        if "waystone" in entered:
            from .exploration import _key
            authored = self.project.exploration.get(room, {}).get(
                "interactions", [])
            if any(point["id"] == "waystone" for point in authored):
                self.progress.story_flags[_key(room, "waystone")] = True

    def _active_platform(self):
        from .platform_physics import PlatformPhysics
        authored = self._platform_definition()
        if self._platform is None:
            opened = [row["opens"] for row in authored["colliders"]
                      if "opens" in row and
                      self.progress.story_flags.get(self._platform_flag(row["opens"])) is True]
            self._platform = PlatformPhysics(
                authored, initial_disabled=sorted(set(opened)),
                max_air_jumps=self._metroidvania_air_jumps())
        return self._platform

    def route_platform_state(self):
        """Detached state projection for Player/Studio; no frame-clock input."""
        return self._active_platform().snapshot()

    def route_platform_step(self, move=0, jump=False, interact=False, attack=False):
        """Exactly one fixed step; rewards and door flags belong to Campaign."""
        # R55: stage a fixed-tick platform step with the economy.
        runtime = deepcopy(self._active_platform())
        if self._living_world is not None:
            self._living_world.preflight(1)
        staged_system = deepcopy(self._systems) if self._systems is not None else None
        if staged_system is not None:
            staged_system.advance(1)
        staged_survival = deepcopy(self._survival) if self._survival is not None else None
        if staged_survival is not None:
            staged_survival.advance(1)
        command = {"tick": runtime.tick + 1, "move": move,
                   "jump": jump, "interact": interact}
        if "boss" in runtime.scene:
            command["attack"] = attack
        else:
            require(type(attack) is bool and not attack,
                    "Attack requires an authored R40 platform boss")
        events = runtime.step(command)
        for event in events:
            if event["kind"] == "door_open":
                self.progress.story_flags[self._platform_flag(event["collider"])] = True
        self._metroidvania_collect(events)
        for event in events:
            if event["kind"] == "boss_defeated":
                from .exploration import _key
                self.progress.story_flags[_key(self.route_scene, "boss_defeated")] = True
        if self._living_world is not None:
            self._living_world.advance(1)
            if self._farming is not None:
                self._farming.sync(self._living_world.day)
            if self._relationships is not None:
                self._relationships.sync(self._living_world.day)
        self._platform = runtime
        if staged_system is not None:
            self._systems = staged_system
        if staged_survival is not None:
            self._survival = staged_survival
        return {"state": runtime.snapshot(), "events": events}

    def route_platform_travel(self, link_id):
        """Allow an existing R25 portal only while its R32 trigger is occupied."""
        require(type(link_id) is str and
                link_id in self._active_platform().available_routes(),
                "Player is not inside the requested portal")
        return self.route_transition(link_id)

    def route_transition(self, link_id):
        """One atomic navigation command; tactical startup uses the real CT core."""
        from .scene_router import MAX_HISTORY
        require(self.scene_router.enabled and self.mode == "campaign"
                and not self.progress.story_pending
                and not self.tactical_story_pending
                and self._action is None,
                "Resolve encounter, action combat or dialogue before changing scenes")
        require(len(self.route_history) < MAX_HISTORY,
                "Scene transition history limit reached")
        from .action_scene_adapter import EXTENSION as ACTION_EXTENSION
        from .action_settlement import settlement_keys
        if self.route_scene in self.project.extensions.get(
                ACTION_EXTENSION, {}).get("data", {}).get("scenes", {}):
            done, _ = settlement_keys(self.route_scene)
            require(self.progress.story_flags.get(done) is True,
                    "Complete and settle action combat before exiting its scene")
        route = self.scene_router.destination(self.route_scene, link_id, self.progress)
        # R33 ability-gated route requirements are explicit project data.
        # For authored physical gates, enforce actual R32 overlap too;
        # narrative-only links retain their earlier R25 behavior.
        metroidvania = self.project.extensions.get("drawtemp.metroidvania")
        if metroidvania is not None:
            gated = [row for row in metroidvania["data"]["links"]
                     if row["id"] == link_id and row["requires"]]
            for row in gated:
                require(row["source"] == self.route_scene and
                        row["destination"] == route["destination"],
                        "R33 gate does not match the authored scene route")
                require(set(row["requires"]) <= self._metroidvania_abilities(),
                        "R33 scene gate requires an earned capability")
        # Every authored physical portal requires actual R32 overlap,
        # including non-ability routes. Prevent old narrative APIs from
        # bypassing the Player's physical movement and collision system.
        physical = (self.project.extensions.get("drawtemp.physics", {})
                    .get("data", {}).get("scenes", {})
                    .get(self.route_scene, {}))
        portals = {c["route"] for c in physical.get("colliders", [])
                   if "route" in c}
        if link_id in portals:
            require(self._platform is not None and
                    link_id in self._platform.available_routes(),
                    "Physical scene route requires actual R32 portal contact")
        before = deepcopy((self.progress, self.battle, self.fronts, self.finalized,
                           self.settled_fronts, self.siege_id, self.route_scene,
                           self.route_history, self.tactical_story_pending,
                           self.tactical_story_queue, self._rt_origin,
                           self._rt_position, self._rt_journal, self._platform,
                           self._stream_world))
        try:
            dest = route["destination"]
            if dest in self.content.missions:
                self._route_starting = True
                try:
                    self.start_mission(dest)
                finally:
                    self._route_starting = False
            else:
                from .exploration import _key
                # Use existing Campaign.story_flags, never a second world save.
                self.progress.story_flags[_key(dest, "pos")] = ",".join(
                    map(str, route["spawn"]))
                self.exploration.state(self.progress, dest)
            self.route_scene = dest
            if self._stream_world is not None:
                self._stream_world.enter_scene(dest)
            self.route_history.append(route["id"])
            # The next exploration segment starts a fresh tick log.
            # R25.E will certify continuous replay spanning mode boundaries.
            self._rt_origin = None
            self._rt_position = None
            self._rt_journal = None
            self._platform = None
            return {"scene": dest, "profile": self.scene_profile(dest),
                    "spawn": list(route["spawn"]), "mode": self.mode}
        except Exception:
            (self.progress, self.battle, self.fronts, self.finalized,
             self.settled_fronts, self.siege_id, self.route_scene,
             self.route_history, self.tactical_story_pending,
             self.tactical_story_queue, self._rt_origin,
             self._rt_position, self._rt_journal, self._platform,
             self._stream_world) = before
            raise

    def route_abandon_ct(self, link_id):
        """Explicitly abandon an R25-routed CT battle and return atomically.

        Abandoned battles pay no tactical reward. Both the battle removal
        and route navigation are rolled back on a rejected or failed exit.
        The Player facade persists the resulting GameSession once.
        """
        require(self.scene_router.enabled and self.mode == "battle"
                and self.route_scene in self.content.missions
                and not self.tactical_story_pending,
                "Only a routed, active CT encounter can be abandoned")
        # Validate destination before the mutation, including narrative gates.
        route = self.scene_router.destination(
            self.route_scene, link_id, self.progress)
        require(route["destination"] in self.project.exploration,
                "CT abandonment must return to authored exploration")
        before = deepcopy((
            self.progress, self.battle, self.fronts, self.finalized,
            self.settled_fronts, self.siege_id, self.route_scene,
            self.route_history, self.tactical_story_pending,
            self.tactical_story_queue, self._rt_origin, self._rt_position,
            self._rt_journal, self._platform, self._action,
            self._action_settlements,
        ))
        try:
            self.abandon_encounter()
            return self.route_transition(link_id)
        except Exception:
            (self.progress, self.battle, self.fronts, self.finalized,
             self.settled_fronts, self.siege_id, self.route_scene,
             self.route_history, self.tactical_story_pending,
             self.tactical_story_queue, self._rt_origin, self._rt_position,
             self._rt_journal, self._platform, self._action,
             self._action_settlements) = before
            raise

    def _tactical_story_progress(self):
        require(bool(self.tactical_story_pending), "No tactical dialogue pending")
        require(not self.progress.story_pending,
                "Cannot overlap campaign and tactical dialogue")
        projected = deepcopy(self.progress)
        projected.story_pending = self.tactical_story_pending
        return projected

    def tactical_scene(self):
        return self.story.active_scene(self._tactical_story_progress())

    def tactical_choices(self):
        return self.story.choices(self._tactical_story_progress())

    def _queue_tactical_story(self, battle, old_fired=(), old_event_count=None):
        """Consume each new event firing, including opt-in repeat pages.

        Mission initialisation retains the historical first-fired-ID logic.
        During an authenticated command the journal slice is authoritative:
        a repeated trigger ID produces a NEW dialogue presentation without
        duplicating the old one-shot event or a restored save.
        """
        if battle is None or self.fronts is not None:
            return
        if old_event_count is None:
            seen = set(old_fired)
            ids = [eid for eid in battle.fired if eid not in seen]
        else:
            ids = [row["id"] for row in battle.events[old_event_count:]
                   if row["kind"] == "trigger"]
        for event_id in ids:
            target = f"{battle.mission.id}/{event_id}"
            scene = self.story.during_tactical_event.get(target)
            if scene:
                self.tactical_story_queue.append(scene)
        if not self.tactical_story_pending and self.tactical_story_queue:
            self.tactical_story_pending = self.tactical_story_queue.pop(0)

    def choose_tactical_story_option(self, choice_id):
        """Atomically apply canonical StoryBook choice and resume the Battle."""
        require(self.mode == "battle", "No standalone tactical dialogue")
        require(self.battle is not None, 'Missing tactical battle')
        self._require_narrative_line_complete()
        previous = deepcopy((self.progress, self.battle,
                             self.tactical_story_pending,
                             self.tactical_story_queue, self.finalized))
        try:
            projected = self._tactical_story_progress()
            scene_id = projected.story_pending
            selected = next((c for c in self.story.choices(projected)
                             if c['id'] == choice_id), None)
            require(selected is not None, 'Choice is unavailable')
            updated = self.story.choose(projected, choice_id)
            # Every tactical choice has a journal entry, including an empty
            # tactical-effects list. This makes replay and story history agree.
            before_fired = tuple(self.battle.fired)
            before_event_count = len(self.battle.events)
            self.battle.execute({
                'kind': 'story_effects', 'scene': scene_id,
                'choice': choice_id,
                'effects': deepcopy(selected.get('tactical_effects', [])),
            })
            self._queue_tactical_story(
                self.battle, before_fired, before_event_count)
            next_scene = updated.story_pending
            updated.story_pending = ""
            self.progress = updated
            self.tactical_story_pending = (next_scene or
                                           (self.tactical_story_queue.pop(0)
                                            if self.tactical_story_queue else ""))
            if not self.tactical_story_pending:
                self._settle()
            return self.tactical_scene() if self.tactical_story_pending else None
        except Exception:
            (self.progress, self.battle, self.tactical_story_pending,
             self.tactical_story_queue, self.finalized) = previous
            raise

    def _scene_cinematic_key(self, clip):
        """Stable per-visit acknowledgement inside the existing verified save.

        Scope by the narrative decision count AND mission completion count:
        returning to a scene in a later chapter plays its clip again. No
        parallel save ledger and no untrusted cinematic callbacks.
        """
        scene = self.active_scene()
        require(scene is not None, "No cinematic narrative scene")
        identity = (self.campaign_id + "|" + scene["id"] + "|" + clip["id"]
                    + "|" + str(len(self.progress.story_history))
                    + "|" + str(len(self.progress.completed)))
        return "cine_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def pending_scene_cinematic(self):
        """First unacknowledged scene clip, pure projection (no clock)."""
        if self.mode != "campaign":
            return None
        scene = self.active_scene()
        if scene is None:
            return None
        from .cinematics import matching_cinematics
        for clip in matching_cinematics(self.project, "scene", scene["id"]):
            if self.progress.story_flags.get(self._scene_cinematic_key(clip)) is not True:
                return clip
        return None

    def acknowledge_scene_cinematic(self, clip_id):
        """Mark only the next currently visible clip as played or skipped.

        Acknowledgement is part of Campaign.story_flags and is serialised by
        normal GameSession recording. No narrative effects, rewards or Battle
        commands are executed here. Simulation supplies rollback/revisions.
        """
        require(isinstance(clip_id, str), "Invalid cinematic identifier")
        clip = self.pending_scene_cinematic()
        require(clip is not None and clip["id"] == clip_id,
                "Cinematic is not the next active clip")
        key = self._scene_cinematic_key(clip)
        require(key not in self.progress.story_flags, "Cinematic already acknowledged")
        require(len(self.progress.story_flags) < 1000,
                "Campaign flag budget exhausted")
        self.progress.story_flags[key] = True
        return self.pending_scene_cinematic()

    def exploration_state(self):
        scene = self.active_scene()
        return self.exploration.state(self.progress, scene["id"]) if scene else None

    def explore_move(self, dx, dy):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.move(self.progress, scene["id"], dx, dy)

    def explore_interact(self, point_id):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.interact(self.progress, scene["id"], point_id)

    def explore_wait(self):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.wait(self.progress, scene["id"])

    def explore_actor(self, actor_id, action):
        require(self.mode == "campaign", "Exploration unavailable during combat")
        scene = self.active_scene()
        require(scene is not None, "No active narrative scene")
        return self.exploration.actor_action(self.progress, scene["id"],
                                             actor_id, action)

    def world_state(self):
        """Read the party cursor without mutating an old campaign slot."""
        return WorldJourney(self.project.world, self.content,
                            self.project.campaign(self.campaign_id)).state(self.progress)

    def world_destination(self, mission_id):
        require(self.mode == "campaign" and not self.progress.story_pending
                and self.active_scene() is None,
                "Resolve combat and narrative scenes before traveling")
        return WorldJourney(self.project.world, self.content,
                            self.project.campaign(self.campaign_id)).destination(
                                self.progress, mission_id)

    def world_advance(self):
        require(self.mode == "campaign" and not self.progress.story_pending
                and self.active_scene() is None,
                "Resolve combat and narrative scenes before traveling")
        journey = WorldJourney(self.project.world, self.content,
                               self.project.campaign(self.campaign_id))
        state = journey.advance(self.progress)
        event = journey.event_at(self.progress)
        if event is not None:
            require(event["scene"] in self.story.scenes,
                    "Unresolved world story scene")
            self.progress.story_flags["world_evt_" + event["id"]] = True
            self.progress.story_flags[PENDING] = event["id"]
            self.progress.story_pending = event["scene"]
        return state

    def world_can_enter(self, mission_id):
        return (self.mode == "campaign" and
                mission_id in self.available_missions() and
                WorldJourney(self.project.world, self.content,
                             self.project.campaign(self.campaign_id)).can_enter(
                                 self.progress, mission_id))

    def available_choices(self):
        stage = self.exploration_state()
        if stage is not None and not stage["completed"]:
            return []
        return self.story.choices(self.progress)

    def available_missions(self):
        if self.progress.story_pending:
            return []
        return flow_available_missions(self.progress, self.project.campaign_flow)

    def campaign_inspector(self):
        """Read-only persistent variables, companions, gates and endings."""
        return flow_inspect_campaign(self.progress, self.project.campaign_flow)

    def choose_story_option(self, choice_id):
        self._require_narrative_line_complete()
        require(self.active_battle is None or self.active_battle.result is not None,
                "Finish combat before choosing dialogue")
        stage = self.exploration_state()
        require(stage is None or stage["completed"], "Explore the area first")
        active = self.active_scene()
        event_id = self.progress.story_flags.get(PENDING, "")
        event = None
        if event_id:
            event = next((item for item in self.project.world.get("events", [])
                          if item["id"] == event_id), None)
            require(event is not None and active is not None and
                    active["id"] == event["scene"],
                    "Pending world event does not match narrative scene")
        updated = self.story.choose(self.progress, choice_id)
        if event is not None:
            next_scene = updated.story_pending
            # Validate the pending road checkpoint while choosing a route;
            # StoryBook may already have switched to a chained next_scene.
            updated.story_pending = active["id"]
            WorldJourney(self.project.world, self.content,
                         self.project.campaign(self.campaign_id)).redirect(
                             updated, event, choice_id)
            updated.story_pending = next_scene
        self.progress = updated
        return self.active_scene()

    def available_sieges(self):
        """Describe authored plans for the current campaign without unlocking missions."""
        available = set(self.available_missions()) if self.mode == "campaign" else set()
        return [
            {"id": bp["id"], "fronts": len(bp["fronts"]),
             "locked": sorted(set(bp["fronts"].values()) - available),
             "ready": (self.mode == "campaign"
                       and len(set(bp["fronts"].values())) == len(bp["fronts"])
                       and set(bp["fronts"].values()) <= available)}
            for bp in self.project.sieges
            if bp["campaign_id"] == self.campaign_id
        ]

    def start_configured_siege(self, siege_id):
        """Start one saved Studio blueprint through normal campaign/roster gates."""
        require(self.mode == "campaign", "End the current encounter first")
        blueprint = next((bp for bp in self.project.sieges
                          if bp["id"] == siege_id and
                          bp["campaign_id"] == self.campaign_id), None)
        require(blueprint is not None, "Unknown siege in this campaign")
        mids = list(blueprint["fronts"].values())
        require(len(set(mids)) == len(mids), "Siege fronts require distinct missions")
        missing = sorted(set(mids) - set(self.available_missions()))
        require(not missing, "Siege missions are locked: " + ", ".join(missing))
        # No parallel rules or save format: use the same validated GameSession.
        self.start_fronts(blueprint["fronts"], blueprint["focused"],
                          specs=blueprint["specs"], links=blueprint["links"],
                          logistics=blueprint.get("logistics"),
                          campaign=blueprint["campaign"],
                          event_graph=blueprint.get("event_graph"))
        self.siege_id = siege_id
        return self.fronts

    def _battle_support(self, mission_id):
        total = 0
        for spec in self.project.battle_support:
            value = self.progress.story_flags.get(spec["flag"], 0)
            require(type(value) is int, "Battle support flag must be an integer")
            if spec["mission"] == mission_id and value >= spec["gte"]:
                total += spec["potion_bonus"]
        if not total:
            return None
        # Use the standard replay-verified Battle.initial_state contract;
        # no out-of-band mutations after Battle was constructed.
        require(total <= 30, "Battle support exceeds supply cap")
        return {"inventory": {"potion": 3 + total, "ether": 2, "phoenix": 1}}

    def _can_edit_hero_equipment(self, uid):
        """Only canonical playable heroes, only outside tactical encounters."""
        require(self.mode == "campaign" and not self.tactical_story_pending,
                "Finish the current encounter before changing equipment")
        require(not self.progress.story_pending and self.active_scene() is None,
                "Finish dialogue/exploration before changing equipment")
        require(isinstance(uid, str) and bool(uid),
                "Hero ID is required")
        roster = {unit.id for mission in self.content.missions.values()
                  for unit in mission.units if unit.team == "player"}
        require(uid in roster, "Unknown playable hero")
        if self._classic_party is not None:
            require(uid in self._classic_party.members,
                    "Cannot equip an unrecruited RPG party member")

    def equip_hero(self, uid, item_id):
        """Delegate inventory/slot/ownership rules to the existing Campaign."""
        self._can_edit_hero_equipment(uid)
        self.progress.equip(self.content, uid, item_id)

    def unequip_hero(self, uid, slot):
        """Return a canonical equipped item to the persistent inventory."""
        self._can_edit_hero_equipment(uid)
        require(slot in ("weapon", "armor", "accessory"),
                "Unknown equipment slot")
        self.progress.unequip(uid, slot)

    def start_mission(self, mission_id):
        require(not self.scene_router.enabled or self._route_starting,
                "Routed projects must enter battles through a scene transition")
        require(self.mode == "campaign", "End the current encounter first")
        require(mission_id in self.available_missions(), "Mission is locked")
        # Enforce arrival at a visible world location at the headless boundary:
        # UI controls alone must not bypass an interrupted route event.
        state = self.world_state()
        if state is not None and any(
                node["mission"] == mission_id
                for node in self.project.world["nodes"]):
            require(self.world_can_enter(mission_id),
                    "Travel to the mission location before starting combat")
        # Campaign.prepare can materialize heroes: use a throwaway roster.
        battle = deepcopy(self.progress).prepare(
            self.content, mission_id, seed=self.seed, ruleset=self.rules,
            initial_state=self._battle_support(mission_id))
        self.battle, self.finalized = battle, False
        self._queue_tactical_story(battle)
        if not self.tactical_story_pending:
            self._settle()
        return battle

    def start_fronts(self, missions, focused, *, specs=None, links=None,
                     logistics=None, campaign=None, event_graph=None):
        require(not self.scene_router.enabled,
                "Routed multi-front sessions are not supported yet")
        require(self.mode == "campaign", "End the current encounter first")
        require(isinstance(missions, dict) and bool(missions) and focused in missions,
                "Invalid front mapping")
        available = set(self.available_missions())
        require(all(isinstance(name, str) and bool(name) and
                    isinstance(mid, str) and mid in available
                    for name, mid in missions.items()), "Front mission is locked")
        require(len(set(missions.values())) == len(missions),
                "Duplicate mission in fronts")
        prepared = deepcopy(self.content)
        for mid in missions.values():
            battle = deepcopy(self.progress).prepare(
                self.content, mid, seed=self.seed, ruleset=self.rules)
            # Battle.mission is live; Battle.content still holds authored units.
            prepared.missions[mid] = deepcopy(battle.content.missions[mid])
        self.fronts = MultiFrontSession(
            prepared, missions, focused, seed=self.seed, rules=self.rules,
            specs=specs, links=links, logistics=logistics, campaign=campaign,
            event_graph=event_graph)
        self.settled_fronts.clear()
        self.siege_id = None
        self.tactical_story_pending = ""
        self.tactical_story_queue.clear()
        return self.fronts

    def _commit(self, battle):
        updated = deepcopy(self.progress)
        route = battle.result == "victory" and battle.mission.id in self.story.after
        changed = updated.finish(battle, unlock_next=not route)
        if changed and route:
            self.story.after_victory(updated, battle.mission.id)
        updated = settle_campaign_flow(updated, self.project.campaign_flow,
                                      battle.mission.id, battle.result,
                                      content=self.content)
        # Author-declared mapping; source is the authenticated Battle journal.
        # This runs after the existing rewards and inside execute() rollback.
        from .logic_campaign_bridge import apply_bridge
        updated = apply_bridge(updated, self.project, battle)
        self.progress = updated

    def _settle(self):
        # A battle may reach victory on the same tick as a dialogue trigger:
        # defer settlement/reward and any after-victory scene until selection.
        if self.tactical_story_pending:
            return
        if self.fronts is not None:
            for front, battle in self.fronts.battles.items():
                if front not in self.settled_fronts and battle.result in ("victory", "defeat"):
                    self._commit(battle)
                    self.settled_fronts.add(front)
        elif self.battle is not None and not self.finalized and self.battle.result in ("victory", "defeat"):
            self._commit(self.battle)
            self.finalized = True

    def execute(self, command):
        require(self.active_battle is not None, "No tactical combat")
        require(isinstance(command, dict)
                and command.get('kind') != 'story_effects',
                'Story effects must come from a validated narrative choice')
        require(not self.progress.story_pending and not self.tactical_story_pending,
                "Resolve pending dialogue first")
        before_fired = set(self.active_battle.fired) if self.fronts is None else set()
        before_event_count = (len(self.active_battle.events)
                              if self.fronts is None else None)
        before = deepcopy((self.progress, self.battle, self.fronts,
                           self.finalized, self.settled_fronts,
                           self.tactical_story_pending, self.tactical_story_queue))
        try:
            if self.fronts is not None:
                if self.fronts.recovery_battles:
                    front = sorted(self.fronts.recovery_battles)[0]
                    self.fronts.execute_recovery(front, command)
                else:
                    self.fronts.execute(command)
            else:
                require(not self.finalized, "Combat already completed")
                self.battle.execute(command)
                self._queue_tactical_story(
                    self.battle, before_fired, before_event_count)
            self._settle()
        except Exception:
            (self.progress, self.battle, self.fronts,
             self.finalized, self.settled_fronts,
             self.tactical_story_pending, self.tactical_story_queue) = before
            raise
        return self.active_battle

    def switch_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.switch(front)
        return self.active_battle

    def advance_fronts(self):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        before = deepcopy((self.progress, self.fronts, self.settled_fronts))
        try:
            state = self.fronts.advance()
            self._settle()
        except Exception:
            self.progress, self.fronts, self.settled_fronts = before
            raise
        return state

    def set_doctrine(self, front, doctrine):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.set_doctrine(front, doctrine)

    def select_route(self, route):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.select_route(route)

    def negotiate_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.negotiate_front(front)

    def partial_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.partial_front(front)

    def withdraw_front(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.withdraw_front(front)

    def start_recovery(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.start_recovery(front)

    def abandon_recovery(self, front):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        self.fronts.abandon_recovery(front)

    def send_reserves(self, destination, actors):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.send_reserves(destination, actors)

    def transfer_units(self, destination, placements):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.transfer_units(destination, placements)

    def escort_convoy(self, convoy_id):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.escort_convoy(convoy_id)

    def rescue_convoy(self, convoy_id):
        require(self.fronts is not None and not self.progress.story_pending,
                "No available multi-front encounter")
        return self.fronts.rescue_convoy(convoy_id)

    def ai_turn(self):
        require(self.mode == "battle" and not self.finalized and
                not self.battle.deploying and not self.tactical_story_pending,
                "No standalone AI combat or pending tactical dialogue")
        require(self.battle.active is not None and self.battle.active.team == "enemy",
                "Not an enemy activation")
        old_fired = set(self.battle.fired)
        before = deepcopy((self.progress, self.battle, self.finalized,
                           self.tactical_story_pending, self.tactical_story_queue))
        try:
            play_activation(self.battle)
            self._queue_tactical_story(self.battle, old_fired)
            self._settle()
        except Exception:
            (self.progress, self.battle, self.finalized,
             self.tactical_story_pending, self.tactical_story_queue) = before
            raise

    def return_to_campaign(self):
        if self.fronts is not None:
            require(not (self.fronts.rescue_battles or self.fronts.pursuit_battles
                         or self.fronts.recovery_battles),
                    "Finish tactical side missions first")
            require(all(row["status"] != "active"
                        or self.fronts.battles[name].result is not None
                        for name, row in self.fronts.timeline.fronts.items()),
                    "Fronts still active; abandon explicitly")
        elif self.battle is not None:
            require(self.finalized, "Combat still active; abandon explicitly")
        self.abandon_encounter()

    def abandon_encounter(self):
        """Discard uncompleted tactical progress, not already settled rewards."""
        self.battle = None
        self.fronts = None
        self.finalized = False
        self.settled_fronts = set()
        self.siege_id = None
        self.tactical_story_pending = ""
        self.tactical_story_queue.clear()

    def recording(self):
        """Portable v1 checkpoint; embedded tactical journals verify by replay."""
        tactical = None
        if self.battle is not None:
            tactical = self.battle.recording()
            Battle.replay(tactical, rules=self.rules)
        elif self.fronts is not None:
            tactical = self.fronts.recording()
            MultiFrontSession.replay(tactical, rules=self.rules)
        data = {
            "version": self.VERSION, "kind": "game_session",
            "campaign_id": self.campaign_id, "seed": self.seed,
            "content_digest": digest(self.content.to_dict()),
            "project_digest": gameplay_project_digest(self.project),
            "rules": self.rules.manifest(),
            "progress": {"version": 1, **asdict(self.progress)},
            "mode": self.mode, "tactical": tactical,
            "finalized": self.finalized,
            "settled_fronts": sorted(self.settled_fronts),
        }
        if self.scene_router.enabled:
            data["scene_route"] = {
                "version": 1, "current": self.route_scene,
                "history": list(self.route_history)}
        if self._platform is not None:
            self._platform_definition()
            data["scene_platform"] = {"version": 1, "scene": self.route_scene,
                                      "physics": self._platform.recording()}
        from .action_settlement import validate_settlements
        validate_settlements(
            self._action_settlements, project=self.project,
            route_history=self.route_history, progress=self.progress,
            current_action=self._action)
        if self._action_settlements:
            data["scene_action_history"] = deepcopy(self._action_settlements)
        if self._action is not None:
            require(self.scene_router.enabled and self.mode == "campaign"
                    and self._rt_journal is None and self._platform is None,
                    "Action checkpoint requires routed campaign without other simulators")
            from .action_scene_adapter import authored_action_scene
            from .action_runtime import ActionRuntime
            scene = authored_action_scene(self.project, self.route_scene)
            ActionRuntime.from_recording(self._action.recording(),
                                         expected_scene=scene)
            data["scene_action"] = {
                "version": 1, "scene": self.route_scene,
                "runtime": self._action.recording()}
        if self._rt_journal is not None:
            require(self.scene_router.enabled and self.mode == "campaign"
                    and self.route_scene in self.project.exploration,
                    "Realtime checkpoint requires active exploration")
            data["scene_realtime"] = {
                "version": 1, "scene": self.route_scene,
                "origin": list(self._rt_origin),
                "position": list(self._rt_position),
                "journal": self._rt_journal.recording()}
        if self._living_world is not None:
            data["living_world"] = self._living_world.snapshot()
        if self._classic_party is not None:
            data["classic_party"] = self._classic_party.snapshot()
        if self._party_orchestration is not None:
            require(self._party_orchestration.active == self._classic_party.active,
                    "R53 active group differs from R41 active roster")
            data["party_orchestration"] = self._party_orchestration.snapshot()
        if self._rpg_encounter is not None:
            require(self.progress.inventory == self._rpg_encounter.inventory,
                    "R41 checkpoint inventory diverges from canonical Campaign")
            data["rpg_encounter"] = self._rpg_encounter.recording()
        if self._advanced_ai is not None:
            data["advanced_ai"] = self._advanced_ai.recording()
        if self._systems is not None:
            data["systems"] = self._systems.snapshot()
        if self._survival is not None:
            data["survival"] = self._survival.snapshot()
        if self._farming is not None:
            data["farming"] = self._farming.snapshot()
        if self._relationships is not None:
            data["relationships"] = self._relationships.snapshot()
        if self._stream_world is not None:
            data["world_stream"] = self._stream_world.recording()
        if self._cinematic_pro is not None:
            data["cinematic_pro"] = self._cinematic_pro.snapshot()
        if self._roguelite is not None:
            data["roguelite"] = self._roguelite.recording()
        if self.siege_id is not None:
            data["siege_id"] = self.siege_id
        if self.tactical_story_pending:
            data["tactical_story_pending"] = self.tactical_story_pending
        if self.tactical_story_queue:
            data["tactical_story_queue"] = list(self.tactical_story_queue)
        if self.fronts is not None:
            # MultiFront journals verify rules/state, but historically recreate
            # Battle UUIDs. Preserve identities used by Campaign.record_bonds.
            data["front_battle_ids"] = {
                group: {key: battle.battle_id for key, battle in
                        sorted(getattr(self.fronts, group).items())}
                for group in self.FRONT_BATTLE_GROUPS}
        return {**data, "digest": digest(data)}

    def save(self, path):
        write_json(path, self.recording())
        return Path(path)

    @classmethod
    def from_recording(cls, data, content, project, *, rules=None):
        require(isinstance(data, dict) and type(data.get("version")) is int
                and data.get("version") == cls.VERSION
                and data.get("kind") == "game_session", "Unsupported game session")
        require(set(data) - {"classic_party", "party_orchestration", "rpg_encounter", "front_battle_ids", "siege_id", "scene_route",
                             "scene_realtime", "scene_platform", "scene_action", "scene_action_history", "living_world", "advanced_ai", "world_stream", "cinematic_pro", "roguelite", "systems", "farming", "relationships", "survival", "tactical_story_pending",
                             "tactical_story_queue"} ==
                {"version", "kind", "campaign_id", "seed",
                "content_digest", "project_digest", "rules", "progress",
                "mode", "tactical", "finalized", "settled_fronts", "digest"},
                "Malformed game session")
        require(data["digest"] == digest({k: v for k, v in data.items()
                                         if k != "digest"}), "Game session checksum mismatch")
        if rules is None:
            from .event_pages import has_pages
            from .logic_variables import has_logic_variables
            from .logic_vertical_objective import has_slice_objective
            from .tactical_rpg3 import authored_rules_for_document
            raw = content.to_dict()
            rules = (authored_rules_for_document(raw)
                     if has_pages(raw) or has_logic_variables(raw) or has_slice_objective(raw)
                     else default_rules())
        current_content = digest(content.to_dict())
        current_project = gameplay_project_digest(project)
        current_rules = rules.manifest()
        if data["content_digest"] != current_content:
            raise IncompatibleSaveError("content", data["content_digest"], current_content)
        if data["project_digest"] != current_project:
            raise IncompatibleSaveError("project", data["project_digest"], current_project)
        if data["rules"] != current_rules:
            raise IncompatibleSaveError("rules", data["rules"], current_rules)
        session = cls(content, project, data["campaign_id"],
                      seed=data["seed"], rules=rules)
        if session._living_world is not None:
            require("living_world" in data,
                    "Living-world checkpoint missing from enabled project")
            session._living_world.restore(data["living_world"])
        else:
            require("living_world" not in data,
                    "Unexpected living-world state in legacy checkpoint")
        if session._systems is not None:
            require("systems" in data, "R55 configured economy checkpoint missing")
            session._systems.restore(data["systems"])
        else:
            require("systems" not in data, "Unexpected R55 economy in legacy save")
        if session._survival is not None:
            require("survival" in data, "R63 configured survival checkpoint missing")
            session._survival.restore(data["survival"])
        else:
            require("survival" not in data, "Unexpected R63 state in legacy save")
        if session._farming is not None:
            require("farming" in data, "R62 configured farming checkpoint missing")
            session._farming.restore(data["farming"])
            require(session._farming.day == session._living_world.day,
                    "R62 farm calendar diverges from R35 living-world clock")
        else:
            require("farming" not in data, "Unexpected R62 farm checkpoint")
        if session._relationships is not None:
            require("relationships" in data,
                    "R62 configured relationship checkpoint is missing")
            session._relationships.restore(data["relationships"])
            require(session._relationships.day == session._living_world.day,
                    "R62 social calendar diverges from R35 living world")
        else:
            require("relationships" not in data,
                    "Unexpected relationship state in legacy checkpoint")
        if session._stream_world is not None:
            require("world_stream" in data, "R54 world checkpoint is missing")
            session._stream_world.restore(data["world_stream"])
        else:
            require("world_stream" not in data,
                    "Unexpected R54 checkpoint on legacy project")
        if session._roguelite is not None:
            require("roguelite" in data,
                    "R34 configured project checkpoint is missing its run state")
            from .roguelite import EXTENSION as ROGUELITE_EXTENSION, RogueliteRun
            session._roguelite = RogueliteRun.from_recording(
                project.extensions[ROGUELITE_EXTENSION]["data"], data["roguelite"],
                content=session.content, project=session.project)
        else:
            require("roguelite" not in data,
                    "Unexpected R34 state in a legacy session")
        session.progress = Campaign.from_dict(data["progress"], ruleset=rules)
        if session._classic_party is None:
            require("classic_party" not in data,
                    "Unexpected R41 party state in legacy checkpoint")
        else:
            require("classic_party" in data,
                    "Missing party state for enabled RPG_TURN campaign")
            session._classic_party.restore(data["classic_party"])
            require(set(session._classic_party.members) <= set(session.progress.heroes),
                    "Party recruitment has no canonical HeroProgress")
        if session._party_orchestration is None:
            require("party_orchestration" not in data,
                    "Unexpected R53 state in unconfigured GameSession")
        else:
            require("party_orchestration" in data,
                    "Missing R53 state from enabled GameSession")
            session._party_orchestration.restore(
                data["party_orchestration"], session._classic_party)
        if session._systems is not None:
            require(all(session.progress.story_flags.get(
                session._systems.quests[quest_id]["flag"]) is True
                for quest_id in session._systems.fulfilled),
                "R55 quest receipt requires the persisted campaign story flag")
        verify_flow_save(session.progress, project.campaign_flow)
        session.story.initialize(session.progress, session.campaign_id)
        if session._cinematic_pro is not None:
            require("cinematic_pro" in data,
                    "R46 configured project checkpoint is missing cinematic progress")
            session._cinematic_pro.restore(data["cinematic_pro"])
        else:
            require("cinematic_pro" not in data,
                    "Unexpected R46 checkpoint in legacy session")
        require(set(session.progress.unlocked + session.progress.completed)
                <= set(session.content.missions), "Unknown campaign mission")
        mode = data["mode"]
        require(mode in {"campaign", "battle", "fronts", "rpg"}, "Invalid session mode")
        if mode == "rpg":
            from .classic_party import EXTENSION
            from .classic_encounter import ClassicEncounter
            require(session._classic_party is not None
                    and type(data.get("rpg_encounter")) is dict
                    and type(data["rpg_encounter"].get("id")) is str
                    and data["tactical"] is None and not data["finalized"]
                    and not data["settled_fronts"]
                    and not session.progress.story_pending
                    and not session.progress.story_flags.get(
                        "r41_" + str(data["rpg_encounter"].get("id", "")), False),
                    "Invalid R41 encounter mode/checkpoint")
            encounter_id = data["rpg_encounter"]["id"]
            spec = session.project.extensions[EXTENSION]["data"].get(
                "encounters", {}).get(encounter_id)
            require(spec is not None, "Unknown saved RPG encounter")
            session._rpg_encounter = ClassicEncounter.replay(
                data["rpg_encounter"], encounter_id=encounter_id,
                config=spec, party=session._classic_party.active,
                content=session.content,
                hero_progress=session.progress.heroes,
                combo_specs=(session._party_orchestration.rpg_combo_specs()
                             if session._party_orchestration is not None else None))
            require(session._rpg_encounter.inventory == session.progress.inventory,
                    "R41 replay inventory disagrees with canonical Campaign")
        else:
            require("rpg_encounter" not in data,
                    "Unexpected R41 encounter state outside RPG mode")
        pending = data.get("tactical_story_pending", "")
        queue = data.get("tactical_story_queue", [])
        require(isinstance(pending, str) and
                isinstance(queue, list) and len(queue) <= 128 and
                all(isinstance(sid, str) for sid in queue),
                "Invalid tactical dialogue checkpoint")
        require(not pending or pending in session.story.scenes,
                "Unknown pending tactical scene")
        require(all(scene in session.story.during_tactical_event.values()
                    for scene in queue), "Unknown queued tactical scene")
        require(not queue or bool(pending),
                "Queued tactical scenes require a pending dialogue")
        require((not pending and not queue) or
                (mode == "battle" and not session.progress.story_pending),
                "Tactical dialogue belongs to a standalone battle")
        session.tactical_story_pending = pending
        session.tactical_story_queue = list(queue)
        require("siege_id" not in data or (mode == "fronts"
                and isinstance(data["siege_id"], str) and bool(data["siege_id"])),
                "Invalid authored siege identity")
        require("front_battle_ids" not in data or mode == "fronts",
                "Battle identities require a multi-front session")
        settled = data["settled_fronts"]
        require(isinstance(settled, list) and all(isinstance(s, str) for s in settled)
                and len(set(settled)) == len(settled), "Invalid settlement log")
        require(type(data["finalized"]) is bool, "Invalid finalization flag")
        if mode in ("campaign", "rpg"):
            require(data["tactical"] is None and not data["finalized"] and not settled,
                    "Non-tactical session has tactical state")
        elif mode == "battle":
            require(isinstance(data["tactical"], dict) and not settled,
                    "Invalid standalone battle state")
            session.battle = Battle.replay(data["tactical"], rules=rules)
            require(session.battle.mission.id in
                    session.progress.unlocked + session.progress.completed,
                    "Unknown or locked tactical mission")
            session.finalized = data["finalized"]
            require(session.finalized ==
                    (session.battle.result in ("victory", "defeat")
                     and not pending),
                    "Battle finalization mismatch")
            if pending:
                require(any(ref.split("/", 1)[0] == session.battle.mission.id
                            and ref.split("/", 1)[1] in session.battle.fired
                            for ref in session.story.during_tactical_event),
                        "Pending tactical dialogue has no fired origin")
            # Recorded narrative actions must correspond to real authored
            # choices, not arbitrary Battle commands injected into the journal.
            # Every post-3.7.21F tactical choice writes one story_effects command.
            decisions = [cmd for cmd in session.battle.commands
                         if cmd.get('kind') == 'story_effects']
            history = session.progress.story_history
            require(len(decisions) <= len(history),
                    'Battle story decisions exceed campaign history')
            if decisions:
                require(history[-len(decisions):] == [
                    {'scene': cmd['scene'], 'choice': cmd['choice']}
                    for cmd in decisions], 'Battle story decisions mismatch campaign history')
                permitted = set()
                def visit(scene_id):
                    if scene_id in permitted:
                        return
                    permitted.add(scene_id)
                    for choice in session.story.scenes[scene_id]['choices']:
                        dest = choice.get('next_scene')
                        if dest:
                            visit(dest)
                for reference, root in session.story.during_tactical_event.items():
                    mid, trigger_id = reference.split('/', 1)
                    if mid == session.battle.mission.id and trigger_id in session.battle.fired:
                        visit(root)
                for cmd in decisions:
                    require(cmd['scene'] in permitted,
                            'Story choice was not reached by a tactical event')
                    authored = next((c for c in session.story.scenes[cmd['scene']]['choices']
                                    if c['id'] == cmd['choice']), None)
                    require(authored is not None and
                            authored.get('tactical_effects', []) == cmd['effects'],
                            'Replayed tactical effects differ from authored choice')
        else:
            require(isinstance(data["tactical"], dict) and not data["finalized"],
                    "Invalid multi-front state")
            session.fronts = MultiFrontSession.replay(data["tactical"], rules=rules)
            require(set(session.fronts.missions.values()) <=
                    set(session.progress.unlocked + session.progress.completed)
                    and set(settled) <= set(session.fronts.missions),
                    "Unknown multi-front mission or settlement")
            for front, battle in session.fronts.battles.items():
                require((front in settled) == (battle.result in ("victory", "defeat")),
                        "Front finalization mismatch")
            session.settled_fronts = set(settled)
            if "siege_id" in data:
                bp = next((row for row in session.project.sieges
                           if row["id"] == data["siege_id"] and
                           row["campaign_id"] == session.campaign_id), None)
                require(bp is not None and session.fronts.missions == bp["fronts"]
                        and session.fronts.initial_focus == bp["focused"]
                        and session.fronts.initial_specs == bp["specs"]
                        and session.fronts.links == bp["links"]
                        and session.fronts.initial_campaign == bp["campaign"]
                        and session.fronts.initial_logistics == bp.get("logistics")
                        and session.fronts.initial_event_graph == bp.get("event_graph", []),
                        "Authored siege no longer matches saved front configuration")
                session.siege_id = data["siege_id"]
            if "front_battle_ids" in data:
                identities = data["front_battle_ids"]
                require(isinstance(identities, dict) and
                        set(identities) == set(cls.FRONT_BATTLE_GROUPS),
                        "Invalid front battle identity groups")
                seen = set()
                for group in cls.FRONT_BATTLE_GROUPS:
                    battles = getattr(session.fronts, group)
                    rows = identities[group]
                    require(isinstance(rows, dict) and set(rows) == set(battles),
                            "Front battle identities do not match live battles")
                    for key, identity in rows.items():
                        require(isinstance(identity, str) and 0 < len(identity) <= 128
                                and identity not in seen, "Invalid or duplicate battle identity")
                        battles[key].battle_id = identity
                        seen.add(identity)
        # R25.B scene routing is opt-in. The legacy v1 recording is untouched.
        if session.scene_router.enabled:
            require("scene_route" in data,
                    "Routed project checkpoint is missing scene state")
            session.route_scene = session.scene_router.validate_checkpoint(
                data["scene_route"], mode=mode, battle=session.battle,
                rpg_scene=(session._rpg_encounter.scene
                           if session._rpg_encounter is not None else None))
            session.route_history = list(data["scene_route"]["history"])
            if session.route_scene in session.project.exploration:
                session.exploration.state(session.progress, session.route_scene)
        else:
            require("scene_route" not in data,
                    "Unexpected scene state in legacy checkpoint")
        if "scene_realtime" in data:
            from .fixed_clock import FixedTickJournal
            from .fixed_realtime import FreeMovement
            saved = data["scene_realtime"]
            require(type(saved) is dict
                    and set(saved) == {"version", "scene", "origin",
                                       "position", "journal"}
                    and type(saved["version"]) is int
                    and saved["version"] == 1
                    and saved["scene"] == session.route_scene
                    and mode == "campaign"
                    and session.scene_router.enabled
                    and saved["scene"] in project.exploration
                    and session.scene_profile(saved["scene"])["movement"]
                    == "FREE_REALTIME",
                    "Invalid realtime checkpoint metadata")
            movement = FreeMovement(project.exploration[saved["scene"]])
            origin = movement.center(movement.cell(saved["origin"]))
            require(origin == saved["origin"],
                    "Realtime journal origin must be an unblocked tile center")
            position = list(origin)
            def verify_tick(tick, commands):
                nonlocal position
                for event in commands:
                    cmd = event["command"]
                    require(event["source"] == "hero"
                            and type(cmd) is dict
                            and set(cmd) == {"kind", "dx", "dy"}
                            and cmd["kind"] == "move",
                            "Invalid replayed movement command")
                    position = movement.advance(position, cmd["dx"], cmd["dy"])
                return {"scene": saved["scene"], "position": list(position)}
            journal = FixedTickJournal.replay(saved["journal"], verify_tick)
            require(journal.rate == 60 and journal.seed == session.seed,
                    "Realtime replay seed/rate mismatch")
            require(journal.tick > 0 and saved["position"] == position,
                    "Realtime replay position diverged")
            stage = session.exploration.state(session.progress, saved["scene"])
            require(stage["position"] == movement.cell(position),
                    "Realtime and campaign exploration positions disagree")
            session._rt_origin = origin
            session._rt_position = list(position)
            session._rt_journal = journal
        # A completed boss in the active room must carry an authentic
        # replay. A hash-recomputed Campaign flag without scene_platform is
        # not sufficient evidence of a physical boss victory.
        physics_catalog = (project.extensions.get("drawtemp.physics", {})
                           .get("data", {}).get("scenes", {}))
        authored_physics = physics_catalog.get(session.route_scene, {})
        if "boss" in authored_physics:
            from .exploration import _key
            claimed = session.progress.story_flags.get(
                _key(session.route_scene, "boss_defeated")) is True
            require(not claimed or "scene_platform" in data,
                    "R40 boss victory requires an authenticated R32 replay")
        if "scene_action" in data:
            from .action_scene_adapter import authored_action_scene
            from .action_runtime import ActionRuntime
            action_saved = data["scene_action"]
            require(type(action_saved) is dict and
                    set(action_saved) == {"version", "scene", "runtime"}
                    and type(action_saved["version"]) is int
                    and action_saved["version"] == 1
                    and action_saved["scene"] == session.route_scene
                    and mode == "campaign" and session.scene_router.enabled
                    and session._rt_journal is None
                    and "scene_platform" not in data
                    and session.route_scene in project.exploration,
                    "Invalid R26 action checkpoint identity or mode")
            scene = authored_action_scene(project, session.route_scene)
            session._action = ActionRuntime.from_recording(
                action_saved["runtime"], expected_scene=scene)
            require(session._action.tick > 0,
                    "Action checkpoint must contain at least one accepted tick")
        if "scene_platform" in data:
            from .platform_physics import PlatformPhysics
            saved = data["scene_platform"]
            require(type(saved) is dict and set(saved) == {"version", "scene", "physics"}
                    and type(saved["version"]) is int and saved["version"] == 1
                    and saved["scene"] == session.route_scene
                    and session._rt_journal is None, "Invalid R32 platform checkpoint")
            authored = session._platform_definition()
            platform = PlatformPhysics.from_recording(saved["physics"],
                                                      expected_scene=authored)
            require(platform.max_air_jumps <= session._metroidvania_air_jumps(),
                    "R32 air jumps are not authorized by earned R33 abilities")
            if "boss" in authored:
                from .exploration import _key
                won = session.progress.story_flags.get(
                    _key(session.route_scene, "boss_defeated")) is True
                require(won == platform.boss.snapshot()["defeated"],
                        "R40 boss replay disagrees with canonical campaign victory")
            authored_openable = {row["opens"] for row in authored["colliders"]
                                 if "opens" in row}
            saved_opened = {ident for ident in authored_openable
                            if session.progress.story_flags.get(
                                session._platform_flag(ident)) is True}
            require(saved_opened == platform.disabled_colliders,
                    "R32 physics replay disagrees with canonical campaign flags")
            session._platform = platform
        if session._stream_world is not None:
            session._stream_world.assert_scene(session.route_scene)
            expected = [session._stream_world.spec["start"]]
            for route_id in session.route_history:
                route = session.scene_router.links[route_id]
                target = session._stream_world.scenes.get(route["destination"])
                if target is not None and target != expected[-1]:
                    require(target in session._stream_world.cells[
                        expected[-1]]["neighbors"],
                        "R54 route history crosses a non-neighbor cell")
                    expected.append(target)
            require(expected == session._stream_world.history,
                    "R54 world history diverged from R25 route journal")
        # World map travel is optional, but an existing cursor must never be
        # accepted from a malformed or inaccessible persisted route.
        from .action_settlement import validate_settlements
        history = data.get("scene_action_history", [])
        require("scene_action_history" not in data or
                (type(history) is list and bool(history)),
                "Empty or malformed R26 settlement evidence")
        validate_settlements(
            history, project=project, route_history=session.route_history,
            progress=session.progress, current_action=session._action)
        session._action_settlements = deepcopy(history)
        session.world_state()
        # Reconstruct each snapshot from its write ledger after the canonical
        # combat / realtime clocks have been verified and loaded.
        if session._advanced_ai is not None:
            require("advanced_ai" in data,
                    "R37 configured project checkpoint is missing AI state")
            session._advanced_ai.restore(data["advanced_ai"])
            for actor_id, agent in session._advanced_ai.agents.items():
                updated = session._advanced_ai.blackboards[actor_id]["updated_tick"]
                if agent["mode"] == "realtime":
                    require(session._living_world is not None
                            and updated <= session._living_world.ticks,
                            "R37 AI memory exceeds replayed world time")
                elif session.mode == "battle" and session.battle is not None:
                    if any(unit.id == actor_id for unit in session.battle.units):
                        require(updated <= session.battle.tick,
                                "R37 CT memory exceeds replayed battle time")
        else:
            require("advanced_ai" not in data,
                    "Unexpected R37 memory in legacy checkpoint")
        if project.story.get('schema_version') == 2:
            from .narrative_playback_r42 import validate_cursor
            # The snapshot has already been restored and authenticated. A
            # cursor outside the pending scene is not a valid resumable save.
            pending = (session.tactical_scene() if session.tactical_story_pending
                       else session.active_scene())
            index = validate_cursor(session.progress, pending)
            require(pending is not None or index == 0,
                    'R42 save has an unbound dialogue cursor')
        return session

    @classmethod
    def load(cls, path, content, project, *, rules=None):
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls.from_recording(data, content, project, rules=rules)
        except IncompatibleSaveError:
            raise
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise RuleError(f"Invalid game session: {exc}") from exc
