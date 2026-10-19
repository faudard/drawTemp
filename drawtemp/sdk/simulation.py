"""R1 synchronous simulation API. All gameplay remains owned by GameSession."""
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from types import MappingProxyType

from drawtemp.core import GameSession, RuleError
from sporebound.ai import choose_command
from sporebound.game_session import IncompatibleSaveError


def freeze(value):
    """Detach and recursively freeze JSON-compatible runtime presentation data."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(freeze(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError('Unsupported presentation value: ' + type(value).__name__)


def thaw(value):
    if isinstance(value, Mapping):
        return {key: thaw(item) for key, item in value.items()}
    if isinstance(value, (tuple, frozenset)):
        return [thaw(item) for item in value]
    return value


class SimulationError(RuleError):
    """Stable code + operation; the underlying canonical exception is __cause__."""
    def __init__(self, code, operation, message):
        self.code, self.operation = code, operation
        super().__init__(message)


@dataclass(frozen=True)
class StateSnapshot:
    revision: int
    mode: str
    campaign_id: str
    missions: tuple[str, ...]
    progress: Mapping
    scene: Mapping | None
    battle: Mapping | None
    exploration: Mapping | None = None

    def to_dict(self):
        return {name: thaw(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class GameEvent:
    revision: int
    index: int
    kind: str
    tick: int | None
    payload: Mapping


@dataclass(frozen=True)
class Transition:
    source_revision: int
    snapshot: StateSnapshot
    events: tuple[GameEvent, ...]


class Simulation:
    """Single-owner session; returns no mutable engine objects to UI consumers.

    Revisions belong to this handle and restart on load. This is not a worker,
    save format or replay format. Multi-front authoring APIs are not exposed yet.
    """
    def __init__(self, session):
        self._session = deepcopy(session)
        self._revision = 0

    @classmethod
    def new(cls, content, project, campaign_id, *, seed=17, rules=None):
        try:
            return cls(GameSession.new(content, project, campaign_id, seed=seed, rules=rules))
        except RuleError as exc:
            raise SimulationError('invalid_session', 'new', str(exc)) from exc

    @classmethod
    def load(cls, path, content, project, *, rules=None):
        try:
            return cls(GameSession.load(path, content, project, rules=rules))
        except IncompatibleSaveError as exc:
            raise SimulationError('incompatible_save', 'load', str(exc)) from exc
        except RuleError as exc:
            raise SimulationError('invalid_save', 'load', str(exc)) from exc
        except OSError as exc:
            raise SimulationError('io_error', 'load', str(exc)) from exc

    def recording(self):
        return deepcopy(self._session.recording())

    def snapshot(self):
        session = self._session
        battle = session.active_battle
        scene = session.tactical_scene() if session.tactical_story_pending else session.active_scene()
        state = None
        if battle is not None:
            state = freeze({**battle.state(), 'mission_id': battle.mission.id,
                            'objective': battle.mission.objective,
                            'width': battle.board.width, 'height': battle.board.height})
        exploration = None
        if session.mode == "campaign":
            if scene is not None:
                exploration = session.exploration_state()
            elif (session.scene_router.enabled
                  and session.route_scene in session.project.exploration):
                exploration = session.route_state()
        return StateSnapshot(self._revision, session.mode, session.campaign_id,
                             tuple(session.available_missions()),
                             freeze(asdict(session.progress)), freeze(scene), state,
                             freeze(exploration) if exploration is not None else None)

    def _check_revision(self, expected, operation):
        if expected is not None and (type(expected) is not int or expected != self._revision):
            raise SimulationError('stale_revision', operation, 'Session changed; refresh the preview')

    def _apply(self, operation, *args, expected_revision=None):
        self._check_revision(expected_revision, operation)
        before = deepcopy(self._session)
        previous_revision = self._revision
        old_battle = before.active_battle
        try:
            getattr(self._session, operation)(*deepcopy(args))
            self._revision += 1
            battle = self._session.active_battle
            start = len(old_battle.events) if (battle is not None and old_battle is not None
                                              and battle.battle_id == old_battle.battle_id) else 0
            rows = battle.events[start:] if battle is not None else ()
            events = [GameEvent(self._revision, index, row['kind'], row.get('tick'),
                                freeze({k: v for k, v in row.items() if k not in ('kind', 'tick')}))
                      for index, row in enumerate(rows)]
            events.append(GameEvent(self._revision, len(events), 'session.' + operation,
                                    battle.tick if battle is not None else None, freeze({})))
            return Transition(previous_revision, self.snapshot(), tuple(events))
        except Exception as exc:
            self._session, self._revision = before, previous_revision
            if isinstance(exc, RuleError):
                raise SimulationError('invalid_action', operation, str(exc)) from exc
            raise

    def choices(self):
        """Only currently permitted story choices; never expose rule internals."""
        if self._session.tactical_story_pending:
            return freeze(self._session.tactical_choices())
        return freeze(self._session.available_choices())

    def living_world_state(self, scene=None):
        """Opt-in detached world projection for Player/Qt; no state mutation."""
        if self._session._living_world is None:
            return None
        return freeze(self._session.living_world_state(scene=scene))

    def living_world_advance(self, ticks=1, *, expected_revision=None):
        """Player-facing explicit time step, checked through R1 revisions."""
        return self._apply("living_world_advance", ticks,
                           expected_revision=expected_revision)

    def roguelite_state(self, *, expected_revision=None):
        """Read-only deterministic R34 run view (not an alternate save schema)."""
        self._check_revision(expected_revision, 'roguelite_state')
        try:
            return freeze(self._session.roguelite_state())
        except RuleError as exc:
            raise SimulationError('invalid_action', 'roguelite_state', str(exc)) from exc

    def roguelite_move(self, room_id, *, expected_revision=None):
        return self._apply('roguelite_move', room_id,
                           expected_revision=expected_revision)

    def roguelite_claim(self, *, expected_revision=None):
        return self._apply('roguelite_claim', expected_revision=expected_revision)

    def roguelite_checkpoint(self, *, expected_revision=None):
        return self._apply('roguelite_checkpoint', expected_revision=expected_revision)

    def roguelite_die(self, *, expected_revision=None):
        return self._apply('roguelite_die', expected_revision=expected_revision)

    def roguelite_restart(self, *, expected_revision=None):
        return self._apply('roguelite_restart', expected_revision=expected_revision)

    def explore_move(self, dx, dy, *, expected_revision=None):
        session = self._session
        # R25 routed exploration is not a narrative StoryBook scene.
        # The Player must use the same canonical route command as GameSession.
        routed = (session.scene_router.enabled
                  and session.active_scene() is None
                  and session.route_scene in session.project.exploration)
        operation = 'route_move' if routed else 'explore_move'
        return self._apply(operation, dx, dy, expected_revision=expected_revision)

    def explore_interact(self, point_id, *, expected_revision=None):
        session = self._session
        routed = (session.scene_router.enabled
                  and session.active_scene() is None
                  and session.route_scene in session.project.exploration)
        operation = 'route_interact' if routed else 'explore_interact'
        return self._apply(operation, point_id, expected_revision=expected_revision)

    def explore_wait(self, *, expected_revision=None):
        return self._apply('explore_wait', expected_revision=expected_revision)

    def explore_actor(self, actor_id, action, *, expected_revision=None):
        return self._apply('explore_actor', actor_id, action,
                           expected_revision=expected_revision)

    def auto_enemy_turn(self, *, expected_revision=None):
        """One bounded engine-owned AI activation; never play the human's turn."""
        self._check_revision(expected_revision, 'auto_enemy_turn')
        battle = self._session.active_battle
        if (battle is None or battle.result or battle.deploying or
                self._session.tactical_story_pending or
                self._session.progress.story_pending or
                battle.active is None or battle.active.team != 'enemy'):
            raise SimulationError('invalid_action', 'auto_enemy_turn',
                                  'No enemy activation is ready')
        return self._apply('execute', choose_command(battle),
                           expected_revision=expected_revision)

    def pending_scene_cinematic(self):
        """Immutable authored presentation cue; never expose mutable engine data."""
        return freeze(self._session.pending_scene_cinematic())

    def acknowledge_scene_cinematic(self, clip_id, *, expected_revision=None):
        """Revision-checked acknowledgement with canonical transaction rollback."""
        return self._apply('acknowledge_scene_cinematic', clip_id,
                           expected_revision=expected_revision)

    def choose_story_option(self, choice, *, expected_revision=None):
        return self._apply('choose_story_option', choice, expected_revision=expected_revision)

    def choose_tactical_story_option(self, choice, *, expected_revision=None):
        return self._apply('choose_tactical_story_option', choice, expected_revision=expected_revision)

    def start_mission(self, mission, *, expected_revision=None):
        return self._apply('start_mission', mission, expected_revision=expected_revision)

    def equip_hero(self, hero_id, item_id, *, expected_revision=None):
        """Revision-checked, rollback-safe existing Campaign equipment action."""
        return self._apply('equip_hero', hero_id, item_id,
                           expected_revision=expected_revision)

    def unequip_hero(self, hero_id, slot, *, expected_revision=None):
        return self._apply('unequip_hero', hero_id, slot,
                           expected_revision=expected_revision)

    def execute(self, command, *, expected_revision=None):
        return self._apply('execute', command, expected_revision=expected_revision)

    def return_to_campaign(self, *, expected_revision=None):
        return self._apply('return_to_campaign', expected_revision=expected_revision)

    def tactical_presentation(self, cell, skill_id="attack", *, expected_revision=None):
        """R12 read-only, revision-checked combat HUD and factual intent overlay.

        The UI sees detached data only; enemy choices remain unknown, and
        Battle.forecast is a probabilistic forecast rather than an RNG sample.
        """
        self._check_revision(expected_revision, 'tactical_presentation')
        from drawtemp.player.tactical_feedback import build_feedback
        return freeze(build_feedback(self._session.active_battle, cell, skill_id,
                                     revision=self._revision))

    def preview(self, command, *, expected_revision=None):
        self._check_revision(expected_revision, 'preview')
        sandbox = Simulation(self._session)
        sandbox._revision = self._revision
        return sandbox.execute(command)

    def simulate(self, *, max_steps=100):
        """Bounded detached AI simulation; may stop before victory or at dialogue.

        Returns a final immutable state. Never advances the live handle.
        """
        if type(max_steps) is not int or not 1 <= max_steps <= 1000:
            raise SimulationError('invalid_budget', 'simulate', 'Expected 1..1000 steps')
        sandbox = Simulation(self._session)
        sandbox._revision = self._revision
        for _ in range(max_steps):
            battle = sandbox._session.active_battle
            if (battle is None or battle.result or sandbox._session.tactical_story_pending
                    or sandbox._session.progress.story_pending):
                break
            sandbox.execute(choose_command(battle))
        return sandbox.snapshot()

    def save(self, path):
        try:
            self._session.save(path)
        except OSError as exc:
            raise SimulationError('io_error', 'save', str(exc)) from exc
