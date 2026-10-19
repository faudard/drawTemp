"""R42.B3 Narrative debugger: deterministic, revision-bound *isolated* R1 Simulation.

Conditions are observed through the canonical R9 matches evaluator; decisions
are committed exclusively by Simulation -> GameSession -> StoryBook. No scripts,
alternative predicates, quest ledger or debug state in gameplay checkpoints.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringError, AuthoringSession
from drawtemp.sdk.simulation import Simulation, thaw
from sporebound.campaign import Campaign
from sporebound.model import Content, require
from sporebound.narrative import matches
from sporebound.tactical_rpg3 import authored_rules_for_document

MAX_STEPS = 128


class NarrativeDebugger:
    """A detached test session; never touches the editor, Player or disk."""

    def __init__(self, session: AuthoringSession, campaign_id: str, *, seed=17):
        require(isinstance(session, AuthoringSession),
                'R42 debugger requires the shared AuthoringSession')
        snapshot = session.snapshot().to_dict()
        from sporebound.game_project import GameProject
        content_data = snapshot['content']
        content = Content.from_dict(content_data,
                                    rules=authored_rules_for_document(content_data))
        project = GameProject.from_dict(snapshot['project'], content)
        require(project.story.get('schema_version') == 2,
                'Migrate Narrative Studio v2 before starting the debugger')
        require(project.campaign(campaign_id) is not None, 'Unknown campaign')
        self._session = session
        self.source_revision = session.revision
        self.campaign_id = campaign_id
        self._simulation = Simulation.new(content, project, campaign_id, seed=seed)
        self._project_story = deepcopy(project.story)
        self.breakpoints = set()
        self.paused_on = None
        self._log = []
        self._events = 0

    def _check(self):
        if self._session.revision != self.source_revision:
            raise AuthoringError('stale_revision', 'narrative_debug',
                                 'The project changed; restart narrative debugging')

    def _snapshot(self):
        return self._simulation.snapshot()

    def _progress(self, snap):
        return Campaign.from_dict({'version': 1, **thaw(snap.progress)})

    def _choice(self, scene, choice_id):
        return next((choice for choice in scene['choices']
                     if choice['id'] == choice_id), None)

    def condition_trace(self, expression):
        """Evaluate with R9; leaf details are diagnostics, never authority."""
        self._check()
        snap = self._snapshot()
        progress = self._progress(snap)
        result = bool(matches(expression, progress))
        def branches(node):
            row = {'expression': deepcopy(node),
                   'passed': bool(matches(node, progress))}
            if 'all' in node or 'any' in node:
                key = 'all' if 'all' in node else 'any'
                row['children'] = [branches(item) for item in node[key]]
            elif 'not' in node:
                row['children'] = [branches(node['not'])]
            elif 'flag' in node:
                row['observed'] = deepcopy(progress.story_flags.get(node['flag']))
            elif 'gold_gte' in node:
                row['observed'] = progress.gold
            elif 'completed_mission' in node:
                row['observed'] = node['completed_mission'] in progress.completed
            return row
        detail = branches(expression)
        require(detail['passed'] == result, 'R42 diagnostic differs from R9')
        return detail

    def inspect(self, choice_id=None):
        """Read-only condition analysis and current values, no advance."""
        self._check()
        snap = self._snapshot()
        scene = thaw(snap.scene)
        line = thaw(self._simulation.narrative_line(
            expected_revision=snap.revision))
        if not scene:
            return {'scene': None, 'line': None, 'choices': []}
        rows = []
        for choice in scene['choices']:
            if choice_id is not None and choice['id'] != choice_id:
                continue
            when = choice.get('when')
            evaluation = self.condition_trace(when) if when is not None else {
                'expression': None, 'passed': True}
            rows.append({'id': choice['id'], 'label': choice['label'],
                         'target': choice.get('next_scene', ''),
                         'available': evaluation['passed'] and bool(
                             not line or line['complete']),
                         'condition': evaluation,
                         'effects': deepcopy(choice.get('effects', []))})
        if choice_id is not None:
            require(rows, 'Unknown authored R42 choice')
        return {'scene': {'id': scene['id'], 'title': scene['title']},
                'line': line, 'choices': rows}

    def breakpoint(self, scene_id, choice_id, enabled=True):
        """Stop *before* a choice can apply its canonical effects."""
        self._check()
        require(type(enabled) is bool, 'Invalid breakpoint enabled flag')
        scene = next((s for s in self._project_story['scenes']
                      if s['id'] == scene_id), None)
        require(scene is not None and self._choice(scene, choice_id) is not None,
                'Breakpoint must target an authored narrative choice')
        key = (scene_id, choice_id)
        if enabled:
            require(len(self.breakpoints) < 64 or key in self.breakpoints,
                    'Too many narrative breakpoints')
            self.breakpoints.add(key)
        else:
            self.breakpoints.discard(key)
            if self.paused_on == key:
                self.paused_on = None
        return self.report()

    def _commit(self, kind, choice_id=None):
        """Single transactional canonical R1 command, with before/after diff."""
        self._check()
        require(self._events < MAX_STEPS, 'R42 debugger step budget reached')
        before = self._snapshot()
        before_progress = thaw(before.progress)
        current = thaw(before.scene)
        require(current is not None, 'No active R42 dialogue')
        if kind == 'line':
            self._simulation.advance_narrative_line(
                expected_revision=before.revision)
        else:
            self._simulation.choose_story_option(
                choice_id, expected_revision=before.revision)
        after = self._snapshot()
        after_progress = thaw(after.progress)
        previous_flags = before_progress['story_flags']
        next_flags = after_progress['story_flags']
        changed = [{'key': key, 'before': deepcopy(previous_flags.get(key)),
                    'after': deepcopy(next_flags.get(key))}
                   for key in sorted(set(previous_flags) | set(next_flags))
                   if previous_flags.get(key) != next_flags.get(key)]
        event = {
            'kind': kind, 'scene': current['id'], 'choice': choice_id,
            'source_revision': before.revision, 'revision': after.revision,
            'next_scene': thaw(after.scene).get('id', '') if after.scene else '',
            'flags': changed,
            'gold_delta': after_progress['gold'] - before_progress['gold'],
            'history_delta': len(after_progress['story_history']) -
                             len(before_progress['story_history']),
            'unlocked_added': sorted(set(after_progress['unlocked']) -
                                     set(before_progress['unlocked'])),
        }
        self._log.append(event)
        self._events += 1
        self.paused_on = None
        return self.report()

    def advance_line(self):
        return self._commit('line')

    def choose(self, choice_id):
        """An armed breakpoint never mutates progress until explicit step."""
        self._check()
        snap = self._snapshot()
        scene = thaw(snap.scene)
        require(scene is not None, 'No active R42 dialogue')
        require(type(choice_id) is str and
                self._choice(scene, choice_id) is not None,
                'Unknown authored choice')
        key = (scene['id'], choice_id)
        available = {row['id'] for row in self.inspect()['choices']
                     if row['available']}
        require(choice_id in available, 'Narrative choice is locked')
        if key in self.breakpoints:
            self.paused_on = key
            return self.report()
        return self._commit('choice', choice_id)

    def step(self):
        """Advance a paused choice or one line; no invented choice selection."""
        self._check()
        if self.paused_on is not None:
            scene_id, choice_id = self.paused_on
            current = self.inspect()
            require(current['scene'] is not None
                    and current['scene']['id'] == scene_id,
                    'Paused narrative scene changed')
            return self._commit('choice', choice_id)
        current = self.inspect()
        require(current['line'] is not None and not current['line']['complete'],
                'Select an available choice or a breakpoint to step')
        return self.advance_line()

    def report(self):
        self._check()
        snap = self._snapshot()
        progress = thaw(snap.progress)
        scene = thaw(snap.scene)
        return {
            'source_revision': self.source_revision,
            'revision': snap.revision,
            'campaign_id': self.campaign_id,
            'scene': scene['id'] if scene is not None else '',
            'line': thaw(self._simulation.narrative_line(
                expected_revision=snap.revision)),
            'paused_on': list(self.paused_on) if self.paused_on else None,
            'breakpoints': [list(key) for key in sorted(self.breakpoints)],
            'flags': deepcopy(progress['story_flags']),
            'gold': progress['gold'],
            'history': deepcopy(progress['story_history']),
            'events': deepcopy(self._log),
            'choices': self.inspect()['choices'],
            'isolated': True,
            'replay_verified': None,
        }
