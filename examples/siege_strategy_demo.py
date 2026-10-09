"""Multi-front siege demonstration: diplomacy -> partial capture -> throne.

    python -m examples.siege_strategy_demo

This deliberately authors a short map variant for a reproducible *real*
Battle-command sequence. The existing sequential campaign runner at
examples.siege_campaign remains untouched.
"""
from sporebound.fronts import MultiFrontSession
from sporebound.model import Content
from .siege_fronts import SIEGE_CAMPAIGN, SIEGE_LINKS, siege_session
from .siege_scenarios import siege_content


def compact_variant():
    data = siege_content().to_dict()
    courtyard = next(m for m in data["missions"] if m["id"] == "castle_courtyard")
    next(o for o in courtyard["objects"]
         if o["id"] == "stone_drop")["pos"] = [2, 3]
    throne = next(m for m in data["missions"] if m["id"] == "castle_throne")
    throne["units"] = [u for u in throne["units"]
                       if u["id"] in {"captain", "engineer", "castellan"}]
    boss = next(u for u in throne["units"] if u["id"] == "castellan")
    boss.update(pos=[2, 3], hp=1, max_hp=1, speed=5)
    return Content.from_dict(data)


def demo():
    template = siege_session(contested=True, campaign=True)
    session = MultiFrontSession(
        compact_variant(), template.missions, "supplies",
        seed=3, specs=template.initial_specs,
        links=SIEGE_LINKS, logistics=template.initial_logistics,
        campaign=SIEGE_CAMPAIGN)
    session.switch("gate")
    session.execute({"kind": "start_battle"})
    session.negotiate_front("gate")  # 2 provisions for a negotiated breach
    session.switch("courtyard")
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "interact", "object": "stone_drop"})
    session.execute({"kind": "end"})
    session.partial_front("courtyard")
    assert session.state()["campaign"]["unlocked"]
    session.switch("throne")
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "act", "skill": "attack", "cell": [2, 3]})
    assert session.state()["campaign"]["status"] == "victory"
    assert MultiFrontSession.replay(session.recording()).digest() == session.digest()
    return session


if __name__ == "__main__":
    session = demo()
    print("Campaign result:", session.state()["campaign"]["status"])
    print("Gate:", session.timeline.fronts["gate"]["status"])
    print("Courtyard:", session.timeline.fronts["courtyard"]["status"])
    print("Throne:", session.timeline.fronts["throne"]["status"])
    print("Supplies remaining:", session.logistics.supplies["player"])
    print("Replay v5 verified.")
