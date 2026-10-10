"""Deterministic patrol behavior used by the sewer infiltration mission."""
import unittest

from examples.siege_scenarios import siege_content
from sporebound.engine import Battle
from sporebound.model import Content, RuleError


ROUTE = [[6, 2], [6, 4], [7, 4], [7, 2]]


def tunnel_content(*, player_positions=((0, 0), (0, 6))):
    raw = siege_content().to_dict()
    mission = next(row for row in raw["missions"] if row["id"] == "castle_tunnels")
    mission["units"][0]["pos"] = list(player_positions[0])
    mission["units"][1]["pos"] = list(player_positions[1])
    sentry = next(row for row in mission["units"] if row["id"] == "sewer_sentry")
    sentry.update(behavior="tactical", patrol_route=ROUTE)
    warden = next(row for row in mission["units"] if row["id"] == "sewer_warden")
    warden["pos"] = [8, 6]
    return raw


class PatrolBehaviorTests(unittest.TestCase):
    def test_patrol_route_moves_to_next_waypoint_through_battle_command(self):
        content = Content.from_dict(tunnel_content())
        battle = Battle(content, "castle_tunnels", seed=3)
        battle.active_id = "sewer_sentry"
        command = battle.rules.behaviors.get("tactical").choose(battle)
        self.assertEqual(command, {"kind": "move", "cell": [6, 4]})
        battle.execute(command)
        self.assertEqual(battle.unit("sewer_sentry").pos, (6, 4))

    def test_patrol_switches_to_tactical_ai_when_player_is_seen(self):
        content = Content.from_dict(
            tunnel_content(player_positions=((5, 2), (0, 6))))
        battle = Battle(content, "castle_tunnels", seed=3)
        battle.active_id = "sewer_sentry"
        command = battle.rules.behaviors.get("tactical").choose(battle)
        self.assertEqual(command["kind"], "act")
        self.assertEqual(command["cell"], [5, 2])

    def test_invalid_patrol_waypoints_are_rejected(self):
        raw = tunnel_content()
        mission = next(row for row in raw["missions"] if row["id"] == "castle_tunnels")
        sentry = next(row for row in mission["units"] if row["id"] == "sewer_sentry")
        sentry["patrol_route"] = [[6, 2], [4, 1]]
        with self.assertRaises(RuleError):
            Content.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
