"""Playable multi-front strategy command center with optional contested routes.

    python -m examples.siege_command                  # inspect the siege
    python -m examples.siege_command --interactive    # command the siege
    python -m examples.siege_command --demo           # scripted deterministic tour
"""
import argparse

from sporebound.command_center import dashboard, run
from sporebound.fronts import MultiFrontSession
from .siege_fronts import siege_session


def demo():
    battle = siege_session(seed=4, contested=True)
    battle.execute({"kind": "start_battle"})
    battle.set_doctrine("walls", "hold")
    convoy = battle.send_reserves("walls", [
        {"id": "reinforcement", "name": "Reinforcement", "team": "player",
         "pos": [3, 6]}])
    battle.advance()  # trap on the reserve route: stalled awaiting a rescue
    assert battle.logistics.convoy(convoy).get("stranded")
    battle.rescue_convoy(convoy)
    for _ in range(3):
        battle.advance()
    recording = battle.recording()
    verified = MultiFrontSession.replay(recording)
    assert verified.digest() == battle.digest()
    return dashboard(battle, event_count=20)


def tactical_rescue_demo():
    """Run a complete protected-wagon battle and verify its strategic outcome."""
    session = siege_session(seed=4, contested=True)
    session.set_doctrine("walls", "hold")
    convoy_id = session.send_reserves("walls", [
        {"id": "rescued_guard", "name": "Rescued Guard",
         "team": "player", "pos": [3, 6]}])
    session.advance()
    session.start_rescue(convoy_id)
    # Deterministic scripted *Battle commands*, not direct unit mutation.
    for _ in range(80):
        if convoy_id not in session.rescue_battles:
            break
        battle = session.rescue_battles[convoy_id]
        if battle.active_id == "rescue_leader" and not battle.active.acted:
            target = next((unit for unit in battle.units
                           if unit.team == "enemy" and unit.alive), None)
            if target is not None:
                session.execute_rescue(convoy_id, {
                    "kind": "act", "skill": "attack", "cell": list(target.pos)})
                continue
        session.execute_rescue(convoy_id, {"kind": "end"})
    if session.rescue_outcomes.get(convoy_id) != "victory":
        raise RuntimeError("The scripted wagon-rescue mission did not succeed")
    session.advance()
    verified = MultiFrontSession.replay(session.recording())
    assert verified.digest() == session.digest()
    return dashboard(session, event_count=40)


def branching_convoy_demo():
    """Evacuate convoy crew, then hunt the stolen supplies in another battle."""
    session = siege_session(seed=4, contested=True, decisions=True)
    session.set_doctrine("walls", "hold")
    convoy = session.send_reserves("walls", [
        {"id": "evacuated_scout", "name": "Evacuated Scout",
         "team": "player", "pos": [3, 6]}])
    session.advance()
    session.evacuate_convoy(convoy)
    pursuit = session.start_pursuit(convoy)
    assert pursuit.mission.id == "castle_convoy_pursuit"
    for _ in range(100):
        if not session.pursuit_battles:
            break
        battle = session.pursuit_battles[convoy]
        if battle.active_id == "pursuit_ranger" and not battle.active.acted:
            enemy = next((u for u in battle.units
                          if u.team == "enemy" and u.alive), None)
            if enemy is not None:
                session.execute_pursuit(convoy, {
                    "kind": "act", "skill": "attack", "cell": list(enemy.pos)})
                continue
        session.execute_pursuit(convoy, {"kind": "end"})
    assert session.pursuit_outcomes[convoy] == "victory"
    for _ in range(3):
        session.advance()
    assert session.pending_reinforcements["walls"][0]["actors"][0]["id"] == "evacuated_scout"
    assert MultiFrontSession.replay(session.recording()).digest() == session.digest()
    return dashboard(session, event_count=50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless castle command center")
    parser.add_argument("--gui", action="store_true",
                        help="Open the graphical Tk command centre")
    parser.add_argument("--interactive", action="store_true",
                        help="Use a small command-driven dashboard")
    parser.add_argument("--choices-demo", action="store_true",
                        help="Evacuate the crew and play a raider-pursuit mission")
    parser.add_argument("--rescue-demo", action="store_true",
                        help="Play the tactical wagon rescue through real Battle commands")
    parser.add_argument("--demo", action="store_true",
                        help="Run an ambush and convoy rescue with verified replay")
    options = parser.parse_args()
    if options.gui:
        from sporebound.strategic_ui import launch
        launch(siege_session(contested=True, decisions=True))
    elif options.choices_demo:
        print(branching_convoy_demo())
        print("Verified branching convoy replay: OK")
    elif options.rescue_demo:
        print(tactical_rescue_demo())
        print("Verified tactical convoy-rescue replay: OK")
    elif options.demo:
        print(demo())
        print("Verified command replay: OK")
    elif options.interactive:
        print("Enter 'help' for a list of commands.")
        run(siege_session(contested=True, decisions=True))
    else:
        print(dashboard(siege_session(contested=True, decisions=True)))
        print("For orders: python -m examples.siege_command --interactive")
