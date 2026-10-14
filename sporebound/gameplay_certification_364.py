"""3.6.4: evidence-backed coverage of real GameSession narrative paths.

A *certified* path is an authored, executed GameSession command script with
an exact serialized checkpoint replay after EVERY step and explicit expected
observations. This is stronger than StoryBook probes or isolated Battle
previews; it is NOT a proof of all reachable runtime states.

Reports omit nondeterministic Battle UUIDs. Full checkpoints remain checked
via GameSession.from_recording, whose Battle journal is replayed by the engine.
"""
from copy import deepcopy
import hashlib
import json

from .game_project import GameProject
from .game_session import GameSession
from .model import Content, RuleError, require
from .story_graph_navigation import navigation_diagnostics
from .tactical_rpg3 import authored_rules_for_document


STEP_KINDS = ('campaign_choice', 'start_mission', 'tactical_choice',
              'command', 'ai_turn', 'abandon_encounter', 'return_to_campaign')


def _digest(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def _validate_case(spec):
    require(isinstance(spec, dict) and
            set(spec) == {'id', 'campaign', 'seed', 'steps'},
            'Invalid gameplay certification case')
    require(isinstance(spec['id'], str) and 1 <= len(spec['id']) <= 64
            and all(ch.isalnum() or ch in '-_' for ch in spec['id']),
            'Invalid certification case ID')
    require(isinstance(spec['campaign'], str) and bool(spec['campaign']),
            'Missing certification campaign')
    require(type(spec['seed']) is int and 0 <= spec['seed'] < 2**32,
            'Invalid certification seed')
    steps = spec['steps']
    require(isinstance(steps, list) and 1 <= len(steps) <= 80,
            'A certification case requires 1..80 steps')
    for step in steps:
        require(isinstance(step, dict) and set(step) in (
            {'kind', 'choice', 'expect'}, {'kind', 'mission', 'expect'},
            {'kind', 'command', 'expect'}, {'kind', 'expect'}),
            'Invalid certification step shape')
        kind = step['kind']
        require(kind in STEP_KINDS, 'Unknown certified gameplay command')
        if kind in ('campaign_choice', 'tactical_choice'):
            require(set(step) == {'kind', 'choice', 'expect'} and
                    isinstance(step['choice'], str) and bool(step['choice']),
                    'Certified narrative choice needs choice ID')
        elif kind == 'start_mission':
            require(set(step) == {'kind', 'mission', 'expect'} and
                    isinstance(step['mission'], str) and bool(step['mission']),
                    'Certified start_mission needs mission ID')
        elif kind == 'command':
            require(set(step) == {'kind', 'command', 'expect'} and
                    isinstance(step['command'], dict),
                    'Certified Battle command needs a typed command')
            require(step['command'].get('kind') != 'story_effects',
                    'Cannot inject or fake a narrative story_effects command')
        else:
            require(set(step) == {'kind', 'expect'},
                    'Unexpected step fields')
        require(isinstance(step['expect'], dict) and bool(step['expect']),
                'Certification requires explicit expectations on every step')
        require(set(step['expect']) <= {
            'mode', 'pending_campaign', 'pending_tactical', 'flags',
            'history', 'fired', 'fired_exact', 'not_fired',
            'completed', 'unlocked', 'gold', 'inventory',
            'battle_result', 'hazards'},
            'Unsupported certified observation')


def _validate_suite(suite):
    require(isinstance(suite, dict) and set(suite) == {
        'version', 'cases', 'required_choices', 'required_events',
        'min_passed_paths'}, 'Invalid certification suite')
    require(type(suite['version']) is int and suite['version'] == 1,
            'Unsupported gameplay certification suite version')
    cases = suite['cases']
    require(isinstance(cases, list) and 1 <= len(cases) <= 20,
            'Certification requires 1..20 scripted paths')
    for case in cases:
        _validate_case(case)
    require(len({c['id'] for c in cases}) == len(cases),
            'Duplicate certification path ID')
    for key in ('required_choices', 'required_events'):
        ids = suite[key]
        require(isinstance(ids, list) and len(ids) <= 300 and
                all(isinstance(value, str) and bool(value) for value in ids)
                and len(set(ids)) == len(ids),
                'Invalid required coverage IDs')
    require(type(suite['min_passed_paths']) is int and
            1 <= suite['min_passed_paths'] <= len(cases),
            'Invalid minimum certified path count')


def _observe(session, tracked_hazards=()):
    battle = session.active_battle
    cells = {}
    if battle is not None:
        for x, y in tracked_hazards:
            cells[str(x)+','+str(y)] = battle.board.tile((x, y)).hazard
    return {
        'mode': session.mode,
        'pending_campaign': session.progress.story_pending,
        'pending_tactical': session.tactical_story_pending,
        'flags': deepcopy(session.progress.story_flags),
        'history': deepcopy(session.progress.story_history),
        'fired': sorted(battle.fired) if battle is not None else [],
        'completed': sorted(session.progress.completed),
        'unlocked': sorted(session.progress.unlocked),
        'gold': session.progress.gold,
        'inventory': deepcopy(session.progress.inventory),
        'battle_result': battle.result if battle is not None else None,
        # Battle.state excludes its random UUID; its digest captures the
        # full deterministic tactical state, including tiles, units and RNG.
        'battle_digest': battle.digest() if battle is not None else None,
        'hazards': cells,
    }


def _assert_expected(observed, expected):
    failures = []
    for key, reference in expected.items():
        if key == 'fired':
            missing = sorted(set(reference) - set(observed['fired']))
            if missing:
                failures.append('Missing fired events: '+repr(missing))
        elif key == 'not_fired':
            wrongly_fired = sorted(set(reference) & set(observed['fired']))
            if wrongly_fired:
                failures.append('Unexpected fired events: '+repr(wrongly_fired))
        elif key == 'fired_exact':
            if sorted(reference) != observed['fired']:
                failures.append('Fired events differ: expected '+
                                repr(sorted(reference))+', got '+
                                repr(observed['fired']))
        elif key == 'flags':
            for flag, value in reference.items():
                observed_flag = observed['flags'].get(flag)
                if type(observed_flag) is not type(value) or observed_flag != value:
                    failures.append('Flag '+flag+': expected '+repr(value)+
                                    ', got '+repr(observed_flag))
        elif key == 'hazards':
            for cell, value in reference.items():
                if observed['hazards'].get(cell) != value:
                    failures.append('Hazard '+cell+': expected '+repr(value)+
                                    ', got '+repr(observed['hazards'].get(cell)))
        elif observed.get(key) != reference:
            failures.append(key+': expected '+repr(reference)+
                            ', got '+repr(observed.get(key)))
    return failures


def _perform(session, step):
    kind = step['kind']
    if kind == 'campaign_choice':
        scene = session.active_scene()
        require(scene is not None, 'No campaign dialogue at certified step')
        sid = scene['id']
        session.choose_story_option(step['choice'])
        return sid+'/'+step['choice']
    if kind == 'start_mission':
        session.start_mission(step['mission'])
        return ''
    if kind == 'tactical_choice':
        scene = session.tactical_scene()
        sid = scene['id']
        session.choose_tactical_story_option(step['choice'])
        return sid+'/'+step['choice']
    if kind == 'command':
        session.execute(deepcopy(step['command']))
        return ''
    if kind == 'ai_turn':
        session.ai_turn()
        return ''
    if kind == 'return_to_campaign':
        session.return_to_campaign()
        return ''
    session.abandon_encounter()
    return ''


def execute_certified_path(content, project, spec, *, rules=None):
    """Run one real route, verify each replay, and retain an exact oracle."""
    _validate_case(spec)
    rules = rules if rules is not None else authored_rules_for_document(
        content.to_dict())
    session = GameSession.new(
        content, project, spec['campaign'], seed=spec['seed'], rules=rules)
    evidence = []
    fired_seen = set()
    choices_seen = set()
    failures = []
    for index, step in enumerate(spec['steps']):
        try:
            selected = _perform(session, step)
            if selected:
                choices_seen.add(selected)
            hazards = []
            for cell in step['expect'].get('hazards', {}):
                x, y = map(int, cell.split(','))
                hazards.append((x, y))
            checkpoint = session.recording()
            restored = GameSession.from_recording(
                checkpoint, content, project, rules=rules)
            require(restored.recording() == checkpoint,
                    'Checkpoint differs from replayed GameSession recording')
            observed = _observe(restored, hazards)
            failed = _assert_expected(observed, step['expect'])
            fired_seen.update(observed['fired'])
            evidence.append({
                'index': index, 'kind': step['kind'],
                'choice_id': selected,
                'replay_verified': True,
                'checkpoint_digest': checkpoint['digest'],
                'observed': observed,
                'errors': failed,
            })
            failures.extend('step '+str(index)+': '+x for x in failed)
            # Resume from the freshly replayed, validated checkpoint.
            session = restored
        except (RuleError, ValueError, KeyError, IndexError,
                TypeError, AttributeError) as exc:
            failures.append('step '+str(index)+': '+str(exc))
            evidence.append({
                'index': index, 'kind': step['kind'],
                'choice_id': '',
                'replay_verified': False,
                'errors': [str(exc)],
            })
            break
    success = len(evidence) == len(spec['steps']) and not failures
    final = (evidence[-1].get('observed', {}) if evidence else {})
    return {
        'id': spec['id'], 'campaign': spec['campaign'],
        'seed': spec['seed'], 'passed': success,
        'replay_verified': success,
        'steps_executed': len(evidence),
        'choices': sorted(choices_seen),
        'events': sorted(fired_seen),
        'final': final,
        'checkpoints': evidence, 'errors': failures,
    }


def _semantic_path(row):
    """Stable across OS and fresh Battle UUIDs, intentionally not a digest."""
    return {
        'id': row['id'], 'passed': row['passed'],
        'choices': row['choices'], 'events': row['events'],
        'steps': [{
            'kind': p['kind'], 'choice_id': p['choice_id'],
            'observed': p.get('observed'), 'errors': p['errors'],
            'replay_verified': p['replay_verified'],
        } for p in row['checkpoints']],
    }


def certify_gameplay_paths(data, project, suite, *, baseline=None):
    """Return evidence report with CI gates; NEVER suppress path failures.

    A previous baseline can be the report['semantic_baseline'] of a known
    good CI run. Baselines compare meaningful gameplay facts, not volatile
    session or battle UUIDs. Real artifacts can be separately retained.
    """
    _validate_suite(suite)
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project.validate(content)
    results = [
        execute_certified_path(content, project, case, rules=rules)
        for case in suite['cases']
    ]
    passed = [row for row in results if row['passed']]
    choices = sorted({c for row in passed for c in row['choices']})
    events = sorted({e for row in passed for e in row['events']})
    missing_choices = sorted(set(suite['required_choices']) - set(choices))
    missing_events = sorted(set(suite['required_events']) - set(events))
    # The denominator is only structurally reachable authored choices.
    # Conditional choices count as possible even if no oracle proved them
    # available in the tested GameSession states.
    statuses = {r['scene_id']: r['status']
                for r in navigation_diagnostics(project.story)['records']}
    authored = {
        scene['id']+'/'+choice['id']
        for scene in project.story.get('scenes', [])
        if statuses.get(scene['id']) in ('reachable', 'conditional_only')
        for choice in scene['choices']
    }
    covered_authored = sorted(authored.intersection(choices))
    semantic = {
        row['id']: _semantic_path(row)
        for row in results
    }
    baseline_errors = []
    if baseline is not None:
        require(isinstance(baseline, dict) and
                set(baseline) == set(semantic),
                'Baseline scenario IDs differ from certification suite')
        for cid, current in semantic.items():
            if current != baseline[cid]:
                baseline_errors.append('Gameplay changed for path '+cid)
    gate_errors = [
        'Fewer certified paths than minimum '+str(suite['min_passed_paths'])
    ] if len(passed) < suite['min_passed_paths'] else []
    if missing_choices:
        gate_errors.append('Required choices not certified: '+
                           ', '.join(missing_choices))
    if missing_events:
        gate_errors.append('Required events not certified: '+
                           ', '.join(missing_events))
    gate_errors.extend(baseline_errors)
    for row in results:
        for failure in row['errors']:
            gate_errors.append(row['id']+': '+failure)
    return {
        'version': 1, 'kind': 'game_session_path_certification',
        'passed': not gate_errors, 'replay_verified': (
            not gate_errors and bool(passed)),
        'paths': results, 'passed_paths': len(passed),
        'total_paths': len(results),
        'certified_choices': choices, 'certified_events': events,
        'structurally_reachable_choice_count': len(authored),
        'certified_reachable_choice_count': len(covered_authored),
        'certified_reachable_choice_percent': (
            round(100.0 * len(covered_authored)/len(authored), 2)
            if authored else 0.0),
        'missing_choices': missing_choices, 'missing_events': missing_events,
        'semantic_baseline': semantic, 'baseline_compared': baseline is not None,
        'gate_errors': gate_errors,
        'evidence': ('Real GameSession actions; every GameSession.recording() '
                     'restored via GameSession.from_recording() and compared '
                     'byte-for-byte as JSON data. Tactical journals are replayed '
                     'by Battle; campaign progress is restored/validated, '
                     'not independently reconstructed from all past actions.'),
    }


def enforce_certification(report):
    """Non-zero CI failure via a strict exception for missing evidence."""
    require(report.get('kind') == 'game_session_path_certification',
            'Not a GameSession certification report')
    require(report['passed'] is True and
            report['replay_verified'] is True and
            not report['gate_errors'],
            'Gameplay path certification failed: '+
            '; '.join(report['gate_errors'][:8]))
    return report


def format_certification(report, *, max_rows=12):
    rows = [
        'GAMESESSION PATH CERTIFICATION — CHECKPOINT REPLAY',
        'Parcours : %d/%d vérifiés · Choix : %d · Événements : %d' %
        (report['passed_paths'], report['total_paths'],
         len(report['certified_choices']), len(report['certified_events'])),
        'Couverture du graphe atteignable : %d/%d choix (%.2f %%)' %
        (report['certified_reachable_choice_count'],
         report['structurally_reachable_choice_count'],
         report['certified_reachable_choice_percent']),
        'Gate : '+('PASS' if report['passed'] else 'FAIL'),
    ]
    for row in report['paths'][:max_rows]:
        rows.append(
            row['id']+': '+('PASS' if row['passed'] else 'FAIL')+
            ' · '+str(row['steps_executed'])+' étape(s)')
        rows.extend('  '+err for err in row['errors'][:5])
    rows.extend('ÉCHEC : '+error for error in report['gate_errors'][:max_rows])
    rows.append('Preuve : '+report['evidence'])
    return rows
