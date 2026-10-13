"""Read-only event links and reproducible probes using the actual battle rules.

The authoring layer never evaluates a trigger or executes its actions itself.
Each preview creates a disposable Battle, arranges a clearly labelled test
state when requested, then delegates to the normal trigger dispatcher.
"""
from copy import deepcopy

from . import event_graph
from .engine import Battle
from .model import Content, RuleError, require
from .rules import triggers
from .tactical_rpg3 import authored_rules_for_document

PREVIEW_SCENARIOS = ('initial', 'satisfied', 'unsatisfied')


def _authored_event(data, mission_id, event_id):
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown mission')
    event = next((e for e in mission.get('triggers', [])
                  if e['id'] == event_id), None)
    require(event is not None, 'Unknown tactical event')
    return mission, event


def inspect_event(data, mission_id, event_id, project=None):
    """Project only persisted references; do not invent trigger-level links."""
    _, event = _authored_event(data, mission_id, event_id)
    scene_id = ''
    clips = []
    if project is not None:
        scene_id = project.story.get('after_mission', {}).get(mission_id, '')
        for clip in project.cinematics:
            trigger = clip['trigger']
            kind, target = trigger['kind'], trigger['target']
            if kind in ('before_mission', 'after_mission') and target == mission_id:
                clips.append({'id': clip['id'], 'stage': kind, 'scope': 'mission'})
            elif kind == 'scene' and scene_id and target == scene_id:
                clips.append({'id': clip['id'], 'stage': 'scene', 'scope': 'scene'})
    return {
        'mission_id': mission_id,
        'event_id': event_id,
        'condition': event_graph.condition_title(event),
        'condition_kind': event['condition'],
        'actions': [event_graph.action_title(action)
                    for action in event['actions']],
        'scene_id': scene_id,
        'cinematics': clips,
        # These are associated with the mission or its after-victory scene.
        # No cinematic starts when the selected tactical trigger itself fires.
        'links_scope': 'mission',
    }


def _free_cell(battle, unit):
    for cell in battle.board.cells():
        footprint = unit.occupied_cells(origin=cell)
        if not all(battle.board.contains(pos) and
                   not battle.board.tile(pos).blocked for pos in footprint):
            continue
        if any(other.alive and other.id != unit.id and
               footprint & other.occupied_cells() for other in battle.units):
            continue
        return cell
    raise RuleError('No free cell to prepare a false entry condition')


def _prepare_scenario(battle, trigger, scenario):
    """Arrange a test state, NEVER implement an event predicate here."""
    if scenario == 'initial':
        return []
    true_case = scenario == 'satisfied'
    kind = trigger['condition']
    if kind == 'tick':
        minimum = trigger['value']
        if not true_case and minimum == 0:
            raise RuleError('Tick >= 0 is always true; no false tick scenario')
        battle.tick = minimum if true_case else minimum - 1
        return [f'Tick de test fixé à {battle.tick} (sans dérouler les tours)']
    if kind == 'enter':
        destination = tuple(trigger['pos'])
        at_destination = [u for u in battle.units
                          if u.team == 'player' and u.alive and u.pos == destination]
        if true_case:
            if not at_destination:
                candidate = next((u for u in battle.units
                                  if u.team == 'player' and u.alive), None)
                require(candidate is not None,
                        'No living player available for entry scenario')
                candidate.pos = destination
                return [f'Position de test de {candidate.id} fixée à {destination}']
            return ['Un joueur occupe déjà la case testée']
        for unit in at_destination:
            origin = unit.pos
            unit.pos = _free_cell(battle, unit)
            require(unit.pos != origin,
                    'No alternative free cell for entry scenario')
        return ['Joueurs éloignés de la case testée, si nécessaire']
    if kind in ('defeated', 'hp_below'):
        unit = battle.unit(trigger['unit'])
        if kind == 'defeated':
            unit.hp = 0 if true_case else unit.max_hp
        else:
            threshold = unit.max_hp * trigger['percent'] // 100
            if true_case:
                require(threshold >= 1, 'No living HP value can meet this threshold')
                unit.hp = threshold
            else:
                unit.hp = unit.max_hp
        return [f'PV de test de {unit.id} fixés à {unit.hp}/{unit.max_hp}']
    if kind == 'wave_capacity':
        team = trigger.get('team', 'enemy')
        maximum = trigger['max_alive']
        alive = [u for u in battle.units if u.team == team and u.alive]
        if true_case:
            for unit in alive[maximum:]:
                unit.hp = 0
            return [f'Unités vivantes du camp {team} limitées à {maximum}']
        require(len(alive) > maximum,
                'Not enough authored living units for a false capacity case')
        return [f'{len(alive)} unités vivantes {team} dépassent {maximum}']
    raise RuleError(f'No scenario setup for condition {kind}')


def _snapshot(battle, hazard_cells):
    return {
        'units': {u.id: {
            'hp': u.hp, 'mp': u.mp, 'pos': tuple(u.pos),
            'statuses': deepcopy(u.statuses),
        } for u in battle.units},
        'hazards': {cell: battle.board.tile(cell).hazard for cell in hazard_cells},
    }


def _state_changes(before, after):
    changes = []
    old_units, new_units = before['units'], after['units']
    for uid in sorted(old_units.keys() & new_units.keys()):
        for field, title in (('hp', 'PV'), ('mp', 'PM'), ('pos', 'position'),
                             ('statuses', 'statuts')):
            left, right = old_units[uid][field], new_units[uid][field]
            if left != right:
                changes.append(f'{uid} · {title} : {left} → {right}')
    for cell in sorted(before['hazards']):
        old = before['hazards'][cell]
        new = after['hazards'][cell]
        if old != new:
            changes.append(f'Case {cell} · danger : {old} → {new}')
    for uid in sorted(new_units.keys() - old_units.keys()):
        changes.append(f'Unité apparue : {uid}')
    for uid in sorted(old_units.keys() - new_units.keys()):
        changes.append(f'Unité retirée : {uid}')
    return changes


def preview_event(data, mission_id, event_id, *, tick=0, scenario='initial'):
    """Probe one trigger with the real dispatcher in a disposable battle.

    initial: actual authored roster at the specified tick, no intervening turns.
    satisfied/unsatisfied: synthetic, explicitly labelled setup to probe the
    engine's own predicate. Impossible cases raise a RuleError rather than
    manufacturing illegal actors or fabricating a condition result.
    """
    require(type(tick) is int and 0 <= tick <= 100000,
            'Preview tick must be an integer from 0 to 100000')
    require(scenario in PREVIEW_SCENARIOS,
            'Unknown contextual preview scenario')
    _, event = _authored_event(data, mission_id, event_id)
    rules = authored_rules_for_document(data)
    snapshot = deepcopy(data)
    mission = next(m for m in snapshot['missions'] if m['id'] == mission_id)
    mission['triggers'] = []
    battle = Battle(Content.from_dict(snapshot, rules=rules),
                    mission_id, seed=1, rules=rules)
    battle.tick = tick
    battle.mission.triggers = [deepcopy(event)]
    notes = _prepare_scenario(battle, event, scenario)
    first_event = len(battle.events)
    hazard_cells = {tuple(a['pos']) for a in event['actions']
                    if a['kind'] == 'hazard'}
    before = _snapshot(battle, hazard_cells)
    error = ''
    try:
        # The same condition rule and ordered actions used during gameplay.
        triggers.dispatch(battle)
    except (RuleError, ValueError, KeyError, IndexError) as exc:
        error = str(exc)
    after = _snapshot(battle, hazard_cells)
    activated = event_id in battle.fired
    return {
        'mission_id': mission_id,
        'event_id': event_id,
        'tick': battle.tick,
        'requested_tick': tick,
        'scenario': scenario,
        'scenario_notes': notes,
        'fired': activated,
        'outcome': 'error' if error else 'applied' if activated else 'inactive',
        'actions': [event_graph.action_title(a) for a in event['actions']],
        'events': deepcopy(battle.events[first_event:]),
        'changes': _state_changes(before, after),
        'spawned': sorted(after['units'].keys() - before['units'].keys()),
        'despawned': sorted(before['units'].keys() - after['units'].keys()),
        'error': error,
        'isolated': True,
    }


def format_preview_report(report):
    """Short, readable Studio trace; a pure projection of a real battle report."""
    status = {
        'inactive': 'Condition non satisfaite : aucune action exécutée',
        'applied': 'Condition satisfaite : actions exécutées',
        'error': 'Erreur pendant l’exécution du moteur (état de test partiel)',
    }[report['outcome']]
    lines = [
        'APERÇU ISOLÉ — aucun enregistrement, aucun tour intermédiaire simulé',
        f"Scénario : {report['scenario']} | Tick : {report['tick']}",
        status,
    ]
    lines.extend('Préparation : ' + note for note in report['scenario_notes'])
    if report['changes']:
        lines.append('CONSÉQUENCES :')
        lines.extend('  ' + change for change in report['changes'])
    if report['events']:
        lines.append('ÉVÉNEMENTS DU MOTEUR :')
        for row in report['events'][:30]:
            details = ', '.join(f'{key}={value}' for key, value in row.items()
                                if key not in ('kind', 'tick'))
            lines.append(f"  {row['kind']} (tick {row['tick']})" +
                         (': ' + details if details else ''))
        if len(report['events']) > 30:
            lines.append(f"  … {len(report['events']) - 30} événements supplémentaires")
    if report['error']:
        lines.append('ERREUR : ' + report['error'])
    if not report['changes'] and not report['events'] and not report['error']:
        lines.append('Aucun effet visible dans ce scénario')
    return lines
