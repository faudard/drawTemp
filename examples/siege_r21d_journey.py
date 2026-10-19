"""Headless, replayable R21.D castle-siege journey.

Run:
    python -m examples.siege_r21d_journey

This intentionally exercises the existing engine and strategic APIs. It
does not auto-win encounters, alter HP out of band or introduce fake results.
"""
from sporebound.fronts import MultiFrontSession
from sporebound.siege_journey_r21 import siege_journey_snapshot
from .siege_fronts import siege_session


def demonstrate(seed=23):
    session = siege_session(seed=seed, focused="supplies", contested=True)
    # A genuine authored deployment; our soldiers hold their initial cells.
    session.execute({"kind": "start_battle"})
    # Cut the enemy's future throne reinforcements from the supply front.
    session.execute({"kind": "interact", "object": "supply_cache"})
    session.execute({"kind": "end"})
    # One reserve goes to the gate via the authored reserve -> gate convoy.
    session.send_reserves("gate", [{
        "id": "r21d_reinforcement", "name": "Relief Guard",
        "team": "player", "pos": [2, 6]}])
    session.advance()  # The global clock, convoy ETA and offscreen attrition.
    session.switch("gate")
    # A real deployment command positions the crew next to the ram.
    session.execute({"kind": "deploy", "unit": "captain", "cell": [2, 3]})
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "interact", "object": "ram"})
    session.execute({"kind": "end"})
    return session


def main():
    session = demonstrate()
    current = siege_journey_snapshot(session)
    assert "throne" in current["blocked_reinforcements"]
    assert any(ev["kind"] == "ram_advanced" for ev in session.active.events)
    restored = MultiFrontSession.replay(session.recording())
    assert restored.digest() == session.digest()
    print("Focused front:", current["focused"])
    print("Strategic clock:", current["turn"])
    print("Siege steps recorded:", current["checkpoint_operations"])
    print("Siege ram:", next(obj["position"] for front in current["fronts"]
                             if front["id"] == "gate"
                             for obj in front["infrastructure"]
                             if obj["id"] == "ram"))
    print("Authenticated replay: OK")


if __name__ == "__main__":
    main()
