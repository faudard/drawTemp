# Combat Fundamentals — Comparative Analysis

This is a design comparison, not a request to clone any one title.

## Evaluation lens

Each reference is examined for:
- time/action economy;
- spatial decision making;
- terrain/elevation;
- information/RNG;
- build expression;
- objective/encounter design;
- lesson for Sporebound.

## Final Fantasy Tactics

### Relevant ideas
- CT rises with Speed until a unit can act.
- Move and Act are separable.
- doing fewer actions spends less CT.
- slow actions resolve later on the shared battle clock.
- reactions, facing, Brave/Faith and jobs create cross-system interactions.

### Sporebound
**KEEP:** CT, Move/Act ordering, delayed casts, reaction layer, constrained build mixing.

**ADAPT:** formulas, Brave/Faith and evasion need clearer player-facing explanations.

**REJECT for now:** zodiac compatibility. It adds hidden matchup arithmetic before the rest of the combat loop is proven.

Source:
https://www.neoseeker.com/finalfantasytactics/faqs/26855-final-fantasy-tactics-battle-mechanics.html

## Tactics Ogre: Reborn

### Relevant ideas
- strong pre-battle party composition;
- class identity plus equipment/skills/magic;
- unit-by-unit progression in Reborn;
- encounter preparation matters before the first action.

### Sporebound
**KEEP:** formation/deployment stage and strong class identity.

**ADAPT:** avoid letting progression complexity overwhelm encounter readability.

Source:
https://amp.square-enix-games.com/en_US/news/tactics-ogre-reborn-preview

## Fell Seal: Arbiter's Mark

### Relevant ideas
- primary class plus subclass;
- active abilities, passives and one counter slot;
- gradual class unlocking;
- explicit restrictions produce build identity.

### Sporebound
**KEEP:** constrained mixing of action set + passive/reaction choices.

**ADAPT:** keep the number of simultaneous passive layers smaller until combat readability is validated.

Sources:
https://fellseal.backerkit.com/hosted_preorders/project_updates?page=9
https://fellseal.fandom.com/wiki/Abilities

## Triangle Strategy

### Relevant ideas
Nintendo's developer material explicitly emphasizes:
- initial placement;
- multi-level maps;
- knockback;
- traps;
- high-ground advantages;
- characters whose utility emerges from terrain and team interaction.

Nintendo's consumer documentation also highlights rear attacks, follow-up attacks, elevation and elemental terrain interactions.

### Sporebound
**KEEP:** elevation, shove/fall damage, setup phase, terrain as a system.

**ADAPT:** elemental terrain interactions into data-driven effects.

Source:
https://www.nintendo.com/en-ca/whatsnew/get-insight-and-tips-for-triangle-strategy-from-the-devs-themselves/

## Fire Emblem Engage

### Relevant idea
The development team describes a direct conflict between spectacular movement abilities and stage design: very large movement bonuses risk making the tactical map irrelevant.

### Sporebound
**KEEP:** strong mobility can be exciting.

**ADAPT:** teleport, haste, movement boosts and jump need encounter-aware costs and threat consequences.

**REJECT:** unrestricted mobility that trivializes chokepoints, elevation and objective routing.

Source:
https://www.nintendo.com/us/whatsnew/ask-the-developer-vol-8-fire-emblem-engage-part-3/

## Into the Breach

### Relevant ideas
Subset Games describes:
- telegraphed enemy intent;
- reduced reliance on randomness;
- failure that should be understandable;
- objectives beyond killing;
- weapons whose displacement/side effects can matter more than damage;
- extensive iteration and feature cuts.

### Sporebound
**KEEP:** forecast clarity, visible consequences, displacement as a high-value mechanic.

**ADAPT:** Sporebound remains an RPG with probabilities; it should borrow clarity rather than become a deterministic puzzle.

**REJECT:** hidden consequences that the player could reasonably have predicted.

Sources:
https://www.gamedeveloper.com/game-platforms/road-to-the-igf-subset-games-i-into-the-breach-i-
https://www.gdcvault.com/play/1026333/-Into-the-Breach-Design

## Mario + Rabbids: Sparks of Hope

### Relevant ideas
Ubisoft's GDC case study separates battle creation into:
- topography;
- navigation;
- cover;
- spawn/zoning;
- objectives;
- enemy archetypes;
- an explicit battle "intention".

The generated content remains constrained by authored rules.

### Sporebound
**KEEP:** encounter intention and layered authoring model.

**ADAPT:** use the same abstraction even for handcrafted missions first. Procedural generation is optional later.

Source:
https://news.ubisoft.com/en-gb/article/3NxX4lLLU7pkebcFDaoOen/gdc-2023-how-mario-rabbids-sparks-of-hope-improved-procedural-generation-with-layered-battles

## Gears Tactics

### Relevant ideas
The published Game AI Pro case study discusses preserving tactical clarity while coordinating multiple enemies, and notes that enemy composition can collapse the player's decision space when one action is always obviously best.

### Sporebound
**KEEP:** enemy archetypes and coordination should be evaluated by the decisions they force.

**ADAPT:** future AI should reason about group roles and spatial intent while preserving deterministic debugging.

Source:
https://www.gameaipro.com/GameAIProOnlineEdition2021/GameAIProOnlineEdition2021_Chapter03_Gearing_the_Tactics_Genre_Simultaneous_AI_Actions_in_Gears_Tactics.pdf

## Cross-game synthesis

| Axis | Reference strength | Sporebound direction |
| --- | --- | --- |
| Time | FFT | CT + visible timeline + delayed actions |
| Position | Triangle Strategy / Fire Emblem | elevation, facing, threat, constrained mobility |
| Terrain | Triangle Strategy / Into the Breach | forced movement + stateful/composable terrain |
| Build | FFT / Fell Seal / Tactics Ogre | expressive but slot-constrained builds |
| Objective | Mario + Rabbids / Into the Breach | every encounter has a stated tactical intention |
| Readability | Into the Breach / Fire Emblem | previews, threat maps, explicit costs |
| AI | Gears Tactics / Game AI Pro | role-aware utility + spatial reasoning |
| Authoring | Mario + Rabbids | layered encounter editor and validation |

## Design conclusion

The target is not "FFT in Python".

The useful synthesis is:

**FFT time/build structure**
+ **Triangle Strategy spatiality**
+ **Into the Breach readability/system interactions**
+ **Mario + Rabbids encounter authoring discipline**
+ **modern tactical AI tooling**.

That combination gives Sporebound a distinct design direction while remaining recognizably a tactical JRPG.
