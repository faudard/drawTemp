# Strategic timeline & tactical fronts (PR #14)

The siege can split into multiple bounded tactical battles (gate, ramparts,
courtyard, reserves) without simulating hundreds of units each tick.

`MultiFrontSession` coordinates one shared **strategic turn** and one
**focused tactical Battle**. Units on the focused map are driven exclusively
through regular `Battle.execute` commands. Each unfocused front uses the
`FrontDirector`'s deterministic doctrine-based aggregate resolution.

## Example

```python
from examples.siege_scenarios import siege_content
from sporebound.fronts import MultiFrontSession

session = MultiFrontSession(
    siege_content(),
    {"gate": "castle_ram", "wall": "castle_ramparts"},
    focused="gate",
    seed=4,
    specs={
        "gate": {"strength": 8, "opposition": 12, "doctrine": "hold"},
        "wall": {"strength": 6, "opposition": 11, "doctrine": "assault"},
    },
)
session.execute({"kind": "start_battle"})
session.reinforce(
    "wall",
    [{"id": "reserve_1", "name": "Reserve", "team": "enemy", "pos": [11, 7]}],
)
session.advance()                    # all *unfocused* fronts auto-resolve once
session.switch("wall")                # preserves losses, queues reinforcements
session.execute({"kind": "start_battle"})
session.set_doctrine("gate", "delay")
checkpoint = session.recording()     # JSON-compatible portable journal
restored = MultiFrontSession.replay(checkpoint)
assert restored.digest() == session.digest()
```

## Tactical objectives that alter other fronts

Cross-front consequences are **declarative** and validated at scenario setup.
A link listens to a Battle event emitted by a successful focused command.
Links fire at most once per session, in authored order, without activating
another tactical battle or consuming a global strategic turn.

```python
from examples.siege_fronts import siege_session
from sporebound.fronts import MultiFrontSession

session = siege_session(focused="supplies")
session.execute({"kind": "start_battle"})
session.execute({"kind": "interact", "object": "supply_cache"})
assert "throne" in session.blocked_reinforcements
assert MultiFrontSession.replay(session.recording()).digest() == session.digest()
```

The complete preset is in
[examples/siege_fronts.py](../examples/siege_fronts.py):

| Source event | Target | Deterministic consequence |
| --- | --- | --- |
| Raise the rampart portcullis via `portcullis_lever` | Gate + courtyard | Open `main_gate` even if the gate front is not loaded; remove 3 opposition from the courtyard |
| Sabotage `boiling_oil` on ramparts | Courtyard | Permanently disable the `stone_drop` defensive post |
| Loot/sabotage `supply_cache` on supply front | Throne | Cancel queued reserves and suppress future mission-triggered reinforcement waves |

The `castle_supply` mission is an **optional concurrent encounter**, not an
additional mandatory stage of the linear siege campaign.

Each link has the following schema:

```python
{
    "id": "cut_supply_route", "source": "supplies",
    "event": "interact", "match": {"object": "supply_cache"},
    "effects": [{"kind": "block_reinforcements", "front": "throne"}],
}
```

`event` accepts `interact`, `gate_breached`, `defense_sabotaged`,
`passage_installed`, `battle_end`; `match` must contain the matching
event field (`object`, `gate` or `result`). Validated actions are
`open_door` (`object`), `disable_defense` (`object`),
`reduce_opposition` (`amount`), and `block_reinforcements`.
References to source/target front and object IDs are checked up front.

An unopened front stores object overrides and strategic losses until it is
first entered. An already loaded front receives the same changes immediately.
Opening a door synchronizes its walkability; disabling a defense does not
retroactively cancel damage already inflicted. Cutting reinforcements cannot
remove a wave that has already spawned, nor arbitrary summons from abilities.
It blocks future explicit `reinforce()` orders and future scripted
`queue_wave`/`wave` trigger actions.

Linked events, affected fronts, and applied-link IDs are included in the
strategic state and validated by the **multi-front recording format v2**.
Replay of the previous unlinked v1 format remains supported. Any failure
during cross-front application restores the entire session snapshot and
does not append a successful operation to its journal.

## Logistics 1.0: bounded reserves and real actor transfers

`MultiFrontSession(..., logistics={...})` opts into an explicit strategic
convoy system; older sessions remain unchanged. A convoy does not move on the
tactical map or simulate hundreds of units. A convoy travels over **global
strategic turns** and occupies a bounded transport slot until arrival.

```python
from examples.siege_fronts import siege_session
from sporebound.fronts import MultiFrontSession

session = siege_session()
session.execute({"kind": "start_battle"})
session.send_reserves("walls", [
    {"id": "shield_reserve", "name": "Shield Reserve",
     "team": "player", "pos": [3, 6]},
])
session.transfer_units("courtyard", {"supply_scout": [3, 6]})
session.advance()  # travel tick 1
session.advance()  # the two convoys arrive: walls and courtyard
assert session.logistics.reserves["player"] == 2
assert MultiFrontSession.replay(session.recording()).digest() == session.digest()
```

The example configuration:

```python
logistics = {
    "reserves": {"player": 3, "enemy": 0},
    "capacity": 4,  # total actor slots in flight, not number of convoys
    "routes": [
        {"from": "reserve", "to": "walls", "turns": 2},
        {"from": "supplies", "to": "courtyard", "turns": 2},
    ],
}
```

- **`send_reserves(destination, actors)`** consumes one reserve point per
  actor at departure, requiring a `reserve → destination` route. Tactical
  landing cells, actor identities and footprints must be valid. Supply spent
  on a convoy that loses its destination is **not refunded**.
- **`transfer_units(destination, placements)`** removes actual, living,
  idle, player-controlled actors from the currently focused Battle. Use the
  mapping `{actor_id: [x, y]}` to specify arrival anchors. Active, casting,
  protected, relic-carrying, summoned, or already moved/acted actors cannot
  transfer. The source retains at least one living player and one strategic
  strength point. A named actor cannot duplicate a destination actor.
- **Travel** uses directional author-defined routes and cannot complete on
  the departure turn. Orders use monotonically increasing IDs, FIFO arrival
  ordering and a total in-transit actor cap. All timers are advanced by
  `session.advance()`, never by tactical CT or background processing.
- **Arrival** increments the appropriate strategic aggregate strength
  (friendly strength, enemy opposition) and queues an ordinary bounded
  encounter wave. Arrivals on unopened fronts wait for their first tactical
  entry. A busy/occupied landing may delay a wave until the landing becomes
  free; already-active enemies can still contest the landing.
- **Attrition and retreat**: a front resolved as withdrawn, victorious,
  defeated, or interdicted before its convoy arrives rejects that convoy.
  This is a real logistics loss, not a teleport or retroactive respawn.
  Transfers preserve HP, MP, statuses and actor identity, while initiative
  and partial actions are reset. The session records departure, transit,
  delivery and loss in a replayable journal.
- **Replays**: logistics sessions use multi-front save format **v3** and
  include configuration, remaining pools, routes, in-flight convoys and
  arrival/loss events. Version 1 (unlinked) and version 2 (linked, without
  logistics) remain readable. Saves must be recorded using the session API,
  not by mutating Battle objects outside the journal.

An authored **gate defeat** effect now reduces courtyard friendly strength
by three, applying corresponding damage if that tactical battle is loaded;
the same loss is materialized on first load otherwise. More consequences can
be authored with `reduce_strength`, `reduce_opposition`, and the existing
object/wave effects. This allows sacrifices and withdrawals to have lasting
consequences without simulating hundreds of combatants.

## Command centre 2.0: contested routes and rescue orders

The same `MultiFrontSession` drives a small terminal **command centre**
(without Tk, Godot or a full army simulation):

```sh
python -m examples.siege_command
python -m examples.siege_command --demo
python -m examples.siege_command --rescue-demo  # complete scripted tactical skirmish
python -m examples.siege_command --interactive
```

Both the Tk window and the terminal screen show the global strategic turn, every front's doctrine/strength/
opposition/status, focused zone, finite reserves and supplies, convoy progress
and ETA, rescue requirements and recent strategic events. The interactive
commands are `status`, `focus FRONT`, `doctrine FRONT DOCTRINE`,
`turn [N]`, `reserve FRONT ID X Y`, `transfer FRONT ID X Y`,
`escort CONVOY`, `rescue CONVOY`, `tactical JSON`,
`save FILE`, `load FILE`, `help` and `quit`.

Unlike rendering, every order is sent to the session API. A saved checkpoint
is JSON written via an atomic replace only after its replay checksum passes.
Loading verifies the journal before adopting the reconstructed session.

### Optional supply and ambush rules

Add these fields to `logistics` in an authored scenario, or omit them to
preserve the pre-existing free-travel rules:

```python
{
    "supplies": {"player": 5, "enemy": 0},
    "escorts": 1,
    "ambushes": [
        {"from": "reserve", "to": "walls",
         "casualties": 0, "delay": 2, "charges": 2}
    ],
}
```

- **Provision costs**: deploying a convoy requires one supply point per
  character; transferring an existing unit has the same cost. Rescuing an
  immobilized convoy costs one additional point. A shortage rejects the
  order atomically. Scenario configs without `supplies` preserve the former
  unlimited-provision behavior.
- **Ambush**: an authored route gets a fixed number of interceptions. On the
  next strategic synchronization, an unescorted convoy loses up to the
  configured number of actors, chosen in stable roster order from the rear.
  If survivors remain they become stranded; they cannot arrive until rescued,
  and their ETA includes the imposed delay. A totally destroyed convoy is
  permanently lost. The attack is deterministic, uses no per-soldier AI, and
  consumes one authored ambush charge.
- **Escort**: `escort_convoy(ID)` consumes one limited escort slot before
  the convoy is intercepted. It prevents the encounter from consuming an
  ambush charge and preserves the convoy's original ETA.
- **Rescue**: `rescue_convoy(ID)` sends a logistical recovery order for a
  *stranded surviving* convoy only. Spending one additional supply unblocks
  the convoy; it reaches the destination no earlier than the following turn.
  This is a strategic recovery action, **not** a playable rescue skirmish yet.
- **Determinism and migration**: sessions with the optional enhanced
  logistics fields use multi-front replay format **v4**. Records from
  versions 1, 2 and 3 remain accepted with their previous semantics.
  A replay reconstructs supply costs, ambush charges, actor losses,
  escort orders and rescue orders, then checks the complete state digest.

Examples keep tactical missions small and set transport capacity independently
from the active-combatant cap. Convoy rescue, supply usage and front orders can
be run from a terminal before an animated UI is developed.

## Playable convoy rescue: tactical wagon encounter

When a convoy is stranded after a route ambush, the commander now has
**three distinct choices**:

1. `rescue_convoy(id)`: pay one provision for an automatic recovery order
   (the older logistics behavior remains supported).
2. `start_rescue(id)`: fight a genuine, small tactical battle. The side
   encounter uses ordinary `Battle.execute` actions, weapons, AI and the
   existing objective system. Its mission declares a **protected player wagon**;
   eliminate the ambushers while keeping that wagon alive.
3. `abandon_convoy(id)`: abandon the stranded convoy, lose its travelling
   actors and release their transport capacity. The order also permits
   withdrawing from an already-started rescue skirmish.

Enable the tactical option by adding
`"rescue_mission": "castle_convoy_rescue"` to the `logistics`
configuration. The referenced mission must exist, use the `eliminate`
objective and name a friendly `protected_id`. This validates at session
construction. The opt-in siege preset is
`siege_session(contested=True)`.

```python
session.send_reserves("walls", [
    {"id": "road_guard", "name": "Road Guard",
     "team": "player", "pos": [3, 6]}])
session.advance()                       # ambush strands convoy_1
encounter = session.start_rescue("convoy_1")
# Play until the encounter resolves, one normal tactical command at a time:
session.execute_rescue("convoy_1", {"kind": "end"})
```

The active rescue skirmish **freezes strategic advancement and front
switching**, so a convoy cannot simultaneously arrive while its wagon is
under attack. The convoy actors remain held in transit until resolution;
the skirmish contains a separate bounded escort and wagon, **never a second
copy of travelling heroes**.

- **Victory**: on elimination of the last ambusher while the wagon survives,
  the convoy is unstranded, retains its remaining actors, resumes with ETA no
  earlier than the next strategic turn, and salvages one provision when the
  optional supply pool exists.
- **Defeat**: if the wagon dies or the rescue squad is eliminated, the entire
  remaining convoy is lost. It cannot be respawned or re-used.
- **Abandonment**: loses the remaining convoy and frees capacity; no reward.
- **Determinism**: `start_rescue`, `execute_rescue`, and
  `abandon_convoy` are explicitly journaled. A mid-battle save includes the
  rescue Battle state; replay rebuilds every tactical command and checks the
  aggregate digest. No direct side-battle mutations are replayable.
- **Interfaces**: from `python -m examples.siege_command --interactive`,
  use `skirmish convoy_1`, then
  `rescue-act convoy_1 {"kind":"end"}` (or other normal tactical commands),
  and `abandon convoy_1` if required. The Tk command center shows wagon HP,
  the active fighter and separate **Combat de secours** / **Abandonner** actions.

This is a reusable **mission reference**, not an extra always-simulated front.
No global turn is advanced by tactical rescue actions. The encounter is a
deliberately bounded proof of the architecture; scenario authors may replace
the map, enemies, defensive positions or wagon stats without modifying
strategic code.

## Branching convoy outcomes: evacuation, ransom, salvage, pursuit

Scenario authors can opt into `logistics["choices"]` without changing
existing v1-v4 recordings. This requires a configured `rescue_mission` and
a finite `supplies` pool:

```python
"choices": {
    "ransom": 2,
    "pursuit_mission": "castle_convoy_pursuit",
    "pursuit_reward": 2,
}
```

For a stranded **friendly** convoy, the commander now chooses:

| Order | Conditions | Survivor/cargo consequences |
| --- | --- | --- |
| `evacuate_convoy(id)` | Stranded crew (before or during skirmish) | All remaining crew survives and can arrive after at least two more strategic turns; cargo is lost, creating a pursuit target |
| `salvage_convoy(id)` | Active rescue skirmish; wagon and escort alive; at least one, but not all, ambushers eliminated | Withdraw crew and half the cargo, rounded down; abandoned cargo may be pursued |
| `negotiate_convoy(id)` | Active rescue skirmish; wagon alive; 2 provisions available in default scenario | Pay an immediate ransom and save the entire crew/cargo; no recovered supplies are awarded |
| `start_pursuit(id)` | Lost loot from evacuation or partial salvage, destination front still active | Launch a second small `Battle`, hunting the escaping pillards |
| `abandon_pursuit(id)` | An unresolved pursuit target | Give up its loot without endangering an already evacuated convoy |

Cargo in this opt-in model is a **fixed two-point value per transported
actor**. This is **potential loot**, not extra inventory awarded at dispatch.
Full rescue remains unchanged; voluntary partial recovery credits the saved
share to the supply pool. The separate pursuit awards up to
`pursuit_reward` provisions and removes **one enemy opposition point** on
the destination front after a genuine tactical victory (without granting
an automatic strategic victory). Pursuit defeat forfeits the remaining loot,
but cannot resurrect or destroy actors that already evacuated.

As with wagon rescue, **time freezes** during an active pursuit battle;
all outcomes, tactical commands, and chosen paths are appended to the
single strategic operation journal. The same replay **v4** format covers
these opt-in branches; absent `choices`, no state keys, defaults or old
checksums change.

```sh
python -m examples.siege_command --choices-demo
python -m unittest discover -s tests_standalone -p test_convoy_choices.py -v
```

Terminal commands: `evacuate ID`, `salvage ID`, `negotiate ID`,
`pursue ID`, `pursuit-act ID {"kind":"end"}`,
`giveup-pursuit ID`. Tk adds **Évacuer équipage**, **Butin partiel**,
**Négocier**, **Poursuivre pillards** and **Abandon poursuite**; the normal
tactical input automatically routes actions to the current pursuit battle.

## Campaign-level choices and locked throne (save format v5)

A new **opt-in** `MultiFrontSession(..., campaign={...})` policy validates
prerequisite fronts and authored alternatives to an outright tactical victory.
It is distinct from the existing sequential `examples.siege_campaign` runner
and does not alter the older v1-v4 multi-front session format.

```python
{
    "final_front": "throne",
    "required_fronts": {
        "gate": ["victory", "negotiated"],
        "courtyard": ["victory", "partial"],
    },
    "partial": {
        "courtyard": {
            "event": "defense_sabotaged", "object": "stone_drop",
            "cost": 1, "target": "throne", "target_loss": 2,
        },
    },
    "negotiation": {
        "gate": {"supplies": 2, "target": "throne", "target_loss": 1},
    },
    "retreat": {
        "gate": {"target": "courtyard", "target_loss": 3},
        "courtyard": {"target": "throne", "target_loss": 3},
    },
}
```

With this siege policy, the throne is **locked** until the gate is
either truly won or negotiated and the courtyard either truly won or
secured in part. A tactical Battle win sets the corresponding front
status at the normal `session.execute(command)` journal boundary.
An unfocused front can also reach an ordinary victory via the pre-existing
deterministic strategic resolution.

- **`negotiate_front("gate")`**: an explicit strategic truce at a safe
  tactical turn boundary, costs two actual provisions and permanently reduces
  friendly strength on the throne front by one. An authored agreement
  cannot be used if the gate fight is already lost.
- **`partial_front("courtyard")`**: requires an actual
  `defense_sabotaged` event from the `stone_drop` objective, not a fake
  battle result. The remaining courtyard garrison is reduced by one and
  the eventual throne attackers by two; the courtyard records a distinct
  `partial` outcome, even if enemies survive. Choosing this outcome
  is allowed only at a safe activation boundary.
- **`withdraw_front("gate")`**: permanently yields the gate, weakens
  the friendly courtyard garrison by three, and blocks this campaign route
  to the throne. Retreat doctrine on an *unfocused* gate applies the same
  adjacent-front cost exactly once when the front becomes withdrawn.
- **Final result**: the actual throne `Battle` must end in victory before
  `campaign.status` reports `victory`. Loss of a required front without an
  accepted outcome yields `blocked`; failure on the throne yields `defeat`.
  This does not invent automatic tactical combat for the other fronts.

All campaign choices, diplomacy payments, authenticated tactical objective
events, penalties and offscreen withdrawals are part of a deterministic
global journal. Campaigned sessions record **version 5**, including the
complete policy in the checksummed state. Older saves retain their previous
semantics and checksum. A tampered policy is rejected at replay.

Terminal: `partial FRONT`, `parley FRONT`, `withdraw FRONT`,
and `focus throne` once unlocked. The Tk command center provides the
same choices and the campaign's gate status.

```sh
python -m examples.siege_strategy_demo  # gate diplomacy, courtyard partial, boss victory
python -m examples.siege_command --gui --campaign
python -m examples.siege_command --interactive --campaign
python -m unittest discover -s tests_standalone -p test_siege_campaign.py -v
```

## Contracts and limitations

- **Bounded tactical maps**: a front keeps its own units, CT, statuses and
  mission objectives. There is no army-wide simultaneous tactical AI.
- **Explicit synchronization**: `advance()` is the only way to advance
  the global strategic turn. It never advances the focused Battle's CT.
- **Stable simulation**: `hold`, `assault`, `delay`, `retreat`
  use fixed and deterministic losses; sorted front names avoid dictionary
  insertion-order dependence. The strategic seed is retained for future rules.
- **Delayed materialization**: an unopened front retains its aggregate
  losses. On its first opening those losses are applied, in stable unit-ID
  order, to its tactical roster; subsequent unfocused turns apply only deltas.
- **Safe focus changes**: a front cannot be entered after it has concluded,
  and a unit in the middle of Move/Act must complete its activation before
  switching. A failed focus switch leaves previous state unchanged.
- **Reinforcements**: queued as encounter waves and delivered when the front
  becomes focused (or at a strategic sync when it is already focused).
  Waves respect the small-scale encounter cap.
- **Deterministic recovery**: use `session.execute`,
  `session.set_doctrine`, `session.reinforce`, `session.switch` and
  `session.advance` for all mutations; then use `session.recording()`
  and `MultiFrontSession.replay(...)`. Replay rebuilds every Battle and
  verifies the full multi-front checksum, including offscreen casualties.
  `restore(recording)` also accepts a verified recording.
- **Not a generic snapshot loader**: `state()` is for inspection. Direct
  calls to `session.active.execute()` or direct mutation of Battles are
  outside the multi-front journal; replays detect resulting divergence.
  A single `Battle.replay` cannot reproduce external strategic attrition.
- **No tactical omniscience**: offscreen resolution uses aggregate strength,
  not pathfinding, cover, line of sight or a hidden live Battle simulation.
  Opening an already simulated front applies HP attrition but does not
  reconstruct hypothetical individual offscreen moves. This is intentional.

Next milestones: alternate breach routes, stronger diplomacy consequences,
campaign-level recovery after a lost prerequisite, authored treaty branches,
and graphical arrival-zone / global timeline editing.
