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
        "id": "cut_supply_route",
        "source": "supplies", "event": "interact",
        "match": {"object": "supply_cache"},
        "effects": [
            {"kind": "block_reinforcements", "front": "throne"},
        ],
    },
]


def siege_session(seed=1, focused="supplies"):
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
    )


if __name__ == "__main__":
    session = siege_session()
    session.execute({"kind": "start_battle"})
    session.execute({"kind": "interact", "object": "supply_cache"})
    restored = MultiFrontSession.replay(session.recording())
    assert restored.digest() == session.digest()
    print("Activated objectives:", sorted(session.applied_links))
    print("Blocked enemy reinforcements:", sorted(session.blocked_reinforcements))
    print("Strategic turn:", session.timeline.turn)
    print("Deterministic replay: OK")
