# R41.A — Classic RPG party foundations

Roadmap: [R41 / DrawTemp 8.1–9.0](../DRAWTEMP_8_1_TO_9_0_DETAILED_ROADMAP_R41_R50.md).

**Status: code candidate — not certified R41, not DrawTemp 8.1.**

## Architecture decision

- Reuse R25 game_modes: classic_rpg already resolves to RPG_TURN. Tactical missions still resolve to TACTICAL_CT by existing validation.
- Authored membership defaults live in GameProject.extensions under the versioned drawtemp.party_rpg namespace (existing R24 envelope, not an external JSON file).
- The running roster, active group and bounded replay journal belong exclusively to GameSession.
- XP, classes, equipment and skills stay in the existing Campaign.heroes / HeroProgress data model. Gold and inventory stay in Campaign. No second database, combat engine or inventory.
- The deterministic rpg_turn_order speed/ID primitive is not a turn-based battle executor. It does not alter CT or settle encounters.

## Project manifest contract

An example extension data payload for the existing R24 envelope, with schema_version=1:

    {
      "version": 1,
      "campaigns": {
        "main": {
          "recruitable": ["jeanne", "margot"],
          "initial": ["jeanne"],
          "active": ["jeanne"],
          "max_active": 2
        }
      }
    }

The project must have an explicit RPG_TURN profile. All tactical missions remain pinned to srpg when the project default uses classic_rpg.

- recruitable: existing player-unit IDs from Content missions, not duplicate actor records.
- initial: initially recruited subset.
- active: initially deployed subset (max_active 1..8); remaining recruits are reserves.
- Additional actors must first be authored through the existing Content/character tooling.
- Unknown versions/fields, duplicate references, non-player IDs, boolean capacity, overcapacity or missing campaign IDs fail closed during canonical project validation.

## Canonical runtime commands

- GameSession.party_state() provides a detached roster snapshot.
- GameSession.party_recruit(hero_id) adds an eligible reserve hero, materializing canonical HeroProgress atomically.
- GameSession.party_set_active(hero_ids) changes only team selection and retains canonical stats and inventory.
- Commands are rejected during battle or pending dialogue, or when they would be invalid/no-op.
- The optional classic_party GameSession checkpoint field contains membership, active roster and a replay-verified bounded event list (512 events). Missing, extra or replay-divergent data fails closed.
- Historical projects lack this extension and their GameSession recordings remain unchanged. Opting in intentionally changes the project digest; rollback means restoring the original project and its matching checkpoint, never silently deleting save keys.

## Verification commands

    python -m unittest tests_standalone.test_r41_classic_party -v
    python -m unittest tests_standalone.test_r25_foundation -v
    python -m unittest tests_standalone.test_game_session -v
    python -m unittest tests_standalone.test_drawtemp5_r1 -v

These are **required commands, not locally executed or passed results**. Review the exact final PR SHA and CI outcomes separately.

## Remaining R41 deliverables

R41.B: Qt Party/Class/Encounter Studio; real turn-based Player battles with attack/guard/ability/item/flee, targeting, combat transitions, keyboard/controller input and UI validation.

R41.C: VS-41 village → dungeon → two encounters → loot → return; recruiting three heroes, inventory and quest progress, deterministic replay/save/load, licensed assets, independent PC export, tri-OS CI and human/GPU proof.

**Gate:** a passing R41.A foundation is not R41 8.1 certification. No Player combat or clean-machine release is claimed by this PR.
