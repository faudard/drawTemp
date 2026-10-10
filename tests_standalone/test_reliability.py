"""2.4.4 integration gate: complete campaigns, adversarial input and recovery."""
from copy import deepcopy
import json
import os
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from examples.reliability_gate import fixture, run_case
from sporebound.ai import choose_command
from sporebound.game_session import GameSession, digest
from sporebound.game_project import GameProject
from sporebound.model import RuleError
from sporebound.persistence import AutosaveSession, SessionStore


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.content, self.project = fixture()

    def new(self, seed=42):
        session = GameSession.new(self.content, self.project, 'main', seed=seed)
        session.choose_story_option('assault')
        return session

    def test_three_mission_campaigns_match_uninterrupted_and_resumed(self):
        for seed in (1, 7, 42):
            for ending in ('spare', 'occupy'):
                with self.subTest(seed=seed, ending=ending), TemporaryDirectory() as folder:
                    control = run_case(seed, folder, resume=False, ending=ending)
                    restored = run_case(seed, folder, ending=ending, checkpoint_every=1)
                    self.assertEqual(control['digest'], restored['digest'])
                    self.assertEqual(control['trace'], restored['trace'])
                    self.assertGreater(restored['checkpoints'], 8)
                    self.assertEqual(restored['recording']['progress']['heroes']['captain']['xp'], 300)

    def test_invalid_commands_leave_state_rng_journal_and_autosave_unchanged(self):
        rng = random.Random(243)
        invalid = [None, [], 4, 'end', {}, {'kind': []},
                   {'kind': 'act', 'skill': 'missing', 'cell': [2, 1]}]
        invalid += [{'kind': 'move', 'cell': [rng.randint(1000, 9999), -1]}
                    for _ in range(20)]
        for fronts in (False, True):
            with self.subTest(fronts=fronts), TemporaryDirectory() as folder:
                session = self.new()
                if fronts:
                    session.start_fronts({'gate': 'gate', 'walls': 'walls'}, 'gate')
                else:
                    session.start_mission('gate')
                store = SessionStore(Path(folder) / 'save.json')
                store.save(session)
                saved = store.path.read_bytes()
                before = session.recording()
                autosave = AutosaveSession(session, store)
                for command in invalid:
                    with self.subTest(command=command), self.assertRaises(RuleError):
                        autosave.perform('execute', command)
                    self.assertEqual(session.recording(), before)
                    self.assertEqual(store.path.read_bytes(), saved)
                control = GameSession.from_recording(before, self.content, self.project)
                command = choose_command(session.active_battle)
                session.execute(command)
                control.execute(command)
                self.assertEqual(session.recording(), control.recording())

    def test_checkpoint_size_is_measured_as_actual_written_utf8_bytes(self):
        self.project.story['scenes'][0]['choices'][0]['effects'].append(
            {'kind': 'set_flag', 'flag': 'note', 'value': 'Épée du château — 勝利'})
        session = self.new()
        with TemporaryDirectory() as folder:
            full = SessionStore(Path(folder) / 'full.json')
            full.save(session)
            size = full.path.stat().st_size
            too_small = SessionStore(Path(folder) / 'small.json', max_bytes=size - 1)
            with self.assertRaisesRegex(RuleError, 'size limit'):
                too_small.save(session)
            self.assertFalse(too_small.path.exists())
            exact = SessionStore(Path(folder) / 'exact.json', max_bytes=size)
            exact.save(session)
            self.assertEqual(exact.path.stat().st_size, size)
            self.assertEqual(exact.load(self.content, self.project).recording(), session.recording())

    def test_malformed_primary_recovers_without_modifying_files(self):
        with TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'save.json')
            session = self.new()
            store.save(session)
            previous = session.recording()
            session.start_mission('gate')
            store.save(session)
            backup = store.backup.read_bytes()
            corruptions = [b'\xff\xfe', b'{', b'null', b'[]', b'[' * 2000 + b']' * 2000]
            for payload in corruptions:
                with self.subTest(payload=payload[:12]):
                    store.path.write_bytes(payload)
                    result = store.load_with_status(self.content, self.project)
                    self.assertEqual(result.source, 'backup')
                    self.assertEqual(result.session.recording(), previous)
                    self.assertEqual(store.path.read_bytes(), payload)
                    self.assertEqual(store.backup.read_bytes(), backup)

    def test_session_version_rejects_bool_even_with_valid_checksum(self):
        data = self.new().recording()
        data['version'] = True
        data['digest'] = digest({k: v for k, v in data.items() if k != 'digest'})
        with self.assertRaises(RuleError):
            GameSession.from_recording(data, self.content, self.project)

    def test_disk_replace_failure_preserves_both_generations_and_cleans_temporary_file(self):
        with TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'save.json')
            session = self.new()
            store.save(session)
            session.start_mission('gate')
            store.save(session)
            primary, backup = store.path.read_bytes(), store.backup.read_bytes()
            real_replace = os.replace
            for failed_target in (store.backup, store.path):
                def interrupted(source, target):
                    if Path(target) == failed_target:
                        raise OSError('injected interrupted replace')
                    real_replace(source, target)
                with self.subTest(target=failed_target), patch('sporebound.storage.os.replace', side_effect=interrupted):
                    with self.assertRaises(OSError):
                        store.save(session)
                self.assertEqual(store.path.read_bytes(), primary)
                # The backup may have advanced before primary publication failed.
                self.assertIn(store.backup.read_bytes(), (primary, backup))
                self.assertEqual(list(Path(folder).glob('*.tmp')), [])
                self.assertEqual(store.load(self.content, self.project).recording(), session.recording())

    def test_long_journal_replay_survives_repeated_checkpoints(self):
        # Waiting is a valid command and grows CT/RNG-independent event history.
        # No mutation of a live battle to fake completion or checkpoint validity.
        session = self.new()
        session.start_mission('gate')
        with TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'long.json')
            for index in range(120):
                session.execute({'kind': 'end'})
                if index % 30 == 29:
                    before = session.recording()
                    store.save(session)
                    session = store.load(self.content, self.project)
                    self.assertEqual(session.recording(), before)
            self.assertEqual(len(session.battle.commands), 120)
            self.assertGreater(session.battle.tick, 100)
            self.assertIsNone(session.battle.result)

    def test_fresh_process_replays_exact_checkpoint(self):
        session = self.new()
        session.start_mission('gate')
        session.execute(choose_command(session.active_battle))
        with TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'fresh.json')
            store.save(session)
            script = ('from examples.reliability_gate import fixture; '
                      'from sporebound.persistence import SessionStore; import sys; '
                      'c,p=fixture(); print(SessionStore(sys.argv[1]).load(c,p).recording()["digest"])')
            result = subprocess.run([sys.executable, '-c', script, str(store.path)],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.strip(), session.recording()['digest'])

    def test_front_identity_metadata_is_optional_but_strict_when_present(self):
        session = self.new()
        session.start_fronts({'gate': 'gate', 'walls': 'walls'}, 'gate')
        record = session.recording()
        restored = GameSession.from_recording(record, self.content, self.project)
        self.assertEqual(restored.active_battle.battle_id, session.active_battle.battle_id)
        for _ in range(200):
            if session.active_battle.result:
                break
            command = choose_command(session.active_battle)
            session.execute(command)
            restored.execute(command)
        self.assertEqual(session.active_battle.result, 'victory')
        self.assertEqual(restored.recording(), session.recording())
        legacy = deepcopy(record)
        del legacy['front_battle_ids']
        legacy['digest'] = digest({k: v for k, v in legacy.items() if k != 'digest'})
        loaded = GameSession.from_recording(legacy, self.content, self.project)
        self.assertEqual(loaded.fronts.digest(), record['tactical']['digest'])
        for value in (None, {}, {'battles': {'ghost': 'id'}, 'rescue_battles': {},
                                'pursuit_battles': {}, 'recovery_battles': {}}):
            altered = deepcopy(record)
            altered['front_battle_ids'] = value
            altered['digest'] = digest({k: v for k, v in altered.items() if k != 'digest'})
            with self.subTest(value=value), self.assertRaises(RuleError):
                GameSession.from_recording(altered, self.content, self.project)

    def test_castle_narrative_multifront_save_quit_reload_and_continue(self):
        from examples.siege_fronts import siege_session
        template = siege_session(seed=17)
        content = template.content
        project = GameProject.default(content)
        project.campaigns[0]['start_mission'] = template.missions['gate']
        project.story = {'entry_scenes': {'main': 'briefing'}, 'scenes': [
            {'id': 'briefing', 'title': 'Castle', 'speaker': 'Captain', 'text': 'Assault.',
             'choices': [{'id': 'assault', 'label': 'Open the fronts', 'effects': [
                 {'kind': 'set_flag', 'flag': 'route', 'value': 'assault'},
                 *[{'kind': 'unlock_mission', 'mission': mid}
                   for mid in template.missions.values()]]}]}]}
        session = GameSession.new(content, project, 'main', seed=17)
        session.choose_story_option('assault')
        session.start_fronts(template.missions, 'gate', specs=template.initial_specs,
                             links=template.links, logistics=template.initial_logistics)
        session.execute({'kind': 'start_battle'})
        session.execute({'kind': 'end'})
        session.advance_fronts()
        session.switch_front('walls')
        session.execute({'kind': 'start_battle'})
        session.execute({'kind': 'end'})
        before = session.recording()
        with TemporaryDirectory() as folder:
            store = SessionStore(Path(folder) / 'castle.json')
            store.save(session)
            command = choose_command(session.active_battle)
            session.execute(command)
            expected = session.recording()
            del session
            loaded = store.load(content, project)
            self.assertEqual(loaded.recording(), before)
            loaded.execute(command)
            self.assertEqual(loaded.recording(), expected)
            self.assertEqual(loaded.progress.story_flags['route'], 'assault')


if __name__ == '__main__':
    unittest.main()
