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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Headless castle command center")
    parser.add_argument("--gui", action="store_true",
                        help="Open the graphical Tk command centre")
    parser.add_argument("--interactive", action="store_true",
                        help="Use a small command-driven dashboard")
    parser.add_argument("--demo", action="store_true",
                        help="Run an ambush and convoy rescue with verified replay")
    options = parser.parse_args()
    if options.gui:
        from sporebound.strategic_ui import launch
        launch(siege_session(contested=True))
    elif options.demo:
        print(demo())
        print("Verified command replay: OK")
    elif options.interactive:
        print("Enter 'help' for a list of commands.")
        run(siege_session(contested=True))
    else:
        print(dashboard(siege_session(contested=True)))
        print("For orders: python -m examples.siege_command --interactive")
