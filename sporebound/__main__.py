"""python -m sporebound: validate, simulate, replay, play or edit."""
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

DEFAULT_CONTENT = Path(__file__).parent / 'content' / 'core.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Sporebound standalone gameplay workbench')
    parser.add_argument('command', choices=['validate','simulate','replay','play','editor','campaign','roster','balance'])
    parser.add_argument('--content', type=Path, default=DEFAULT_CONTENT)
    parser.add_argument('--mission', default='garden')
    parser.add_argument('--seed', type=int, default=1)
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--runs', type=int, default=20, help='Number of deterministic balance seeds')
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
        if args.command == 'validate':
            print(f'Valid: {len(content.missions)} missions, {len(content.skills)} skills, {len(content.jobs)} jobs')
            return 0
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
            print('Commands: deploy UNIT x y [N/S/E/W] | start | move x y | attack x y | skill ID x y | item ID x y | interact ID | end [N/S/E/W] | ai | save FILE | quit')
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
