"""3.6.3 Branch QA: static checks and reproducible, isolated StoryBook probes.

A report makes no claim about actual mission completion. The 'story' probe
calls the production StoryBook.choices/choose code on disposable Campaign
states seeded at authored roots. Tactical probes use the existing isolated
Battle preview and explicitly do NOT certify GameSession replay.
"""
from collections import deque
from copy import deepcopy
import json

from .campaign import Campaign
from .event_branches import preview_choice_routes
from .game_project import GameProject
from .model import Content, RuleError, require
from .narrative import StoryBook
from .story_graph_navigation import entry_scene_ids, navigation_diagnostics
from .tactical_rpg3 import authored_rules_for_document


def _key(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _conjuncts(expression):
    """Flatten AND only; OR and negations must not be assumed conjunctive."""
    if 'all' in expression:
        result = []
        for part in expression['all']:
            result.extend(_conjuncts(part))
        return result
    return [expression]


def condition_contradiction(expression):
    """Return a proof of a narrow logical contradiction, otherwise ''.

    No unsupported assertion of satisfiability: external resources and
    possible story_flags are not modeled. OR is contradictory only if every
    alternative is contradictory. Not of arbitrary expressions is unknown.
    """
    if expression is None:
        return ''
    if 'any' in expression:
        failures = [condition_contradiction(x) for x in expression['any']]
        return 'Toutes les alternatives sont contradictoires' if all(failures) else ''
    if 'not' in expression:
        # Literal negation of a contradiction is satisfiable as a Boolean
        # expression, but may still require a real Campaign state.
        return ''
    if 'all' not in expression:
        return ''

    atoms = _conjuncts(expression)
    for atom in atoms:
        reason = condition_contradiction(atom) if 'any' in atom else ''
        if reason:
            return reason
    positives, negatives = set(), set()
    flags = {}
    for atom in atoms:
        if 'not' in atom:
            negatives.add(_key(atom['not']))
            continue
        positives.add(_key(atom))
        if 'flag' not in atom:
            continue
        record = flags.setdefault(atom['flag'], {
            'eq': [], 'gte': [], 'lte': []})
        for operator in ('eq', 'gte', 'lte'):
            if operator in atom:
                record[operator].append(atom[operator])
    if positives & negatives:
        return 'Une même condition est exigée et niée'

    for name, record in flags.items():
        eqs = record['eq']
        if eqs and any(type(eqs[0]) is not type(value) or
                       eqs[0] != value for value in eqs[1:]):
            return 'Valeurs incompatibles du drapeau '+name
        low = max(record['gte']) if record['gte'] else None
        high = min(record['lte']) if record['lte'] else None
        if low is not None and high is not None and low > high:
            return 'Bornes incompatibles du drapeau '+name
        if eqs and (low is not None or high is not None):
            value = eqs[0]
            if type(value) is not int or (
                    low is not None and value < low) or (
                    high is not None and value > high):
                return 'Égalité et bornes incompatibles du drapeau '+name
    return ''


def audit_branch_coverage(story, data, mission_id):
    """Authoring-only coverage with precise, navigable evidence.

    Terminal choices can be intentional; informational entries are not
    hard errors. A syntactic contradiction is a proven *choice-local*
    impossibility, distinct from an orphan or unknown runtime state.
    """
    diag = navigation_diagnostics(story)
    mission = next((m for m in data['missions'] if m['id'] == mission_id), None)
    require(mission is not None, 'Unknown branch QA mission')
    status = {r['scene_id']: r['status'] for r in diag['records']}
    scenes = {row['id']: row for row in story.get('scenes', [])}
    issues = []
    choices = []
    for sid in sorted(scenes):
        scene = scenes[sid]
        state = status[sid]
        if state in ('unreferenced', 'disconnected'):
            issues.append({
                'code': 'disconnected_scene', 'severity': 'warning',
                'scene_id': sid, 'choice_id': '',
                'detail': 'Scène non accessible depuis une entrée déclarée',
                'status': state})
        elif state == 'conditional_only':
            issues.append({
                'code': 'conditional_path', 'severity': 'info',
                'scene_id': sid, 'choice_id': '',
                'detail': 'Chemin dépendant de conditions non résolues',
                'status': state})
        for choice in scene['choices']:
            cid = choice['id']
            key = sid+'/'+cid
            target = choice.get('next_scene', '')
            condition = choice.get('when')
            contradiction = condition_contradiction(condition)
            row = {
                'id': key, 'scene_id': sid, 'choice_id': cid,
                'title': choice['label'], 'conditioned': condition is not None,
                'target': target, 'status': state,
                'structurally_reachable': state not in (
                    'unreferenced', 'disconnected'),
                'contradiction': contradiction,
                'terminal': not bool(target),
            }
            choices.append(row)
            if contradiction:
                issues.append({
                    'code': 'contradictory_condition', 'severity': 'error',
                    'scene_id': sid, 'choice_id': cid, 'detail': contradiction,
                    'status': state})
            if not target:
                issues.append({
                    'code': 'terminal_choice', 'severity': 'info',
                    'scene_id': sid, 'choice_id': cid,
                    'detail': 'Fin du dialogue (vérifier si voulue)',
                    'status': state})
    guarded = []
    for event in sorted(mission.get('triggers', []), key=lambda e: e['id']):
        guard = event.get('after_choice')
        if not guard:
            continue
        source = guard['scene']+'/'+guard['choice']
        guarded.append({'event_id': event['id'], 'choice_id': source})
        if source not in {c['id'] for c in choices}:
            issues.append({
                'code': 'orphan_tactical_guard', 'severity': 'error',
                'scene_id': guard['scene'], 'choice_id': guard['choice'],
                'detail': 'Événement '+event['id']+' : choix non défini',
                'status': 'unknown'})
    return {
        'kind': 'structural', 'mission_id': mission_id,
        'entry_scenes': diag['entries'],
        'scene_count': len(scenes), 'choice_count': len(choices),
        'reachable_scene_count': diag['reachable_count'],
        'structurally_reachable_choices': sum(
            c['structurally_reachable'] for c in choices),
        'conditional_choices': sum(c['conditioned'] for c in choices),
        'terminal_choices': sum(c['terminal'] for c in choices),
        'guarded_events': guarded,
        'choices': choices, 'issues': issues,
        'evidence': 'Graph projection only; NOT gameplay execution',
    }


def probe_story_choices(data, project, *, max_states=220,
                        max_depth=24, max_paths=30):
    """Enumerate available StoryBook choices from fresh synthetic states.

    Each authored entry is independently seeded as pending. The production
    StoryBook applies conditions and effects via choose(), so scripted branch
    paths are real StoryBook transitions; tactical triggers and mission
    completion are not replayed. The limits are global and deterministic.
    """
    require(isinstance(project, GameProject), 'Open a GameProject')
    require(type(max_states) is int and 1 <= max_states <= 4000,
            'Invalid branch simulation state budget')
    require(type(max_depth) is int and 1 <= max_depth <= 64,
            'Invalid branch simulation depth')
    require(type(max_paths) is int and 1 <= max_paths <= 200,
            'Invalid branch simulation path budget')
    rules = authored_rules_for_document(data)
    content = Content.from_dict(data, rules=rules)
    project.validate(content)
    story = project.story
    static = {s['id']+'/'+c['id'] for s in story.get('scenes', [])
              for c in s['choices']}
    roots = entry_scene_ids(story)
    if not roots:
        return {'kind': 'storybook_probe', 'roots': [],
                'states': 0, 'executed_choices': [],
                'uncovered_choices': sorted(static),
                'finished': [], 'errors': [], 'truncated': False,
                'replay_verified': False,
                'evidence': 'No authored entry scenes; no execution performed'}
    book = StoryBook(story, content, project.campaigns)
    starter = project.campaigns[0]['start_mission']
    pending = deque()
    for sid in roots:
        progress = Campaign(unlocked=[starter],
                            story_started=True, story_digest=book.digest,
                            story_pending=sid)
        pending.append((sid, progress, (), 0))
    executed = set()
    finished = []
    errors = []
    states = 0
    while pending and states < max_states:
        root, progress, steps, depth = pending.popleft()
        states += 1
        if not progress.story_pending:
            if len(finished) < max_paths:
                finished.append({'root': root, 'choices': list(steps),
                                 'story_flags': deepcopy(progress.story_flags),
                                 'gold': progress.gold})
            continue
        if depth >= max_depth:
            continue
        options = book.choices(progress)
        for choice in options:
            sid = progress.story_pending
            key = sid+'/'+choice['id']
            try:
                next_state = book.choose(progress, choice['id'])
            except (RuleError, ValueError, KeyError) as exc:
                if len(errors) < max_paths:
                    errors.append({'choice_id': key, 'error': str(exc)})
                continue
            executed.add(key)
            pending.append((root, next_state, steps+(key,), depth+1))
    return {
        'kind': 'storybook_probe', 'roots': roots, 'states': states,
        'executed_choices': sorted(executed),
        'uncovered_choices': sorted(static-executed),
        'finished': finished, 'errors': errors,
        'truncated': bool(pending),
        'replay_verified': False,
        'evidence': ('Production StoryBook.choices/choose applied to independent '
                     'synthetic Campaign entry states; no tactical GameSession replay'),
    }


def probe_tactical_branches(data, project, mission_id, *, max_events=8):
    """Read-only Battle previews of narrative-event roots with hard budget."""
    require(type(max_events) is int and 1 <= max_events <= 20,
            'Invalid tactical branch probe budget')
    event_ids = {e['id'] for m in data['missions'] if m['id'] == mission_id
                 for e in m.get('triggers', [])}
    links = project.story.get('during_tactical_event', {})
    refs = sorted(event_id for reference in links
                  for mid, _, event_id in [reference.partition('/')]
                  if mid == mission_id and event_id in event_ids)
    reports = []
    for eid in refs[:max_events]:
        try:
            probe = preview_choice_routes(
                data, project, mission_id, eid, scenario='satisfied')
            reports.append({
                'event_id': eid, 'source_fired': probe['source_fired'],
                'choice_ids': [r['choice_id'] for r in probe['routes']],
                'routes': [{'choice_id': r['choice_id'],
                            'event_ids': r['fired_ids'],
                            'error': r['error']}
                           for r in probe['routes']],
                'blocked_reason': probe.get('blocked_reason','')})
        except (RuleError, ValueError, KeyError) as exc:
            reports.append({
                'event_id': eid, 'source_fired': False, 'choice_ids': [],
                'routes': [], 'blocked_reason': str(exc)})
    return {
        'kind': 'isolated_battle_preview', 'mission_id': mission_id,
        'reports': reports, 'truncated': len(refs) > max_events,
        'replay_verified': False,
        'evidence': ('EventContext/Battle isolated source-and-choice preview; '
                     'not a GameSession recording or replay'),
    }


def format_branch_qa(report, *, max_rows=80):
    """Human-readable Studio output for any of the three report kinds."""
    lines = []
    if report['kind'] == 'structural':
        lines = [
            'BRANCH QA — COUVERTURE STRUCTURELLE',
            'Mission : '+report['mission_id'],
            'Scènes : %d (atteignables : %d)' %
            (report['scene_count'], report['reachable_scene_count']),
            'Choix : %d (structurellement atteignables : %d)' %
            (report['choice_count'], report['structurally_reachable_choices']),
            'Choix conditionnels : %d · Fins de dialogue : %d' %
            (report['conditional_choices'], report['terminal_choices']),
            'Événements gardés par un choix : %d' %
            len(report['guarded_events']),
        ]
        for issue in report['issues'][:max_rows]:
            lines.append(
                '%s [%s] %s/%s : %s' %
                (issue['severity'].upper(), issue['code'],
                 issue['scene_id'], issue['choice_id'], issue['detail']))
        if len(report['issues']) > max_rows:
            lines.append('… liste de diagnostics limitée à %d' % max_rows)
    elif report['kind'] == 'storybook_probe':
        lines = [
            'BRANCH QA — SONDES STORYBOOK (SYNTHÉTIQUES)',
            'Entrées : %d · États visités : %d' %
            (len(report['roots']), report['states']),
            'Choix exercés : %d · Non exercés : %d' %
            (len(report['executed_choices']), len(report['uncovered_choices'])),
            'Chemins terminés enregistrés : %d' % len(report['finished']),
        ]
        for key in report['uncovered_choices'][:max_rows]:
            lines.append('NON EXERCÉ : '+key)
        for row in report['errors'][:max_rows]:
            lines.append('ERREUR : '+row['choice_id']+' — '+row['error'])
    else:
        lines = ['BRANCH QA — APERÇUS BATTLE ISOLÉS',
                 'Mission : '+report['mission_id'],
                 'Sources testées : %d' % len(report['reports'])]
        for row in report['reports'][:max_rows]:
            lines.append(
                row['event_id']+' : '+
                ('source déclenchée' if row['source_fired']
                 else 'source non déclenchée') +
                ' · choix sondés %d' % len(row['choice_ids']))
            for item in row['routes']:
                lines.append('  '+item['choice_id']+' → '+
                             (', '.join(item['event_ids']) or 'aucun événement')+
                             (' · ERREUR '+item['error'] if item['error'] else ''))
            if row['blocked_reason']:
                lines.append('  BLOQUÉ : '+row['blocked_reason'])
    lines.append('Limite de budget atteinte : ' +
                 ('oui' if report.get('truncated') else 'non'))
    lines.append('Preuve : '+report['evidence'])
    return lines
