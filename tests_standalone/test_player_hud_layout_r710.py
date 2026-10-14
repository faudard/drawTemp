"""R7.10 sections stay deterministic and independent of Tk/GameSession."""
from dataclasses import replace
import unittest

from sporebound.__main__ import DEFAULT_CONTENT
from sporebound.engine import Battle
from sporebound.model import Content
from sporebound.presentation import battle_frame
from sporebound.player_hud_layout import combat_hud_sections
from sporebound.player_ux import combat_hud


class PlayerHudLayoutR710Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = Content.load(DEFAULT_CONTENT)

    def test_sections_reuse_canonical_ct_and_roster_without_mutation(self):
        battle = Battle(self.content, "garden", seed=9)
        before = battle.digest()
        frame = battle_frame(battle, (1, 1))
        policy = combat_hud(frame, battle.mission.objective)
        sections = combat_hud_sections(frame, battle.mission.objective)
        self.assertEqual(sections.objective, str(battle.mission.objective))
        self.assertEqual(sections.timeline, policy.timeline[:8])
        self.assertEqual(sections.selection, policy.selection_summary)
        self.assertEqual(
            sections.party,
            tuple(row for row, unit in zip(policy.roster, frame.actors)
                  if unit.team == "player"))
        self.assertEqual(sections, combat_hud_sections(frame, battle.mission.objective))
        self.assertEqual(battle.digest(), before)

    def test_compact_density_and_overflow_are_read_only(self):
        battle = Battle(self.content, "garden", seed=7)
        frame = battle_frame(battle)
        large_timeline = tuple(
            {"unit": "actor" + str(i), "active": i == 0, "eta_ticks": i}
            for i in range(15))
        frame = replace(frame, timeline=large_timeline)
        small = combat_hud_sections(frame, compact=True, timeline_limit=4)
        full = combat_hud_sections(frame, compact=False, timeline_limit=15)
        self.assertEqual(len(small.timeline), 5)
        self.assertEqual(small.timeline[-1], "+11 activations")
        self.assertEqual(len(full.timeline), 15)
        self.assertLessEqual(len(small.party), 4)
        self.assertEqual(full.party[:len(small.party)], small.party)

    def test_journal_is_bounded_and_keeps_existing_event_text(self):
        battle = Battle(self.content, "garden", seed=3)
        frame = battle_frame(battle)
        events = tuple({"kind": "log", "seq": i} for i in range(60))
        frame = replace(frame, events=events)
        sections = combat_hud_sections(frame, journal_limit=3)
        self.assertEqual(sections.journal, tuple(str(row) for row in events[-3:]))
        self.assertEqual(combat_hud_sections(frame, journal_limit=0).journal, ())

    def test_focus_handles_deployment_and_multicell_actors(self):
        battle = Battle(self.content, "garden", seed=1)
        frame = battle_frame(battle)
        actor = next(a for a in frame.actors if a.team == "player")
        extended = replace(actor, footprint=(2, 2), active=True)
        modified = replace(frame, actors=(extended,), active_id=actor.id)
        rendered = combat_hud_sections(modified)
        self.assertIn(actor.name, rendered.focus)
        self.assertIn("PV ", rendered.focus)
        self.assertIn("MP ", rendered.focus)
        self.assertEqual(len(rendered.party), 1)
        self.assertIn("Déploiement", combat_hud_sections(
            replace(modified, active_id=None)).focus)

    def test_reject_incorrect_parameters(self):
        battle = Battle(self.content, "garden", seed=2)
        frame = battle_frame(battle)
        for kwargs in ({"timeline_limit": 0}, {"journal_limit": -1},
                       {"compact": "yes"}, {"timeline_limit": True}):
            with self.assertRaises(ValueError):
                combat_hud_sections(frame, **kwargs)
        with self.assertRaises(ValueError):
            combat_hud_sections(None)


if __name__ == "__main__":
    unittest.main()
