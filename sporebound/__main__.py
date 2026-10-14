"""DrawTemp tactical CLI (legacy sporebound import path retained)."""
import argparse
from dataclasses import asdict
import json
import statistics
from pathlib import Path

from .ai import play_activation, simulate
from .campaign import Campaign
from .engine import Battle
from .model import Content, RuleError
from .storage import load_battle, save_battle

# Legacy test fixture constant, intentionally preserved.
DEFAULT_CONTENT = Path(__file__).parent / 'content' / 'core.json'
DEFAULT_GAME_CONTENT = Path(__file__).parent / 'content' / 'jeanne.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description="DrawTemp — Jeanne d'Arc RPG and Game Studio")
    parser.add_argument('command', choices=['validate','simulate','replay','play','editor','player','jeanne-chapter1','campaign','roster','balance','battle-lab','battle-diagnostics','balance-matrix','tactical-choices','tactical-quality','full-activation','export'])
    parser.add_argument('--content', type=Path, default=DEFAULT_GAME_CONTENT)
    parser.add_argument('--project', type=Path, help='Game presentation manifest for player')
    parser.add_argument('--output', type=Path, help='Destination ZIP for export')
    parser.add_argument('--profile', type=Path, help='Writable player profile path')
    parser.add_argument('--mission', help='Mission ID (default: first mission of selected content)')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--runs', type=int, default=20, help='Number of deterministic balance seeds')
    parser.add_argument('--baseline', type=Path, help='Prior Battle Lab or Matrix JSON for paired gate')
    parser.add_argument('--matrix-cases', type=Path, help='JSON scenario file for balance-matrix')
    parser.add_argument('--report', type=Path, help='Write versioned Battle Lab JSON')
    parser.add_argument('--max-victory-drop', type=float, default=0.25)
    parser.add_argument('--max-p95-growth', type=float, default=0.30)
    parser.add_argument('--max-new-limits', type=int, default=0)
    parser.add_argument('--activation-min-distinct', type=int, default=1,
                        help='Minimum R6.16 player states with distinct full-turn outcomes')
    parser.add_argument('--activation-min-pairs', type=int, default=0,
                        help='Minimum R6.16 states with non-dominated full-turn options')
    parser.add_argument('--quality-min-differentiated', type=int, default=1)
    parser.add_argument('--quality-min-tradeoffs', type=int, default=0)
    parser.add_argument('--human-playtest', type=Path,
                        help='Optional opt-in human playtest report for R6.15')
    parser.add_argument('--human-signoff', type=Path,
                        help='Explicit five-checkbox review JSON for R6.15')
    parser.add_argument('--quality-annotations', type=Path,
                        help='Optional R6.11 categorical playtest annotation JSON')
    parser.add_argument('--quality-variant', default='authored')
    parser.add_argument('--max-choice-drop', type=float, default=0.25,
                        help='Maximum paired decrease of multi-category opportunity rate')
    parser.add_argument('--choice-min-multi', type=int, default=1,
                        help='Minimum sampled multi-category player decisions')
    parser.add_argument('--choice-required-pair', action='append', default=[],
                        help='Pair required in tactical-choices (e.g. positioning+damage)')
    parser.add_argument('--save', type=Path)
    parser.add_argument('--load', type=Path)
    parser.add_argument('--campaign-file', type=Path, default=Path('saves/campaign.json'))
    parser.add_argument('--campaign', action='store_true', help='Persist progress after manual play')
    parser.add_argument('--hero', help='Hero id for roster operations')
    parser.add_argument('--job', help='Select an unlocked job')
    parser.add_argument('--buy', help='Buy an equipment id with campaign gold')
    parser.add_argument('--equip', help='Equip an owned item')
    parser.add_argument('--unequip', choices=['weapon','armor','accessory'])
    args = parser.parse_args(argv)
    try:
        if args.command == 'jeanne-chapter1':
            from .player_app import launch as launch_player
            launch_player(DEFAULT_GAME_CONTENT,
                          DEFAULT_GAME_CONTENT.with_suffix(".game.json"),
                          args.profile, chapter_one=True)
            return 0
        if args.command == 'player':
            from .player_app import launch as launch_player
            launch_player(args.content, args.project, args.profile)
            return 0
        if args.command == 'editor':
            from .editor import launch
            launch(args.content)
            return 0
        if args.command == 'replay':
            if not args.load:
                parser.error('replay requires --load')
            battle = load_battle(args.load)
            print(json.dumps({'verified':True,'digest':battle.digest(),'result':battle.result}))
            return 0
        content = Content.load(args.content)
        if args.mission is None:
            args.mission = next(iter(content.missions))
        if args.command == 'export':
            if args.project is None or args.output is None:
                parser.error('export requires --project and --output')
            from .game_project import GameProject
            from .game_export4 import export_game
            project = GameProject.load(args.project, content)
            path = export_game(content, project, args.project.parent, args.output)
            print(json.dumps({'exported': str(path)}, ensure_ascii=False))
            return 0
        if args.command == 'validate':
            if args.project:
                from .game_project import GameProject
                project = GameProject.load(args.project, content)
                issues = project.asset_registry().diagnostics(args.project.parent)
                if issues:
                    print(json.dumps({'valid': False, 'assets': issues}, ensure_ascii=False))
                    return 1
            print(f'Valid: {len(content.missions)} missions, {len(content.skills)} skills, {len(content.jobs)} jobs')
            return 0
        if args.command == 'battle-diagnostics':
            from .battle_diagnostics import trace_seed, trace_report
            from .tactical_rpg3 import authored_rules_for_document
            rules = authored_rules_for_document(content.to_dict())
            trace = trace_seed(content, args.mission, seed=args.seed,
                               max_commands=args.limit, rules=rules)
            if args.report:
                trace_report(args.report, trace)
            print(json.dumps({
                'mission': trace['mission'], 'seed': trace['seed'],
                'result': trace['result'], 'commands': trace['commands'],
                'ticks': trace['ticks'], 'digest': trace['digest'],
                'replay_verified': trace['replay_verified'],
                'diagnostics': trace['diagnostics'],
                'trace_report': str(args.report) if args.report else None
            }, ensure_ascii=False, sort_keys=True))
            return 0
        if args.command == 'balance-matrix':
            from .balance_matrix import run_matrix, compare_matrices, save_matrix
            from .tactical_rpg3 import authored_rules_for_document
            from .rules import default_rules
            if args.matrix_cases is None:
                parser.error('balance-matrix requires --matrix-cases file.json')
            if not 1 <= args.runs <= 64 or not 1 <= args.limit <= 10000:
                parser.error('balance-matrix requires 1..64 seeds and 1..10000 commands')
            if args.seed < 0 or args.seed + args.runs > 2**32:
                parser.error('Matrix seeds must fit unsigned 32-bit integers')
            with args.matrix_cases.open(encoding='utf-8') as stream:
                definition = json.load(stream)
            cases = definition.get('cases') if type(definition) is dict else definition
            if type(cases) not in (list, tuple):
                raise RuleError('Matrix definitions need a cases array')
            rulesets = {'authored': authored_rules_for_document(content.to_dict())}
            if any(row.get('ruleset') == 'default'
                   for row in cases if type(row) is dict):
                rulesets['default'] = default_rules()
            matrix = run_matrix(content, cases, seeds=list(range(args.seed,
                                args.seed + args.runs)), max_commands=args.limit,
                                rulesets=rulesets)
            if args.report:
                save_matrix(args.report, matrix)
            comparison = None
            if args.baseline:
                with args.baseline.open(encoding='utf-8') as stream:
                    baseline = json.load(stream)
                comparison = compare_matrices(
                    baseline, matrix, max_victory_drop=args.max_victory_drop,
                    max_p95_growth=args.max_p95_growth,
                    max_new_limits=args.max_new_limits)
            print(json.dumps({'matrix': matrix, 'comparison': comparison},
                             ensure_ascii=False, sort_keys=True))
            return 2 if comparison is not None and not comparison['passed'] else 0
        if args.command == 'full-activation':
            from .full_activation_r616 import (
                run_activation_lab, evaluate_activation_gate)
            from .tactical_rpg3 import authored_rules_for_document
            if args.baseline is not None:
                parser.error(
                    'full-activation does not implement paired baseline review; '
                    'use independently exported reports to inspect changes')
            report = run_activation_lab(
                content, args.mission, seed=args.seed,
                max_commands=args.limit,
                rules=authored_rules_for_document(content.to_dict()))
            gate = evaluate_activation_gate(
                report, min_distinct=args.activation_min_distinct,
                min_non_dominated=args.activation_min_pairs)
            report["gate"] = gate
            if args.report:
                args.report.write_text(
                    json.dumps(report, sort_keys=True, ensure_ascii=False,
                               indent=2) + "\n", encoding='utf-8')
            print(json.dumps({
                'mission': report['mission'], 'seed': report['seed'],
                'digest': report['digest'],
                'replay_verified': report['replay_verified'],
                'gate': gate,
                'human_certified': False,
                'report': str(args.report) if args.report else None,
            }, ensure_ascii=False, sort_keys=True))
            return 0 if gate['passed'] else 2
        if args.command == 'tactical-quality':
            from .tactical_quality_r6 import (
                run_quality_lab, evaluate_quality_gate, release_quality_review)
            from .tactical_rpg3 import authored_rules_for_document
            quality = run_quality_lab(
                content, args.mission, seed=args.seed, max_commands=args.limit,
                rules=authored_rules_for_document(content.to_dict()))
            gate = evaluate_quality_gate(
                quality, min_differentiated=args.quality_min_differentiated,
                min_tradeoffs=args.quality_min_tradeoffs)
            quality["automated_gate"] = gate
            human_review = None
            if args.human_playtest or args.human_signoff or args.quality_annotations:
                if not args.human_playtest:
                    parser.error('Human review requires --human-playtest')
                with args.human_playtest.open(encoding='utf-8') as stream:
                    human = json.load(stream)
                signoff = None
                if args.human_signoff:
                    with args.human_signoff.open(encoding='utf-8') as stream:
                        signoff = json.load(stream)
                annotations = []
                if args.quality_annotations:
                    with args.quality_annotations.open(encoding='utf-8') as stream:
                        bundle = json.load(stream)
                    if (type(bundle) is not dict or
                            bundle.get('kind') != 'r6_playtest_annotations' or
                            bundle.get('schema') != 1 or
                            bundle.get('session_count') != len(human['sessions']) or
                            bundle.get('content_sha256') !=
                            human.get('content_sha256')):
                        raise RuleError('Incompatible human annotation bundle')
                    annotations = bundle['annotations']
                human_review = release_quality_review(
                    quality, human, annotations=annotations,
                    variant=args.quality_variant, human_signoff=signoff,
                    min_tradeoffs=max(1, args.quality_min_tradeoffs))
                quality["human_review"] = human_review
            if args.report:
                args.report.write_text(
                    json.dumps(quality, sort_keys=True, ensure_ascii=False,
                               indent=2) + "\n", encoding='utf-8')
            print(json.dumps({
                'mission': quality['mission'], 'seed': quality['seed'],
                'digest': quality['digest'],
                'replay_verified': quality['replay_verified'],
                'automated_gate': gate, 'human_review': human_review,
                'release_status': ('not_certified_without_human_review'
                                   if human_review is None else human_review['status']),
                'report': str(args.report) if args.report else None,
            }, ensure_ascii=False, sort_keys=True))
            return 0 if gate['passed'] and (
                human_review is None or human_review['passed']) else 2
        if args.command == 'tactical-choices':
            from .tactical_choice_lab_r6 import (
                run_choice_lab, evaluate_choice_gate, compare_choice_reports)
            from .tactical_rpg3 import authored_rules_for_document
            report = run_choice_lab(
                content, args.mission, seed=args.seed, max_commands=args.limit,
                rules=authored_rules_for_document(content.to_dict()))
            gate = evaluate_choice_gate(
                report, min_multi=args.choice_min_multi,
                required_pairs=args.choice_required_pair)
            report["gate"] = gate
            comparison = None
            if args.baseline:
                with args.baseline.open(encoding='utf-8') as stream:
                    previous = json.load(stream)
                comparison = compare_choice_reports(
                    previous, report, max_multi_rate_drop=args.max_choice_drop)
            if args.report:
                args.report.write_text(
                    json.dumps(report, sort_keys=True, ensure_ascii=False,
                               indent=2) + "\n", encoding='utf-8')
            print(json.dumps({
                'mission': report['mission'], 'seed': report['seed'],
                'digest': report['digest'],
                'replay_verified': report['replay_verified'],
                'gate': gate, 'comparison': comparison,
                'report': str(args.report) if args.report else None,
            }, ensure_ascii=False, sort_keys=True))
            return 0 if gate['passed'] and (
                comparison is None or comparison['passed']) else 2
        if args.command == 'battle-lab':
            from .battle_lab import compare_reports, run_lab, save_report
            from .tactical_rpg3 import authored_rules_for_document
            if not 1 <= args.runs <= 1000 or not 1 <= args.limit <= 100000:
                parser.error('battle-lab requires 1..1000 runs and 1..100000 commands')
            if args.seed < 0 or args.seed + args.runs > 2**32:
                parser.error('Battle Lab seeds must fit unsigned 32-bit integers')
            rules = authored_rules_for_document(content.to_dict())
            report = run_lab(content, args.mission,
                             seeds=list(range(args.seed, args.seed + args.runs)),
                             max_commands=args.limit, rules=rules)
            if args.report:
                save_report(args.report, report)
            comparison = None
            if args.baseline:
                with args.baseline.open(encoding='utf-8') as stream:
                    old_report = json.load(stream)
                comparison = compare_reports(
                    old_report, report,
                    max_victory_drop=args.max_victory_drop,
                    max_p95_growth=args.max_p95_growth,
                    max_new_limits=args.max_new_limits)
            print(json.dumps({'report': report, 'comparison': comparison},
                             ensure_ascii=False, sort_keys=True))
            return 2 if comparison is not None and not comparison['passed'] else 0
        if args.command == 'balance':
            if not 1 <= args.runs <= 1000 or args.limit < 1:
                parser.error('balance requires 1..1000 runs and a positive command limit')
            results = [simulate(Battle(content,args.mission,args.seed+i),args.limit) for i in range(args.runs)]
            print(json.dumps({'mission':args.mission,'runs':args.runs,'first_seed':args.seed,
                              'outcomes':{r:sum(v['result']==r for v in results) for r in ['victory','defeat','draw','limit']},
                              'median_ticks':statistics.median(v['ticks'] for v in results),
                              'median_commands':statistics.median(v['commands'] for v in results)}))
            return 0
        campaign = None
        if args.command == 'roster':
            campaign = Campaign.load(args.campaign_file) if args.campaign_file.exists() else Campaign([next(iter(content.missions))])
            hero_ids = {u.id for m in content.missions.values() for u in m.units if u.team == 'player'}
            if any((args.job,args.equip,args.unequip)) and args.hero not in hero_ids:
                parser.error('roster changes require --hero with a known player id')
            if args.buy: campaign.buy(content,args.buy)
            if args.job: campaign.set_job(content,args.hero,args.job)
            if args.unequip: campaign.unequip(args.hero,args.unequip)
            if args.equip: campaign.equip(content,args.hero,args.equip)
            campaign.save(args.campaign_file)
            print(json.dumps(asdict(campaign),ensure_ascii=False,indent=2))
            return 0
        if args.command == 'campaign' or args.command == 'play' and args.campaign:
            campaign = Campaign.load(args.campaign_file) if args.campaign_file.exists() else Campaign([next(iter(content.missions))])
            battle = load_battle(args.load) if args.load else campaign.prepare(content, args.mission, args.seed)
        else:
            battle = load_battle(args.load) if args.load else Battle(content,args.mission,args.seed)
        if args.command in {'simulate','campaign'}:
            print(json.dumps(simulate(battle,max_commands=args.limit)))
        else:
            print('Commands: deploy UNIT x y [N/S/E/W] | start | move x y | attack x y | skill ID x y | item ID x y | interact ID | siege-attack ID | repair-siege ID | end [N/S/E/W] | ai | save FILE | quit')
            while not battle.result:
                u = battle.active
                if battle.deploying:
                    print('Deployment: '+json.dumps(battle.mission.deployment))
                    print([(u.id, u.pos) for u in battle.units if u.team == 'player'])
                else:
                    print(f't={battle.tick} {u.id}({u.team}) at {u.pos}: HP={u.hp}, MP={u.mp}, CT={u.ct}')
                try:
                    words = input('> ').split()
                    if not words: continue
                    kind = words[0]
                    if kind == 'quit': break
                    if kind == 'save': save_battle(words[1],battle); continue
                    if kind == 'ai': play_activation(battle); continue
                    if kind == 'start': command = dict(kind='start_battle')
                    elif kind == 'deploy':
                        command = dict(kind='deploy', unit=words[1], cell=list(map(int,words[2:4])))
                        if len(words)>4: command['facing'] = {'N':[0,-1],'S':[0,1],'E':[1,0],'W':[-1,0]}[words[4]]
                    elif kind == 'move': command = dict(kind='move',cell=list(map(int,words[1:3])))
                    elif kind == 'attack': command = dict(kind='act',skill='attack',cell=list(map(int,words[1:3])))
                    elif kind == 'skill': command = dict(kind='act',skill=words[1],cell=list(map(int,words[2:4])))
                    elif kind == 'item': command = dict(kind='item',item=words[1],cell=list(map(int,words[2:4])))
                    elif kind == 'interact': command = dict(kind='interact',object=words[1])
                    elif kind == 'siege-attack': command = dict(kind='siege_attack',object=words[1])
                    elif kind == 'repair-siege': command = dict(kind='repair_siege',object=words[1])
                    elif kind == 'end': command = dict(kind='end',facing={'N':[0,-1],'S':[0,1],'E':[1,0],'W':[-1,0]}[words[1] if len(words)>1 else 'S'])
                    else: raise RuleError('Unknown command')
                    battle.execute(command)
                except (ValueError,KeyError,IndexError) as exc:
                    print(f'Rejected: {exc}')
                except EOFError:
                    break
            print(battle.result or 'paused')
        if campaign:
            campaign.finish(battle)
            campaign.save(args.campaign_file)
        if args.save:
            save_battle(args.save,battle)
        return 0 if battle.result != 'draw' and (battle.result or args.command=='play') else 2
    except (RuleError,OSError,ValueError,KeyError,TypeError) as exc:
        parser.exit(1,f'Error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())

