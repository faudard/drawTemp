# R5.B — Campaign Flow 3.0

Campaign Flow is an **optional GameProject sidecar**. It does not change the tactical
`Content` schema, `Mission.next_missions`, or `Battle` journals. StoryBook is
still responsible for narrative choices and their `when` predicates; the flow
layer consumes those same predicates at the mission-entry boundary.

## Authoring example

```json
{
  "campaign_flow": {
    "gates": {
      "castle_throne": {
        "all": [
          {"completed_mission": "castle_courtyard"},
          {"flag": "reputation_village", "gte": 2},
          {"flag": "fortification_gate", "eq": "open"}
        ]
      }
    },
    "outcomes": {
      "castle_courtyard": {
        "victory": [
          {"kind": "add_flag", "flag": "reputation_village", "amount": 2},
          {"kind": "set_flag", "flag": "fortification_gate", "value": "open"},
          {"kind": "set_flag", "flag": "enemy_garrison", "value": "weakened"},
          {"kind": "grant_item", "item": "potion", "quantity": 2}
        ],
        "defeat": [
          {"kind": "set_flag", "flag": "allies_relief", "value": false}
        ]
      }
    },
    "endings": {
      "liberation": {"completed_mission": "castle_throne"},
      "truce": {"flag": "diplomacy_agreement", "eq": true}
    }
  }
}
```

Names in this example are illustrative; mission, equipment and actor ids must
exist in the authored content. Conditions accept the **existing** narrative
syntax: `all`, `any`, `not`, `flag/eq`, `flag/gte`, `flag/lte`,
`completed_mission` and `gold_gte`. Outcomes accept the validated narrative
effects (`set_flag`, `add_flag`, `gold`, `grant_item`, `unlock_mission`,
`recruit_hero`, `equip_hero`) plus `wound` and `heal_wound` for existing
actor ids and known injury types.

Use flag namespaces to make cross-mission context readable in the Inspector:
`reputation_*` or `trust_*`, `supplies_*` or `provisions_*`,
`fortification_*`, `gate_*`, `wall_*`, `enemy_*`, `allies_*`.
Wounds use existing `HeroProgress.wounds` and affect `Campaign.prepare`.

## Runtime contract

1. Mission progression uses `Campaign.unlocked` and original
   `Mission.next_missions` / StoryBook unlocks. A `gates` condition only
   restricts **availability**, never creates a second graph or silently unlocks.
2. A real settled `victory` or `defeat` applies validated consequences to a
   **copy** of the campaign, then the normal unified session checkpoint or
   PlayerSession atomic save commits it.
3. Each consequence outcome has one ledger key, `mission:result`, preventing
   repeated grants, while allowing an earlier defeat and a later victory.
   Re-running the same outcome does not duplicate resources or wounds.
4. `Campaign.flow_digest` records the sidecar definition. Unchanged projects
   without flow remain compatible with legacy slots; changes to an active
   flow **reject older slots** rather than silently reinterpreting them.
   A migration workflow must be explicit and validated.
5. `GameSession.campaign_inspector()` and
   `PlayerSession.campaign_inspector()` return **read-only** snapshots of
   missions, flags, gold, inventory, companions, wounds, consequences and
   satisfied endings. The Player exposes a **Inspecter la campagne** panel.

## Studio inspection

From **Jeu, campagnes et sauvegardes**, select a campaign, then use
**Inspecter état R5.8** to view its live persistent state (or the new-game
state when no save is loaded). **Analyser parcours R5.11** presents a
read-only bounded route report with potential ending witnesses and blocked
missions. These actions do not mutate campaign, project or document data;
authoring remains the responsibility of the existing Story and mission tools.
The Studio launch control enforces the same campaign flow gates as the Player,
instead of launching a locked mission by reading `Campaign.unlocked` directly.

## Quality gate and standalone export

```bash
python -m unittest tests_standalone.test_campaign_flow_r5b -v
# Includes a three-mission Python/Tk source export playthrough, replays and ending.\npython scripts/campaign_flow_qa.py \
  --content sporebound/content/core.json \
  --project sporebound/content/core.game.json \
  --report /tmp/campaign-flow-r5b.json
```

To check real save compatibility **without rewriting user files**, also pass
`--save-campaign main --check-slot /path/to/slot_1.json` (old Campaign v1)
or `--save-campaign main --check-session /path/to/checkpoint.json` (unified
GameSession checkpoint). Repeat either file option as needed. The report
contains a `save_checks` section with PASS/FAIL-equivalent `compatible`
flags, source (primary vs backup) and an error message on incompatibility.
Any incompatible save makes the CLI exit nonzero while still writing its
diagnostic report.

Add `--require-ending-witnesses` to enforce witnesses to all declared endings
under **bounded symbolic exploration**. Reports include cycle/terminal
analysis, conditional gates, potential mission and ending routes, duplicate
outcome checks, warnings and truncation. A symbolic victory is a *candidate*
route, not a tactical win: tactical triggers, multi-front settlement, timed
events and genuine battle victory must additionally be certified by recorded
`GameSession` execution and replay.

`game_export4.export_game` runs the audit before replacement of the ZIP;
failures keep the old archive untouched. The output includes
`game/campaign_qa.json`, all referenced portable sources/assets and
`export_manifest.json` SHA-256 hashes. It is a playable **Python/Tk source
distribution**: unzip and run `python run_game.py` without opening the Studio.
It does not include a Python interpreter or any author's saves.

## Gates and limitations

- Strict validation rejects unknown mission/actor/equipment ids, unknown
  condition operators and effects, and invalid/out-of-bounds values.
- The ledger prevents repeated flow consequences; the existing
  `Campaign.completed` / `reward_ledger` logic still prevents repeated
  tactical XP and mission payout.
- The graph audit is finite and deliberately reports its state/depth bound. A
  missing candidate path is **not** by itself proof that an ending is
  impossible; authoring with tactical events requires scenario replay QA.
- For saves authored before a nonempty flow definition was added, load with
  the original project or implement an explicit reviewed migration. No
  automatic data loss or mission unlock rewrite is performed.
