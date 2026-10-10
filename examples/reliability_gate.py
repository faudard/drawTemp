"""Reproducible headless integration gate, using real commands and checkpoints.

python -m examples.reliability_gate --seeds 1 7 42 --output reliability.json
This compact three-mission fixture tests lifecycle, not castle game balance.
"""
import argparse
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from sporebound.ai import choose_command
from sporebound.game_project import GameProject
from sporebound.game_session import GameSession, digest
from sporebound.model import Content, require
from sporebound.persistence import SessionStore
from sporebound.storage import write_json


def fixture():
    missions = []
    for mid in ('gate', 'walls', 'throne'):
        missions.append({'id': mid, 'name': mid, 'board': {'width': 4, 'height': 3},
                         'reward': 100, 'units': [
            {'id': 'captain', 'name': 'Captain', 'team': 'player', 'pos': [1, 1],
             'max_hp': 100, 'hp': 100, 'attack': 5, 'speed': 20},
            {'id': 'guard', 'name': 'Guard', 'team': 'enemy', 'pos': [2, 1],
             'max_hp': 35, 'hp': 35, 'attack': 2, 'speed': 10},
        ]})
    content = Content.from_dict({'version': 1, 'skills': [], 'missions': missions})
    project = GameProject.default(content)
    project.story = {
        'entry_scenes': {'main': 'briefing'}, 'after_mission': {'throne': 'epilogue'},
        'scenes': [
            {'id': 'briefing', 'title': 'Briefing', 'speaker': 'Captain', 'text': 'Two fronts.',
             'choices': [{'id': 'assault', 'label': 'Assault', 'effects': [
                 {'kind': 'set_flag', 'flag': 'route', 'value': 'assault'},
                 {'kind': 'unlock_mission', 'mission': 'walls'},
                 {'kind': 'unlock_mission', 'mission': 'throne'}]}]},
            {'id': 'epilogue', 'title': 'Epilogue', 'speaker': 'Captain', 'text': 'Victory.',
             'choices': [{'id': 'spare', 'label': 'Spare the defenders',
                          'when': {'all': [{'completed_mission': 'gate'},
                                           {'completed_mission': 'walls'}]},
                          'effects': [{'kind': 'set_flag', 'flag': 'ending', 'value': 'mercy'},
                                      {'kind': 'gold', 'amount': 25}]},
                         {'id': 'occupy', 'label': 'Occupy the castle', 'effects': [
                             {'kind': 'set_flag', 'flag': 'ending', 'value': 'occupation'}]}]},
        ]}
    project.validate(content)
    return content, project


def run_case(seed, folder, *, resume=True, ending='spare', checkpoint_every=3):
    """Complete all missions. Reopen disk saves at boundaries and during combat."""
    require(type(checkpoint_every) is int and checkpoint_every > 0, 'Invalid checkpoint interval')
    content, project = fixture()
    session = GameSession.new(content, project, 'main', seed=seed)
    store = SessionStore(Path(folder) / 'session.json')
    checkpoints, max_bytes, commands = 0, 0, 0
    save_seconds, load_seconds, trace = [], [], []

    def checkpoint():
        nonlocal session, checkpoints, max_bytes
        if not resume:
            return
        expected = session.recording()
        start = perf_counter()
        store.save(session)
        save_seconds.append(perf_counter() - start)
        max_bytes = max(max_bytes, store.path.stat().st_size)
        # Reconstruct from disk, not a deepcopy of the live session.
        start = perf_counter()
        session = store.load(content, project)
        load_seconds.append(perf_counter() - start)
        require(session.recording() == expected, f'Checkpoint diverged: seed={seed}')
        checkpoints += 1

    def finish_battle():
        nonlocal commands
        for _ in range(200):
            if session.active_battle.result:
                require(session.active_battle.result == 'victory', f'Unexpected outcome: seed={seed}')
                checkpoint()
                return
            command = choose_command(session.active_battle)
            session.execute(command)
            commands += 1
            trace.append(session.active_battle.digest())
            if commands % checkpoint_every == 0:
                checkpoint()
        raise AssertionError(f'Battle command budget exhausted: seed={seed}')

    checkpoint()
    session.choose_story_option('assault')
    checkpoint()
    session.start_fronts({'gate': 'gate', 'walls': 'walls'}, 'gate',
                         specs={f: {'strength': 50, 'opposition': 50} for f in ('gate', 'walls')})
    session.execute({'kind': 'end'})
    commands += 1
    session.set_doctrine('walls', 'assault')
    session.advance_fronts()
    session.switch_front('walls')
    checkpoint()
    session.execute({'kind': 'end'})
    commands += 1
    session.switch_front('gate')
    finish_battle()
    session.switch_front('walls')
    finish_battle()
    session.advance_fronts()
    session.return_to_campaign()
    checkpoint()
    require(session.progress.completed == ['gate', 'walls'], 'Front rewards missing')
    session.start_mission('throne')
    finish_battle()
    session.return_to_campaign()
    checkpoint()
    session.choose_story_option(ending)
    checkpoint()
    require(session.progress.completed == ['gate', 'walls', 'throne'], 'Campaign incomplete')
    require(session.progress.gold == (325 if ending == 'spare' else 300), 'Rewards duplicated/lost')
    record = session.recording()
    # Independent campaigns intentionally have unique battle UUIDs. Only normalize
    # these identities for cross-run comparison; disk roundtrips above stay exact.
    normalized = deepcopy(record)
    ids = normalized['progress']['tracked_battles']
    require(len(ids) == len(set(ids)) == 3, 'Battle identity lost or duplicated')
    normalized['progress']['tracked_battles'] = [f'battle-{i}' for i in range(len(ids))]
    normalized.pop('digest')
    return {'seed': seed, 'ending': ending, 'digest': digest({'session': normalized, 'trace': trace}),
            'commands': commands, 'checkpoints': checkpoints, 'max_bytes': max_bytes,
            'save_seconds': save_seconds, 'load_seconds': load_seconds,
            'recording': record, 'trace': trace}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', type=int, nargs='+', default=[1, 7, 42])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    results = []
    for seed in args.seeds:
        for ending in ('spare', 'occupy'):
            with TemporaryDirectory() as folder:
                control = run_case(seed, folder, resume=False, ending=ending)
                restored = run_case(seed, folder, ending=ending)
            require(control['digest'] == restored['digest'],
                    f'Uninterrupted/resumed divergence: seed={seed}, ending={ending}')
            restored.pop('recording')
            restored.pop('trace')
            results.append(restored)
    write_json(args.output, {'version': 1, 'verified': True, 'cases': results})
    print(f'Verified {len(results)} campaigns; report: {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
