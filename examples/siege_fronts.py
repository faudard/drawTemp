"""Causal castle fronts: use the same MultiFrontSession for play, AI and replay.

    python -m examples.siege_fronts

The example prints the front rules and a verified save/replay smoke run.
Use `session.execute(...)` for every tactical command if saving a session.
"""
from sporebound.fronts import MultiFrontSession
from .siege_scenarios import siege_content


SIEGE_LINKS = [
    {
        "id": "raise_herse",
        "source": "walls", "event": "interact",
        "match": {"object": "portcullis_lever"},
        "effects": [
            {"kind": "open_door", "front": "gate", "object": "main_gate"},
            {"kind": "reduce_opposition", "front": "courtyard", "amount": 3},
        ],
    },
    {
        "id": "secure_ramparts",
        "source": "walls", "event": "defense_sabotaged",
        "match": {"object": "boiling_oil"},
        "effects": [
            {"kind": "disable_defense", "front": "courtyard",
             "object": "stone_drop"},
        ],
    },
    {
        "id": "gate_collapse",
        "source": "gate", "event": "battle_end",
        "match": {"result": "defeat"},
        "effects": [
            {"kind": "reduce_strength", "front": "courtyard", "amount": 3},
        ],
    },
    {
        "id": "cut_supply_route",
        "source": "supplies", "event": "interact",
        "match": {"object": "supply_cache"},
        "effects": [
            {"kind": "block_reinforcements", "front": "throne"},
        ],
    },
]


def siege_session(seed=1, focused="supplies", *, contested=False, decisions=False):
    logistics = {
        "reserves": {"player": 3, "enemy": 0},
        "capacity": 4,
        "routes": [
            {"from": "reserve", "to": "walls", "turns": 2},
            {"from": "reserve", "to": "gate", "turns": 1},
            {"from": "supplies", "to": "courtyard", "turns": 2},
            {"from": "walls", "to": "courtyard", "turns": 1},
            {"from": "courtyard", "to": "throne", "turns": 2},
        ],
    }
    if contested:
        logistics.update(
            supplies={"player": 5, "enemy": 0},
            escorts=1,
            rescue_mission="castle_convoy_rescue",
            ambushes=[{"from": "reserve", "to": "walls",
                       "casualties": 0, "delay": 2, "charges": 2},
                      {"from": "supplies", "to": "courtyard",
                       "casualties": 1, "delay": 2, "charges": 1}],
        )
    if decisions:
        if not contested:
            raise ValueError("Advanced convoy choices require contested routes")
        logistics["choices"] = {
            "ransom": 2,
            "pursuit_mission": "castle_convoy_pursuit",
            "pursuit_reward": 2,
        }
    return MultiFrontSession(
        siege_content(),
        {"walls": "castle_ramparts", "gate": "castle_ram",
         "courtyard": "castle_courtyard", "supplies": "castle_supply",
         "throne": "castle_throne"},
        focused=focused, seed=seed,
        specs={
            "walls": {"strength": 8, "opposition": 12, "doctrine": "assault"},
            "gate": {"strength": 10, "opposition": 14, "doctrine": "hold"},
            "courtyard": {"strength": 9, "opposition": 16, "doctrine": "delay"},
            "supplies": {"strength": 6, "opposition": 10, "doctrine": "hold"},
            "throne": {"strength": 7, "opposition": 18, "doctrine": "hold"},
        },
        links=SIEGE_LINKS,
        logistics=logistics,
    )


if __name__ == "__main__":
    session = siege_session()
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "interact", "object": "supply_cache"})
    session.send_reserves("walls", [
        {"id": "shield_reserve", "name": "Shield Reserve", "team": "player",
         "pos": [3, 6]}])
    session.transfer_units("courtyard", {"supply_scout": [3, 6]})
    session.advance()
    session.advance()
    restored = MultiFrontSession.replay(session.recording())
    assert restored.digest() == session.digest()
    print("Activated objectives:", sorted(session.applied_links))
    print("Blocked enemy reinforcements:", sorted(session.blocked_reinforcements))
    print("Strategic turn:", session.timeline.turn)
    print("Convoys still travelling:", len(session.logistics.in_transit))
    print("Player reserves remaining:", session.logistics.reserves["player"])
    print("Deterministic replay: OK")
