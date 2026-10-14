# Jeanne d'Arc — Visual Identity Pass (Player MVP)

## Scope

The prologue's map remains owned by `GameSession`; this pass changes **only
presentation**. It builds upon the fullscreen exploration, camera and pause
shortcuts in PR #213. It should be reviewed/merged after that PR.

- **Scene readability:** narrative terrain is painted in coherent bands (fields,
  village lanes, forest border). Hand-painted terrain and decor atlases remain
  shared with the Studio; decorations never change obstacles or available moves.
- **Characters:** living civilians and witnesses are now composited as actual
  sprite actors by the isometric renderer, rather than circles with letters.
  Lost/rescued actors keep their narrative semantics. There is no new game unit.
- **Objectives:** restrained wayfinding diamonds/ground rings distinguish
  discovered, exit and pending story interactions.
- **Atmosphere:** a quiet per-theme gradient surrounds the map without adding
  weather simulation, RNG, save fields or frame timers.
- **UI:** common warm parchment/slate colors, typographic hierarchy, readable
  buttons/tabs/forms. High-contrast mode remains explicit and deterministic.
- **Input:** hit tests still use `IsoGeometry.hit_test` on unchanged grid
  coordinates; the decorative canvas tags do not intercept game commands.

## Acceptance checks

```sh
python -m unittest \
  tests_standalone.test_exploration_iso_view \
  tests_standalone.test_player_visual_theme \
  tests_standalone.test_player_immersive_map \
  tests_standalone.test_jeanne_prologue -v

SPOREBOUND_GUI_SMOKE=1 xvfb-run -a python -m unittest \
  tests_standalone.test_exploration_iso_view_gui \
  tests_standalone.test_player_immersive_map -v
```

A final human visual pass is still required at 800×580, 1160×820 and
1920×1080: verify hero/PNJ visibility against foliage, label legibility,
high-contrast controls, prompt legibility, and that story choices cannot be
obscured. No 100% visual quality claim is made from unit tests alone.

## Follow-on art production

Cohesive peasant Jeanne sprite variants, civilian-specific idle/walk poses,
animated embers/foliage and authored scene art are still **separate asset
production** work, requiring goldens and real Player screenshots. This pass
integrates the current atlases; it does not pretend that placeholder character
art has become commissioned final art.
