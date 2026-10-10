"""2.8 playable castle campaign, from roster selection to a verified epilogue.

Run: python -m examples.castle_vertical_slice --save saves/castle-2.8.json
Resume: python -m examples.castle_vertical_slice --load saves/castle-2.8.json
"""
import argparse
import json
import shlex
from pathlib import Path

from examples.siege_fronts import siege_session
from examples.tactical_rpg3_castle import advanced_castle_content
from sporebound.model import Content, RuleError
from sporebound.tactical_rpg3 import tactical_rpg_rules
from sporebound.vertical_slice import CastleVerticalSlice


def castle_content():
    """Production-strength siege fixtures plus selectable jobs and starter gear."""
    data = advanced_castle_content().to_dict()
    data["jobs"].update({
        "brave": {"bonuses": {}},
        "vanguard": {"bonuses": {"max_hp": 8, "attack": 2}},
        "scout": {"bonuses": {"speed": 2, "move": 1}},
        "siege_engineer": {"bonuses": {"defense": 2, "move": 1}},
    })
    data["equipment"].update({
        "tactical_blade": {"slot": "weapon", "price": 30,
                           "bonuses": {"attack": 2}},
        "sturdy_armor": {"slot": "armor", "price": 25,
                         "bonuses": {"defense": 3}},
        "swift_boots": {"slot": "accessory", "price": 15,
                        "bonuses": {"move": 1}},
    })
    return Content.from_dict(data, rules=tactical_rpg_rules())


def castle_blueprint():
    """Reuse the actual multi-front authored routes, links and diplomacy."""
    template = siege_session(seed=1, contested=True, campaign=True, paths=True)
    return {"missions": template.missions,
            "specs": template.initial_specs,
            "links": template.links,
            "logistics": template.initial_logistics,
            "campaign": template.initial_campaign}


def new_game(seed=7):
    return CastleVerticalSlice(castle_content(), castle_blueprint(),
                               seed=seed, rules=tactical_rpg_rules())


HELP = """
Preparation: squad captain [engineer] | job HERO CLASS | buy ITEM | equip HERO ITEM
Approach: approach ram|infiltration|tunnels|negotiation|direct
Campaign: switch FRONT | route direct|tunnels | doctrine FRONT hold|assault|delay
          advance | negotiate | partial | withdraw FRONT | concede
Battle:  deploy HERO X Y | begin | move X Y | attack X Y | skill ID X Y
         interact OBJECT | siege OBJECT | repair OBJECT | end | ai
Any time: status | save [PATH] | help | quit
Use a real objective at supplies before negotiating; win a genuine tactical
battle in the tunnels to unlock that route. Final throne victory is NEVER
granted by the strategic auto-resolver.
""".strip()


def apply(session, tokens):
    name = tokens[0].lower()
    a = tokens[1:]
    if name == "squad":
        session.select_squad(a)
    elif name == "job":
        session.set_job(a[0], a[1])
    elif name == "buy":
        session.buy(a[0])
    elif name == "equip":
        session.equip(a[0], a[1])
    elif name == "approach":
        session.start(a[0])
    elif name == "switch":
        session.switch(a[0])
    elif name == "route":
        session.select_route(a[0])
    elif name == "doctrine":
        session.doctrine(a[0], a[1])
    elif name == "advance":
        session.advance()
    elif name == "negotiate":
        session.negotiate()
    elif name == "partial":
        session.partial()
    elif name == "withdraw":
        session.withdraw(a[0])
    elif name == "concede":
        session.concede()
    elif name == "ai":
        from sporebound.ai import choose_command
        battle = session.fronts.active
        if battle.deploying or battle.result is not None or battle.active is None or battle.active.team != "enemy":
            raise RuleError("AI can only play the enemy activation")
        active_id = battle.active.id
        for _ in range(3):
            battle = session.fronts.active
            if battle.result is not None or battle.active is None or battle.active.id != active_id:
                break
            session.execute(choose_command(battle))
    elif name in {"deploy", "begin", "move", "attack", "skill", "interact", "siege", "repair", "end"}:
        if name == "deploy":
            cmd = {"kind": "deploy", "unit": a[0], "cell": [int(a[1]), int(a[2])]}
        elif name == "begin":
            cmd = {"kind": "start_battle"}
        elif name == "move":
            cmd = {"kind": "move", "cell": [int(a[0]), int(a[1])]}
        elif name == "attack":
            cmd = {"kind": "act", "skill": "attack", "cell": [int(a[0]), int(a[1])]}
        elif name == "skill":
            cmd = {"kind": "act", "skill": a[0], "cell": [int(a[1]), int(a[2])]}
        elif name == "interact":
            cmd = {"kind": "interact", "object": a[0]}
        elif name == "siege":
            cmd = {"kind": "siege_attack", "object": a[0]}
        elif name == "repair":
            cmd = {"kind": "repair_siege", "object": a[0]}
        else:
            cmd = {"kind": "end"}
        session.execute(cmd)
    else:
        raise RuleError("Unknown command: " + name)


def display(session):
    state = session.state()
    print(json.dumps(state, ensure_ascii=False, indent=2))
    if session.fronts is not None and session.ending is None:
        battle = session.fronts.active
        print("Mission:", battle.mission.name, "|", "Deployment" if battle.deploying
              else "Actor: " + str(battle.active_id))
        print("Units:", [(u.id, list(u.pos), u.hp) for u in battle.units if u.alive])
        print("Objects:", [(o["id"], o["kind"], o["pos"])
                           for o in battle.mission.objects])


def play(*, seed=7, save_path=Path("saves/castle-2.8.json"), load=None):
    content, blueprint, rules = castle_content(), castle_blueprint(), tactical_rpg_rules()
    session = (CastleVerticalSlice.load(load, content, blueprint, rules=rules)
               if load else CastleVerticalSlice(content, blueprint, seed=seed, rules=rules))
    print(HELP)
    display(session)
    while True:
        try:
            line = input("castle> ")
        except EOFError:
            break
        try:
            tokens = shlex.split(line)
            if not tokens:
                continue
            if tokens[0] == "quit":
                break
            if tokens[0] == "help":
                print(HELP)
                continue
            if tokens[0] == "status":
                display(session)
                continue
            if tokens[0] == "save":
                target = Path(tokens[1]) if len(tokens) > 1 else save_path
                session.save(target)
                print("Checkpoint:", target)
                continue
            apply(session, tokens)
            session.save(save_path)
            display(session)
            if session.ending is not None:
                print("Epilogue:", {"victory": "Victoire", "accord": "Accord",
                                    "defeat": "Défaite"}[session.ending])
        except (RuleError, ValueError, KeyError, IndexError, TypeError) as exc:
            print("Refused:", exc)
    session.save(save_path)
    print("Checkpoint:", save_path)
    return session


def main(argv=None):
    parser = argparse.ArgumentParser(description="2.8 castle vertical slice")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--save", type=Path, default=Path("saves/castle-2.8.json"))
    parser.add_argument("--load", type=Path)
    args = parser.parse_args(argv)
    play(seed=args.seed, save_path=args.save, load=args.load)


if __name__ == "__main__":
    main()
