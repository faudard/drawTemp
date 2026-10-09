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

Next milestones: logistics/supply and limited transfers between fronts,
player-selectable arrival points, doctrine presets, tactical objectives that
alter strategic strength, and cross-front victory/failure conditions.
