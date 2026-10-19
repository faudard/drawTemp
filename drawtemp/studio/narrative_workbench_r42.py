"""R42.B1 Narrative Studio authoring facade on the single R1 AuthoringSession.

All mutations compile to existing GameProject.story and are only committed
through preview/apply. The facade does not save files or create a second history.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.authoring import AuthoringSession
from sporebound.model import Content, RuleError, require
from sporebound.narrative_r42 import (
    migrate_story_v1, set_dialogue_lines, declare_subgraph, line_references,
)
from sporebound.narrative_state_r42 import declare_state, state_key


class NarrativeWorkbench:
    def __init__(self, session):
        require(isinstance(session, AuthoringSession), 'R42 needs the shared AuthoringSession')
        self.session = session

    def document(self):
        snapshot = self.session.snapshot().to_dict()
        return deepcopy(snapshot['project'].get('story', {}))

    def _content(self):
        raw = self.session.snapshot().to_dict()['content']
        from sporebound.tactical_rpg3 import authored_rules_for_document
        return Content.from_dict(raw, rules=authored_rules_for_document(raw))

    def _edit(self, operation, *, kind):
        return self.session.preview_project(
            lambda project: operation(project).to_dict(), kind=kind)

    def preview_migrate(self):
        content = self._content()
        return self._edit(lambda project: migrate_story_v1(project, content),
                          kind='r42-migrate-story')

    def preview_lines(self, scene_id, lines):
        content = self._content()
        lines = deepcopy(lines)
        return self._edit(lambda project: set_dialogue_lines(
            project, content, scene_id, lines), kind='r42-dialogue-lines')

    def preview_state(self, *, identifier, kind, scope, owner, initial):
        content = self._content()
        return self._edit(lambda project: declare_state(
            project, content, identifier=identifier, kind=kind,
            scope=scope, owner=owner, initial=initial),
            kind='r42-declare-state')

    def preview_subgraph(self, identifier, entry_scene):
        content = self._content()
        return self._edit(lambda project: declare_subgraph(
            project, content, identifier, entry_scene),
            kind='r42-declare-subgraph')

    def preview_link(self, source, choice_id, target):
        from sporebound.story_authoring import link_choice
        content = self._content()
        return self._edit(lambda project: link_choice(
            project, content, source, choice_id, target),
            kind='r42-link-choice')

    def preview_create_scene(self, scene_id, title, speaker, text):
        """Create canonical v2 scene; never construct an invalid v1-style scene."""
        content = self._content()
        def mutate(project):
            from sporebound.game_project import GameProject
            data = deepcopy(project)
            story = data.get('story', {})
            require(story.get('schema_version') == 2,
                    'Migrate to R42 v2 before authoring dialogue')
            require(not any(s['id'] == scene_id for s in story['scenes']),
                    'Duplicate narrative scene')
            story['scenes'].append({
                'id': scene_id, 'title': title, 'speaker': speaker, 'text': text,
                'lines': [{'id': 'line_001', 'speaker': speaker, 'text': text}],
                'choices': [{'id': 'continue', 'label': 'Continuer'}]})
            return GameProject.from_dict(data, content)
        return self._edit(mutate, kind='r42-create-scene')

    def apply(self, plan):
        return self.session.apply(plan)

    def undo(self):
        return self.session.undo()

    def redo(self):
        return self.session.redo()

    def inspect(self, scene_id):
        """Detached canonical source/usage and typed effects for one scene."""
        story = self.document()
        scenes = {s['id']: s for s in story.get('scenes', [])}
        require(scene_id in scenes, 'Unknown R42 narrative scene')
        incoming = []
        for source in story['scenes']:
            for choice in source['choices']:
                if choice.get('next_scene') == scene_id:
                    incoming.append({'scene': source['id'], 'choice': choice['id']})
        for kind in ('entry_scenes', 'after_mission',
                     'after_strategic_event', 'during_tactical_event'):
            for origin, target in story.get(kind, {}).items():
                if target == scene_id:
                    incoming.append({'source': kind, 'id': origin})
        for subgraph in story.get('subgraphs', []):
            if subgraph['entry_scene'] == scene_id:
                incoming.append({'source': 'subgraph', 'id': subgraph['id']})
        scene = scenes[scene_id]
        return {'scene': deepcopy(scene),
                'incoming': sorted(incoming, key=lambda x: (x.get('source',''),
                                                          x.get('scene',''),
                                                          x.get('id',''),
                                                          x.get('choice',''))),
                'outgoing': deepcopy(scene['choices']),
                'line_ids': tuple(scene_id + '/' + line['id']
                                  for line in scene.get('lines', [])),
                'state': deepcopy(story.get('state', []))}

    def graph(self):
        """Finite, detached read-only projection, including shared destinations."""
        story = self.document()
        nodes = [{'id': s['id'], 'title': s['title']}
                 for s in story.get('scenes', [])]
        edges = [{'from': s['id'], 'choice': c['id'],
                  'to': c['next_scene'], 'label': c['label']}
                 for s in story.get('scenes', [])
                 for c in s['choices'] if 'next_scene' in c]
        return {'nodes': nodes, 'edges': edges,
                'entries': deepcopy(story.get('entry_scenes', {})),
                'subgraphs': deepcopy(story.get('subgraphs', [])),
                'version': story.get('schema_version', 1),
                'revision': self.session.revision}
