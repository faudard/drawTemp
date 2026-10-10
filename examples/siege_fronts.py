"""Causal castle fronts: use the same MultiFrontSession for play, AI and replay.

    python -m examples.siege_fronts

The example prints the front rules and a verified save/replay smoke run.
Use `session.execute(...)` for every tactical command if saving a session.
"""
from copy import deepcopy
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


SIEGE_CAMPAIGN = {
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


SIEGE_CAMPAIGN_PATHS = deepcopy(SIEGE_CAMPAIGN)
SIEGE_CAMPAIGN_PATHS["routes"] = {
    "breach": {
        "required": {"gate": ["victory", "negotiated", "reclaimed"],
                     "courtyard": ["victory", "partial"]},
        "supplies": 0, "strength_loss": 0,
    },
    "tunnels": {
        "required": {"tunnels": ["victory"]},
        "supplies": 1, "strength_loss": 2,
    },
    "direct": {
        "required": {},
        "supplies": 3, "strength_loss": 4,
    },
}
SIEGE_CAMPAIGN_PATHS["recovery"] = {
    "gate": {"mission": "castle_gate_recovery", "supplies": 1,
             "strength_loss": 1, "reclaimed_strength": 2},
}
SIEGE_CAMPAIGN_PATHS["treaties"] = {
    "gate": {"requires_front": "supplies", "event": "interact",
             "object": "supply_cache"},
}
SIEGE_CAMPAIGN_PATHS["counteroffensives"] = {
    "gate": {"after_turn": 5, "mission": "castle_gate_recovery",
             "strength_loss": 2, "opposition_gain": 3},
}


def siege_session(seed=1, focused="supplies", *, contested=False, decisions=False,
                  campaign=False, paths=False):
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
    if paths and not campaign:
        raise ValueError("Alternative routes need campaign mode")
    if campaign and not contested:
        raise ValueError("Siege campaign choices need contested supplies")
    return MultiFrontSession(
        siege_content(),
        {"walls": "castle_ramparts", "gate": "castle_ram",
         "courtyard": "castle_courtyard", "supplies": "castle_supply",
         "throne": "castle_throne",
         **({"tunnels": "castle_tunnels"} if paths else {})},
        focused=focused, seed=seed,
        specs={
            "walls": {"strength": 8, "opposition": 12, "doctrine": "assault"},
            "gate": {"strength": 10, "opposition": 14, "doctrine": "hold"},
            "courtyard": {"strength": 9, "opposition": 16, "doctrine": "delay"},
            "supplies": {"strength": 6, "opposition": 10, "doctrine": "hold"},
            "throne": {"strength": 7, "opposition": 18, "doctrine": "hold"},
            **({"tunnels": {"strength": 6, "opposition": 8,
                            "doctrine": "hold"}} if paths else {}),
        },
        links=SIEGE_LINKS,
        logistics=logistics,
        campaign=(SIEGE_CAMPAIGN_PATHS if paths else
                  SIEGE_CAMPAIGN if campaign else None),
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
