"""R1 core independence, UI-facing state and canonical simulation parity."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from drawtemp.core import GameSession
from drawtemp.sdk.migration import comparable
from drawtemp.sdk.reference import MISSION, reference_project
from drawtemp.sdk.simulation import Simulation, SimulationError
from scripts.audit_drawtemp5 import inventory
from sporebound.ai import choose_command


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = reference_project()
        self.sdk = Simulation.new(self.content, self.project, 'main')

    def battle(self):
        self.sdk.choose_story_option('enter')
        self.sdk.start_mission(MISSION)
        return {'kind': 'interact', 'unit': 'jeanne', 'object': 'lever'}

    def test_deeply_immutable_detached_snapshot_and_json_export(self):
        command = self.battle()
        before = self.sdk.snapshot()
        with self.assertRaises(FrozenInstanceError):
            before.mode = 'oops'
        with self.assertRaises(TypeError):
            before.battle['units'][0]['hp'] = 999
        with self.assertRaises(TypeError):
            before.progress['gold'] = 999
        exported = before.to_dict()
        json.dumps(exported)
        exported['battle']['units'][0]['hp'] = 999
        self.sdk.execute(command)
        self.assertNotEqual(before.revision, self.sdk.snapshot().revision)
        self.assertNotEqual(before.battle['units'][0]['hp'], 999)
        self.assertEqual(before.battle['events'], tuple(before.battle['events']))

    def test_preview_purity_and_stale_result_rejected(self):
        command = self.battle()
        recording = self.sdk.recording()
        revision = self.sdk.snapshot().revision
        preview = self.sdk.preview(command, expected_revision=revision)
        self.assertEqual(self.sdk.recording(), recording)
        self.assertEqual(preview.source_revision, revision)
        result = self.sdk.execute(command, expected_revision=preview.source_revision)
        self.assertEqual(result.snapshot, preview.snapshot)
        self.assertEqual(result.events, preview.events)
        committed = self.sdk.recording()
        with self.assertRaises(SimulationError) as error:
            self.sdk.execute(command, expected_revision=preview.source_revision)
        self.assertEqual(error.exception.code, 'stale_revision')
        self.assertEqual(self.sdk.recording(), committed)

    def test_rejected_action_keeps_revision_and_full_state(self):
        self.battle()
        before, snapshot = self.sdk.recording(), self.sdk.snapshot()
        with self.assertRaises(SimulationError) as error:
            self.sdk.execute({'kind': 'unknown'})
        self.assertEqual(error.exception.code, 'invalid_action')
        self.assertEqual(error.exception.operation, 'execute')
        self.assertEqual(self.sdk.recording(), before)
        self.assertEqual(self.sdk.snapshot(), snapshot)

    def test_only_new_native_events_are_returned_and_payload_is_frozen(self):
        command = self.battle()
        result = self.sdk.execute(command)
        interactions = [event for event in result.events if event.kind == 'interact']
        self.assertEqual(len(interactions), 1)
        self.assertEqual(interactions[0].payload['object'], 'lever')
        with self.assertRaises(TypeError):
            interactions[0].payload['object'] = 'forged'
        following = self.sdk.execute({'kind': 'end', 'facing': [0, 1]})
        self.assertFalse(any(event.kind == 'interact' for event in following.events))
        self.assertEqual([event.index for event in result.events], list(range(len(result.events))))

    def test_simulation_is_bounded_and_does_not_mutate_live_session(self):
        self.sdk.execute(self.battle())
        original = self.sdk.recording()
        first = self.sdk.simulate(max_steps=700)
        self.assertEqual(first.battle['result'], 'victory')
        self.assertEqual(first, self.sdk.simulate(max_steps=700))
        self.assertEqual(self.sdk.recording(), original)
        with self.assertRaises(SimulationError):
            self.sdk.simulate(max_steps=True)
        with self.assertRaises(SimulationError):
            self.sdk.simulate(max_steps=1001)
        limited = self.sdk.simulate(max_steps=1)
        self.assertLessEqual(limited.revision, self.sdk.snapshot().revision + 1)

    def test_complete_mission_resume_replay_and_legacy_state_match(self):
        legacy = GameSession.new(self.content, self.project, 'main', seed=17)
        for session in (legacy, self.sdk):
            session.choose_story_option('enter')
            session.start_mission(MISSION)
            session.execute({'kind': 'interact', 'unit': 'jeanne', 'object': 'lever'})
        self.assertEqual(comparable(legacy.recording()), comparable(self.sdk.recording()))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            self.sdk.save(path)
            raw = path.read_bytes()
            self.sdk = Simulation.load(path, self.content, self.project)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(self.sdk.snapshot().revision, 0)
            for _ in range(700):
                if legacy.active_battle.result:
                    break
                command = choose_command(legacy.active_battle)
                legacy.execute(command)
                self.sdk.execute(command)
                self.assertEqual(comparable(legacy.recording()), comparable(self.sdk.recording()))
            self.assertEqual(self.sdk.snapshot().battle['result'], 'victory')
            self.sdk.save(path)
            replay = GameSession.load(path, self.content, self.project)
            self.assertEqual(comparable(replay.recording()), comparable(legacy.recording()))
            self.sdk.return_to_campaign()
            self.assertEqual(self.sdk.snapshot().mode, 'campaign')

    def test_save_compatibility_and_io_errors_are_explicit(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'session.json'
            self.sdk.save(path)
            before = path.read_bytes()
            changed = deepcopy(self.project)
            changed.title += ' different'
            with self.assertRaises(SimulationError) as error:
                Simulation.load(path, self.content, changed)
            self.assertEqual(error.exception.code, 'incompatible_save')
            self.assertEqual(path.read_bytes(), before)
            with self.assertRaises(SimulationError) as error:
                Simulation.load(path.with_name('missing.json'), self.content, self.project)
            self.assertEqual(error.exception.code, 'io_error')

    def test_full_static_import_closure_is_headless(self):
        report = inventory()
        self.assertEqual(report['headless_violations'], [])
        self.assertEqual(report['deferred_ui_paths_to_extract_in_r1'], [])

    def test_runtime_structure_authoring_and_sdk_without_graphics_imports(self):
        script = '''
import sys
class NoUI:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('tkinter', '_tkinter', 'PySide6', 'PyQt6', 'PyQt5'):
            raise AssertionError(fullname)
sys.meta_path.insert(0, NoUI())
from drawtemp.sdk.reference import reference_project, MISSION
from drawtemp.sdk.simulation import Simulation
from sporebound.iso_structures import structure_at, remove_structure
from sporebound.architecture_model import architecture_instances
from sporebound.model import Content
from pathlib import Path
content = Content.load(Path('sporebound/content/core.json'))
for mission in content.missions.values():
    architecture_instances(mission.board, mission.structures)
from tests_standalone.test_structure_editing_3719b import *
import unittest
suite = unittest.defaultTestLoader.loadTestsFromName('tests_standalone.test_structure_editing_3719b')
assert unittest.TextTestRunner().run(suite).wasSuccessful()
c,p=reference_project(); sim=Simulation.new(c,p,'main');sim.choose_story_option('enter')
sim.start_mission(MISSION);sim.execute({'kind':'interact','unit':'jeanne','object':'lever'})
assert sim.simulate(max_steps=700).battle['result'] == 'victory'
'''
        subprocess.run([sys.executable, '-c', script], check=True, capture_output=True,
                       text=True, cwd=Path(__file__).resolve().parents[1])


if __name__ == '__main__':
    unittest.main()
