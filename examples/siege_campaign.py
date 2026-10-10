"""Castle siege campaign: choose the breach, then resolve the courtyard."""
from sporebound.scenarios import ScenarioDirector

SIEGE_CAMPAIGN = {
    "start": "approach",
    "phases": [
        {"id": "approach", "mission": "castle_troll",
         "exits": {"ram": "gate", "artillery": "bombardment", "infiltrate": "ramparts"},
         "on_exit": {"ram": {"breach": "ram"}, "artillery": {"breach": "catapult"},
                     "infiltrate": {"breach": "infiltration"}}},
        {"id": "gate", "mission": "castle_ram",
         "exits": {"continue": "courtyard"}},
        {"id": "bombardment", "mission": "castle_artillery",
         "exits": {"continue": "courtyard"}},
        {"id": "relief", "mission": "castle_relief",
         "exits": {"continue": "courtyard"}},
        {"id": "ramparts", "mission": "castle_ramparts",
         "exits": {"continue": "courtyard"}},
        {"id": "courtyard", "mission": "castle_courtyard",
         "exits": {"continue": "throne"},
         "entry_effects": [
             {"flag": "breach", "equals": "infiltration",
              "objects": {"stone_drop": {"disabled": True}}},
             {"flag": "breach", "equals": "catapult",
              "statuses": {"courtyard_guard": {"slow": 20}}},
         ]},
        {"id": "throne", "mission": "castle_throne",
         "exits": {"finish": None}},
    ],
}

# No successful branch can be taken after losing an encounter.
for phase in SIEGE_CAMPAIGN['phases']:
    phase['required_result'] = 'victory'



def play(load=None, autosave=None):
    """Small terminal campaign runner using the same transactional commands."""
    from examples.siege_scenarios import siege_content
    from sporebound.ai import play_activation
    from sporebound.model import RuleError
    from sporebound.scenarios import ScenarioSession
    from sporebound.storage import load_scenario, save_scenario
    session = load_scenario(load) if load else ScenarioSession(siege_content(), ScenarioDirector.from_dict(SIEGE_CAMPAIGN))
    def checkpoint():
        if autosave:
            save_scenario(autosave, session)
    checkpoint()
    print('Commands: deploy UNIT x y | start | move x y | attack x y | interact ID | item ID x y | end | ai | save FILE | quit')
    while not session.director.completed:
        battle = session.battle
        print(f'\n{battle.mission.name} | elapsed ticks: {session.elapsed_ticks + battle.tick}')
        print('Assault route:', session.director.flags.get('breach', 'undecided'))
        print('Supplies:', battle.inventory['player'])
        while not battle.result:
            if battle.active and battle.active.team != 'player':
                play_activation(battle)
                checkpoint()
                continue
            print('Deployment' if battle.deploying else f'{battle.active.id} at {battle.active.pos}')
            print('Units:', [(u.id, u.pos, u.hp) for u in battle.units if u.alive])
            print('Objects:', [(o['id'], o['pos']) for o in battle.mission.objects])
            try:
                words = input('> ').split()
                if not words: continue
                kind = words[0]
                if kind == 'quit': checkpoint(); return
                if kind == 'save': save_scenario(words[1], session); continue
                if kind == 'ai': play_activation(battle); checkpoint(); continue
                if kind == 'start': cmd = {'kind':'start_battle'}
                elif kind == 'deploy': cmd = dict(kind='deploy',unit=words[1],cell=list(map(int,words[2:4])))
                elif kind == 'move': cmd = dict(kind='move',cell=list(map(int,words[1:3])))
                elif kind == 'attack': cmd = dict(kind='act',skill='attack',cell=list(map(int,words[1:3])))
                elif kind == 'item': cmd = dict(kind='item',item=words[1],cell=list(map(int,words[2:4])))
                elif kind == 'interact': cmd = dict(kind='interact',object=words[1])
                elif kind == 'end': cmd = dict(kind='end')
                else: raise RuleError('Unknown command')
                battle.execute(cmd)
                checkpoint()
            except (RuleError, ValueError, IndexError) as exc:
                print('Rejected:', exc)
            except EOFError:
                return
        if battle.result != 'victory':
            print('The assault has failed.'); return
        choices = session.director.available_choices()
        choice = choices[0]
        while len(choices) > 1:
            try:
                choice = input('Choose '+', '.join(choices)+': ').strip()
            except EOFError:
                return
            if choice in choices: break
        session.complete(choice)
        checkpoint()
    print('The throne room is secured!')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Play the complete branching castle siege')
    parser.add_argument('--play', action='store_true')
    parser.add_argument('--load', help='Resume a verified scenario save')
    parser.add_argument('--save', default='saves/siege-campaign.json', help='Automatic checkpoint file')
    args = parser.parse_args()
    if args.play or args.load:
        play(load=args.load, autosave=args.save)
    else:
        parser.print_help()
