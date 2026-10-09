"""Three playable, journal-verified approaches to the same throne.

    python -m examples.siege_routes_demo

Only the demonstration's enemy HP and courtyard object placement are simplified.
All victories are achieved by genuine Battle commands.
"""
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content
from .siege_fronts import SIEGE_CAMPAIGN_PATHS, SIEGE_LINKS, siege_session
from .siege_scenarios import siege_content


def compact_content():
    raw = siege_content().to_dict()
    for mission in raw["missions"]:
        if mission["id"] in {"castle_tunnels", "castle_gate_recovery"}:
            for actor in mission["units"]:
                if actor["team"] == "enemy":
                    actor.update(hp=1, max_hp=1)
        if mission["id"] == "castle_courtyard":
            next(obj for obj in mission["objects"]
                 if obj["id"] == "stone_drop")["pos"] = [2, 3]
        if mission["id"] == "castle_throne":
            mission["units"] = [actor for actor in mission["units"]
                                if actor["id"] in {"captain", "engineer", "castellan"}]
            boss = next(actor for actor in mission["units"]
                        if actor["id"] == "castellan")
            boss.update(hp=1, max_hp=1, pos=[2, 3], speed=5)
    return Content.from_dict(raw)


def fresh():
    example = siege_session(contested=True, campaign=True, paths=True, seed=3)
    return MultiFrontSession(
        compact_content(), example.missions, "supplies", seed=3,
        specs=example.initial_specs, links=SIEGE_LINKS,
        logistics=example.initial_logistics, campaign=SIEGE_CAMPAIGN_PATHS)


def play_side(session, front, shooter, *, recovery=False):
    if recovery:
        session.start_recovery(front)
    else:
        session.switch(front)
        session.execute({"kind": "start_battle"})
    for _ in range(80):
        if recovery:
            if front not in session.recovery_battles:
                break
            battle = session.recovery_battles[front]
        else:
            battle = session.active
            if battle.result is not None:
                break
        if battle.active_id == shooter and not battle.active.acted:
            enemy = next((unit for unit in battle.units
                          if unit.team == "enemy" and unit.alive), None)
            if enemy is not None:
                action = {"kind": "act", "skill": "attack",
                          "cell": list(enemy.pos)}
                if recovery:
                    session.execute_recovery(front, action)
                else:
                    session.execute(action)
                continue
        if recovery:
            session.execute_recovery(front, {"kind": "end"})
        else:
            session.execute({"kind": "end"})
    result = session.recovery_outcomes.get(front) if recovery else session.active.result
    assert result == "victory", f"{front}: tactical outcome = {result}"


def defeat_castellan(session):
    session.switch("throne")
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "act", "skill": "attack", "cell": [2, 3]})
    assert session.state()["campaign"]["status"] == "victory"


def verify(session):
    assert MultiFrontSession.replay(session.recording()).digest() == session.digest()
    return {"route": session.route_selected,
            "status": session.state()["campaign"]["status"],
            "turns": session.timeline.turn,
            "supplies": session.logistics.supplies["player"],
            "throne_strength": session.timeline.fronts["throne"]["strength"]}


def demo():
    direct = fresh()
    direct.select_route("direct")
    defeat_castellan(direct)

    tunnels = fresh()
    tunnels.select_route("tunnels")
    play_side(tunnels, "tunnels", "tunnel_sapper")
    defeat_castellan(tunnels)

    restored = fresh()
    restored.switch("gate")
    restored.execute({"kind": "start_battle"})
    restored.withdraw_front("gate")
    play_side(restored, "gate", "relief_captain", recovery=True)
    restored.switch("courtyard")
    restored.execute({"kind": "start_battle"})
    restored.execute({"kind": "interact", "object": "stone_drop"})
    restored.execute({"kind": "end"})
    restored.partial_front("courtyard")
    defeat_castellan(restored)

    return {"direct": verify(direct), "tunnels": verify(tunnels),
            "recaptured_gate": verify(restored)}


if __name__ == "__main__":
    for name, result in demo().items():
        print(name, result)
    print("Three verifiable siege endings: OK")
