"""Headless regression gates for the 2.5.5 Project Workspace foundation."""
from copy import deepcopy
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.game_project import GameProject
from sporebound.model import Content, RuleError
from sporebound.workspace import (GROUPS, ProjectWorkspaceIndex,
                                  create_blank_mission, duplicate_mission,
                                  create_campaign)


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.content = Content.load(DEFAULT_CONTENT)
        self.project = GameProject.default(self.content)
        self.data = self.content.to_dict()

    def test_index_uses_existing_documents_and_stable_resource_ids(self):
        index = ProjectWorkspaceIndex(self.content, self.project)
        sections = index.sections()
        self.assertEqual(set(sections), {name for name, _ in GROUPS})
        self.assertEqual(len(sections['campaign']), 1)
        self.assertEqual(len(sections['mission']), len(self.content.missions))
        self.assertEqual(len(sections['skill']), len(self.content.skills))
        self.assertEqual(len(sections['actor']), len(self.content.archetypes))
        self.assertEqual(index.node('campaign:main').id, 'main')
        self.assertTrue(index.node('game:settings').label)
        with self.assertRaises(RuleError):
            index.node('mission:does_not_exist')
        self.assertEqual(index.asset_issues('.'), [])

    def test_blank_mission_preserves_game_and_previous_content(self):
        before = deepcopy(self.data)
        project_before = self.project.to_dict()
        updated = create_blank_mission(self.data, self.project,
                                       'castle_gate', 'Porte du château', 12, 10)
        self.assertEqual(before, self.data)
        self.assertEqual(project_before, self.project.to_dict())
        self.assertIn('castle_gate', Content.from_dict(updated).missions)
        self.assertEqual(ProjectWorkspaceIndex(
            Content.from_dict(updated), self.project).node('mission:castle_gate').label,
            'Porte du château')
        with self.assertRaises(RuleError):
            create_blank_mission(self.data, self.project, 'castle_gate', 'X', 2, 129)
        self.assertEqual(before, self.data)

    def test_duplicate_mission_drops_links_and_is_atomic(self):
        mid = next(iter(self.content.missions))
        updated = duplicate_mission(self.data, self.project, mid,
                                    'castle_copy', 'Assaut alternatif')
        old = next(m for m in self.data['missions'] if m['id'] == mid)
        new = next(m for m in updated['missions'] if m['id'] == 'castle_copy')
        self.assertEqual(new['next_missions'], [])
        self.assertEqual(new['board'], old['board'])
        self.assertEqual(new['units'], old['units'])
        self.assertEqual(Content.from_dict(updated).missions['castle_copy'].name,
                         'Assaut alternatif')
        new['units'][0]['name'] = 'Isolé'
        self.assertNotEqual(new['units'][0]['name'], old['units'][0]['name'])
        before = deepcopy(self.data)
        with self.assertRaises(RuleError):
            duplicate_mission(self.data, self.project, mid, mid, 'Collision')
        with self.assertRaises(RuleError):
            duplicate_mission(self.data, self.project, 'missing', 'other', 'Unknown')
        self.assertEqual(before, self.data)

    def test_campaign_authoring_reuses_project_validation(self):
        mid = next(iter(self.content.missions))
        updated = create_campaign(self.project, self.content, 'siege',
                                  'Le château', mid)
        self.assertEqual(len(updated.campaigns), 2)
        self.assertEqual(updated.campaign('siege')['start_mission'], mid)
        self.assertEqual(len(self.project.campaigns), 1)
        self.assertEqual(GameProject.from_dict(updated.to_dict(),
                                               self.content).to_dict(), updated.to_dict())
        with self.assertRaises(RuleError):
            create_campaign(self.project, self.content, 'main', 'Duplicate', mid)
        with self.assertRaises(RuleError):
            create_campaign(self.project, self.content, 'orphan',
                            'Invalid', 'not_a_mission')
        self.assertEqual(len(self.project.campaigns), 1)


if __name__ == '__main__':
    unittest.main()
