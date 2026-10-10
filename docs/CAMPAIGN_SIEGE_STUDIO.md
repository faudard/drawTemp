# 2.5.4 — Campaign & Siege Studio

The **Campagne & siège** tab of the existing Python/Tk Studio edits the same
validated systems already used by castle siege examples. Start with:

```shell
python -m sporebound editor sporebound/content/core.json
```

No hand editing of JSON or modifications to the siege engine are required.

## Workflow (authoring → play → checkpoint)

1. Create missions and place gates, mechanisms, defenses and characters in the
   tactical **Carte et combat** / **Graphe des événements** editors.
2. Choose a parent campaign, then **Nouveau siège**. A first front uses the
   currently selected tactical mission. Add other fronts by naming them and
   selecting their associated missions.
3. Edit strength, opposition and doctrine per front, and choose the front the
   player controls initially. The graph displays concurrent fronts.
4. Optionally select a final sector and at least one prerequisite front,
   with accepted results (`victory`, `partial`, `negotiated`). The final
   sector is protected from automatic/offscreen victory.
5. Add causal cross-front links. Select a real source event and object
   (or an end-of-battle result), target another front and add one or more
   consequences (door opened, defense disabled, strength/opposition reduced,
   reinforcement waves blocked). These are the existing
   `front_links` event/effect contracts; never fabricated events.
6. Add timed reinforcement waves. Select a front, an existing actor archetype,
   a spawn cell, a team and a tactical tick. This writes a normal
   `queue_wave` **mission trigger**, with the existing encounter cap.
   Wave editing is undoable through the normal content document.
7. Click **Simuler 8 tours** to inspect deterministic doctrine-based
   offscreen attrition. This **does not** simulate tactical victories, unlock
   the final boss or change the saved mission.
8. Save **both** the tactical content JSON and the game's `.game.json`
   manifest. Campaign siege blueprints live in the latter.
9. Start the siege and click **Jouer dans Command Center** to control each
   sector through the existing tactical/strategic session. When returning to
   the Studio, **Sauver partie** / **Charger partie** use slots 1–9.
   The checkpoint holds the versioned session journal, and load verifies the
   replay and blueprint/content compatibility.

For linear mission progression, narrative prologues, dialogue choices and
alternative endings, use the existing **Graphe des missions** and
**Scénario & dialogues** editors. They edit the same parent campaign and
missions; the siege blueprint adds concurrent fronts and tactical consequences.

## Persistence contract

Old game projects load unchanged. New manifests optionally include:

```json
{
  "sieges": [{
    "id": "castle",
    "campaign_id": "main",
    "fronts": {"gate": "castle_ram", "walls": "castle_ramparts"},
    "focused": "gate",
    "specs": {
      "gate": {"strength": 10, "opposition": 10, "doctrine": "hold"},
      "walls": {"strength": 8, "opposition": 12, "doctrine": "assault"}
    },
    "links": [],
    "campaign": {
      "final_front": "walls",
      "required_fronts": {"gate": ["victory"]},
      "partial": {}, "negotiation": {}, "retreat": {}
    }
  }]
}
```

This is an example of the **serialized** form, not something the user must
author manually. Each edit is validated transactionally against the existing
`Content`, `FrontDirector`, `front_links`, and `SiegeCampaign` contracts.
A failed edit cannot corrupt the current project.

A siege checkpoint is stored in
`<project-stem>_saves/siege_<id>/slot_N.json`.
Content, links, rules, front configuration and the replay journal must match
the current authored siege to resume. If the authored project was changed
since saving, re-create a new session instead of replaying incompatible data.

## Acceptance gates

- [x] Create/update/remove fronts from Tk without JSON editing
- [x] Configure focus, doctrines, final sector and tactical outcome gates
- [x] Compose and validate event links across sectors
- [x] Author encounter-driven reinforcement waves into tactical missions
- [x] Preview shared strategic turns without modifying the session
- [x] Create a playable `MultiFrontSession` from the project manifest
- [x] Save and load a deterministic replay checkpoint
- [x] Keep legacy game projects and ordinary solo campaigns compatible
- [ ] Visual edit of advanced logistics, alternative-route costs, treaties and
  counteroffensive policies (separate enhancement; core engine already supports
  these mechanisms)

## 2.5.4.2 — Play the Studio siege in the normal Player

The Player now reads the optional `GameProject.sieges` collection directly.
To use it:

1. In the Studio, create at least one front and save both the tactical
   `content.json` and game `content.game.json` project.
2. Run `python -m sporebound player --content content.json --project content.game.json`.
3. Choose the parent campaign/slot and click **Nouvelle partie** or **Continuer**.
4. In the campaign screen, **Sièges créés dans le Studio** lists the plans
   for that campaign. A locked siege shows the *mission ids* still required.
   When every front mission is unlocked, select **Jouer le siège : …**.
5. The standard tactical view, **Timeline / Fronts**, doctrines, switching
   and autosave now operate on the Studio blueprint; **Continuer** restores
   its original id and exact replay-verified multi-front state.

A configured siege never bypasses campaign unlocks or pending dialogue.
Distinct front ids **must reference distinct missions** at play time, even
though the 2.5.4 authoring schema still permits a duplicated mission to
support editing before launch. Every mutation passes through the existing
PlayerController rollback and version-2 SessionStore with a backup generation.
No separate siege save format is introduced in Player. The Studio's older
**Sauver partie** / **Charger siège** independent checkpoint files remain
separate and are **not** silently imported into Player slots.

Compatibility: older GameSession checkpoints have no `siege_id` field;
ad-hoc multi-front encounters continue to omit it. An authored siege
checkpoint includes a siege id and verifies its parent campaign, initial
front/focus/specs, link rules and finale against the current project on load.
Editing the project/content after saving requires a new compatible session.

### Acceptance tests

```shell
python -m unittest tests_standalone.test_configured_siege_player -v
SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python3 -m unittest discover -s tests_standalone -p test_configured_siege_player_gui.py -v
```

Next: 2.5.4.3 visual logistics/routes and 2.5.4.4 route/diplomacy policies.
