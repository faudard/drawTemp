"""Transient, deterministic Event Studio debugger using the real Battle dispatcher.

Not a runtime mode, replay format, game command, schema or alternate event
interpreter. Debug snapshots contain synthetic setup and are NEVER certified
as authenticated Battle/GameSession replays.
"""
from copy import deepcopy

from .engine import Battle
from .event_context import (_authored_event, _prepare_scenario, _snapshot,
                            _state_changes, condition_trace)
from .event_graph import chain_descendants, action_title
from .model import Content, require
from .rules import triggers
from .tactical_rpg3 import authored_rules_for_document


class EventDebugger:
    """A single disposable preview lifecycle, with bounded per-event stepping."""

    MAX_TIMELINE = 200

    def __init__(self, data, mission_id, event_id, *, project=None,
                 tick=0, scenario='satisfied', included_event_ids=None):
        require(type(tick) is int and 0 <= tick <= 100000,
                'Debug tick must be 0..100000')
        require(scenario in ('initial', 'satisfied', 'unsatisfied'),
                'Unknown event-debug scenario')
        _, selected = _authored_event(data, mission_id, event_id)
        self.rules = authored_rules_for_document(data)
        Content.from_dict(data, rules=self.rules)
        self.mission_id, self.event_id = mission_id, event_id
        self.project = deepcopy(project) if project is not None else None
        self.selected = deepcopy(selected)
        if included_event_ids is None:
            self.chain = chain_descendants(data, mission_id, event_id)
        else:
            # R31 visual IF/ELSE requires BOTH mutually cancelling native
            # triggers in the SAME disposable Battle. Explicit selection does
            # not change the canonical dispatcher or legacy R9 behaviour.
            require(type(included_event_ids) in (list, tuple) and
                    1 <= len(included_event_ids) <= self.MAX_TIMELINE and
                    all(type(eid) is str for eid in included_event_ids) and
                    len(set(included_event_ids)) == len(included_event_ids) and
                    event_id in included_event_ids,
                    'Invalid explicit debug event selection')
            mission = next(m for m in data['missions'] if m['id'] == mission_id)
            selected_ids = set(included_event_ids)
            self.chain = [deepcopy(row) for row in mission['triggers']
                          if row['id'] in selected_ids]
            require(len(self.chain) == len(selected_ids),
                    'Unknown event in explicit debug selection')
        require(0 < len(self.chain) <= self.MAX_TIMELINE,
                'Debug graph exceeds 200 events')
        self.by_id = {row['id']: row for row in self.chain}
        self.breakpoint_ids = set()
        self.paused_on = None
        self.exhausted = False
        self.timeline = []
        self.last_states = {}
        self._before = None
        self._before_id = None
        self._hazard_cells = {
            tuple(act['pos']) for row in self.chain for act in row['actions']
            if act['kind'] == 'hazard'
        }

        raw = deepcopy(data)
        mission = next(m for m in raw['missions'] if m['id'] == mission_id)
        mission['triggers'] = []
        self.battle = Battle(Content.from_dict(raw, rules=self.rules),
                             mission_id, seed=1, rules=self.rules)
        self.battle.tick = tick
        self.notes = _prepare_scenario(self.battle, selected, scenario)
        # Stage a real interaction in a throwaway battle, but never let the
        # command auto-dispatch the unprepared chain before the first step.
        if scenario == 'satisfied' and selected['condition'] == 'interact':
            self.battle.execute({'kind': 'interact',
                                 'unit': self.battle.active_id,
                                 'object': selected['object']})
            self.notes.append('Commande interact réellement exécutée '
                              '(sans dispatcher les triggers avant le pas)')
        self.battle.mission.triggers = deepcopy(self.chain)
        self.start = _snapshot(self.battle, self._hazard_cells)

    def set_breakpoint(self, event_id, enabled=True):
        require(event_id in self.by_id, 'Event is not part of this debug chain')
        require(type(enabled) is bool, 'Invalid breakpoint state')
        if enabled:
            self.breakpoint_ids.add(event_id)
        else:
            self.breakpoint_ids.discard(event_id)

    def _observe(self, row):
        eid, status = row['event_id'], row['state']
        self.last_states[eid] = deepcopy(row)
        if status == 'fired':
            after = _snapshot(self.battle, self._hazard_cells)
            changes = (_state_changes(self._before, after)
                       if self._before is not None and
                       self._before_id == eid else [])
            self.timeline.append({
                'step': len(self.timeline) + 1,
                'event_id': eid,
                'tick': self.battle.tick,
                'actions': [action_title(act) for act
                            in self.by_id[eid]['actions']],
                'changes': changes,
            })
            self._before = None
            self._before_id = None

    def _step(self, *, honor_breakpoints=False, bypass=None, limit=None):
        if self.exhausted:
            return self.report()
        # Capture a before-state at the SAME point where dispatch validates
        # the canonical registered trigger predicates.
        def before_fire(trigger):
            if (honor_breakpoints and trigger['id'] in self.breakpoint_ids
                    and trigger['id'] != bypass):
                return True
            self._before_id = trigger['id']
            self._before = _snapshot(self.battle, self._hazard_cells)
            return False

        # The Player's command boundary is transactional. Give the disposable
        # debugger the same rollback guarantee if a validated action fails at
        # runtime (for example a spawn colliding with an occupied cell).
        saved_battle = deepcopy(self.battle)
        saved_timeline = deepcopy(self.timeline)
        saved_states = deepcopy(self.last_states)
        try:
            result = triggers.dispatch(
                self.battle, observer=self._observe,
                before_fire=before_fire, fire_limit=limit)
        except Exception:
            self.battle = saved_battle
            self.timeline = saved_timeline
            self.last_states = saved_states
            self._before = None
            self._before_id = None
            raise
        self.paused_on = result['paused']
        if not result['fired'] and self.paused_on is None:
            self.exhausted = True
        if len(self.timeline) == len(self.chain):
            self.exhausted = True
        return self.report()

    def step(self):
        """Execute one actual trigger, ignoring breakpoints for that one step."""
        return self._step(limit=1)

    def continue_to_breakpoint(self):
        """Settle ready events; pause BEFORE the next breakpoint's effects.

        Continue after a pause bypasses that one breakpoint once; otherwise
        pressing Continue repeatedly would stop forever on the same event.
        """
        previous = self.paused_on
        self.paused_on = None
        return self._step(honor_breakpoints=True, bypass=previous)

    def inspect(self, event_id):
        require(event_id in self.by_id, 'Event is not part of this debug chain')
        passed, rows = condition_trace(self.battle, self.by_id[event_id])
        return {'event_id': event_id, 'passed': passed, 'conditions': rows}

    def report(self):
        fired = set(self.battle.fired)
        waiting = []
        for event in self.chain:
            if event['id'] in fired:
                continue
            missing = [p for p in event.get('after', ()) if p not in fired]
            alternatives = event.get('after_any', ())
            if alternatives and not any(p in fired for p in alternatives):
                missing += list(alternatives)
            if missing:
                reason = 'prerequisite'
            else:
                passed, _ = condition_trace(self.battle, event)
                reason = 'ready' if passed else (
                    'choice' if event.get('after_choice') and
                    not any(row['kind'] == 'story_choice' and
                            row.get('scene') == event['after_choice']['scene'] and
                            row.get('choice') == event['after_choice']['choice']
                            for row in self.battle.events)
                    else 'condition')
            waiting.append({'event_id': event['id'],
                            'reason': reason, 'missing': missing})
        clips, scenes = [], []
        if self.project is not None:
            from .cinematics import triggered_tactical_cinematics
            found, _ = triggered_tactical_cinematics(self.project, self.battle)
            clips = [c['id'] for c in found]
            links = self.project.story.get('during_tactical_event', {})
            scenes = [links[self.mission_id + '/' + eid]
                      for eid in self.battle.fired
                      if self.mission_id + '/' + eid in links]
        current = _snapshot(self.battle, self._hazard_cells)
        return {
            'mission_id': self.mission_id,
            'event_id': self.event_id,
            'chain_ids': [e['id'] for e in self.chain],
            'fired_ids': [eid for eid in self.battle.fired if eid in self.by_id],
            'paused_on': self.paused_on,
            'exhausted': self.exhausted,
            'timeline': deepcopy(self.timeline),
            'latest_conditions': deepcopy(self.last_states),
            'waiting': waiting,
            'breakpoints': sorted(self.breakpoint_ids),
            'changes': _state_changes(self.start, current),
            'cinematic_ids': clips,
            'narrative_scene_ids': scenes,
            'notes': list(self.notes),
            'isolated': True,
            'replay_verified': None,
        }


def format_debug_report(report):
    lines = [
        'DÉBOGUEUR TACTIQUE — Battle isolé / prédicats du moteur réel',
        'Chaîne : ' + ' → '.join(report['chain_ids']),
        'Déclenchés : ' + (', '.join(report['fired_ids']) or 'aucun'),
        'Replay : NON ATTESTÉ (état initial de diagnostic non journalisé)',
    ]
    lines += ['Préparation : ' + row for row in report['notes']]
    if report['paused_on']:
        lines.append('POINT D’ARRÊT — avant effets : ' +
                     report['paused_on'])
    for item in report['timeline']:
        lines.append(f"{item['step']}. {item['event_id']} (tick {item['tick']})")
        lines.extend('  Action : ' + x for x in item['actions'])
        lines.extend('  Effet : ' + x for x in item['changes'])
    for row in report['waiting']:
        lines.append('En attente : ' + row['event_id'] +
                     (' ← ' + ', '.join(row['missing'])
                      if row['missing'] else ' (' + row['reason'] + ')'))
    if report['cinematic_ids']:
        lines.append('Cinématiques : ' + ', '.join(report['cinematic_ids']))
    if report['narrative_scene_ids']:
        lines.append('Scènes : ' + ', '.join(report['narrative_scene_ids']))
    if report['exhausted']:
        lines.append('Fin du diagnostic : aucune autre action immédiatement prête')
    return lines
