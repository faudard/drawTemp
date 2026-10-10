"""Optional historical-fantasy roster for Jeanne's campaign (Content v1).

Catalog metadata is kept OUTSIDE the combat schema. Importing a pack adds
ordinary skills, archetypes, jobs and equipment; missions and legacy saves
are unchanged. Every placed unit is a snapshot of its template.
"""
from copy import deepcopy

from .actor_catalog import place_archetype
from .model import Content, require


def _skill(name, power, *, kind="damage", cost=0, range=1, target="enemy",
           min_range=0, status="", duration=24, extra_effect=None):
    effect = {"kind": kind, "power": power}
    if status:
        effect.update(status=status, duration=duration)
    effects = [effect]
    if extra_effect is not None:
        effects.append(deepcopy(extra_effect))
    return {"name": name, "effects": effects, "cost": cost, "range": range,
            "min_range": min_range, "target": target}


SKILLS = {
    "bite": _skill("Morsure", 6),
    "pack_howl": _skill("Hurlement de meute", 1, kind="status", status="haste",
                        target="self", range=0, cost=2),
    "charge": _skill("Charge", 8, extra_effect={"kind": "push", "power": 1}),
    "shield": _skill("Garde levée", 1, kind="status", status="guard",
                     target="self", range=0, cost=2),
    "thrust": _skill("Estoc", 8, range=2, cost=2),
    "aim": _skill("Tir visé", 9, range=5, min_range=2, cost=2),
    "bandage": _skill("Bandage de campagne", 16, kind="heal",
                      target="ally", range=2, cost=3),
    "rally": _skill("Ralliement", 1, kind="status", status="protect",
                    target="ally", range=2, cost=3),
    "sunder": _skill("Brise-garde", 11, cost=3),
    "hamstring": _skill("Entaille entravante", 6, cost=2,
                        extra_effect={"kind": "status", "power": 1,
                                      "status": "slow", "duration": 18}),
}


def _actor(kind, hp, attack, defense, speed, move, weapon="melee", *,
           skills=(), tags=(), reaction="none", weapon_power=3,
           attack_range=1, footprint=(1, 1), magic=2, max_mp=12):
    return {"kind": kind, "max_hp": hp, "max_mp": max_mp, "attack": attack,
            "magic": magic, "defense": defense, "speed": speed, "move": move,
            "weapon": weapon, "weapon_power": weapon_power,
            "attack_range": attack_range, "skills": list(skills),
            "tags": list(tags), "reaction": reaction,
            "footprint": list(footprint)}


def _entry(name, family, role, tier, description, actor):
    return {"name": name, "family": family, "role": role, "tier": tier,
            "description": description, "actor": actor}


# All identifiers are namespaced to avoid collisions with legacy content.
BESTIARY = {
    "wolf": _entry("Loup", "Faune", "Prédateur mobile", 1,
        "Rapide et fragile; dangereux en groupe.",
        _actor("monster", 27, 6, 1, 13, 5, "unarmed",
               skills=("bite",), tags=("beast", "wolf"))),
    "alpha_wolf": _entry("Loup alpha", "Faune", "Chef de meute", 2,
        "Accélère ses alliés et poursuit les isolés.",
        _actor("monster", 49, 9, 3, 14, 5, "unarmed",
               skills=("bite", "pack_howl"), tags=("beast", "wolf", "leader"),
               reaction="pursuit")),
    "war_hound": _entry("Chien de guerre", "Faune", "Interception", 1,
        "Animal dressé pour intercepter les fuyards.",
        _actor("monster", 34, 7, 2, 12, 5, "unarmed",
               skills=("bite", "hamstring"), tags=("beast", "warhound"),
               reaction="opportunity")),
    "boar": _entry("Sanglier", "Faune", "Charge brutale", 2,
        "Percute et repousse le premier combattant exposé.",
        _actor("monster", 61, 10, 3, 9, 4, "unarmed",
               skills=("charge",), tags=("beast", "boar"))),
    "bandit": _entry("Bandit", "Brigands", "Mêlée légère", 1,
        "Adversaire peu protégé mais offensif.",
        _actor("character", 40, 7, 1, 11, 4,
               skills=("hamstring",), tags=("bandit",))),
    "bandit_archer": _entry("Archer bandit", "Brigands", "Tir à distance", 1,
        "Menace les soigneurs depuis l'arrière.",
        _actor("character", 31, 6, 1, 11, 4, "ranged",
               skills=("aim",), tags=("bandit", "ranged"),
               attack_range=4, weapon_power=3)),
    "raider": _entry("Pillard", "Brigands", "Assaut", 2,
        "Combattant agressif avec une attaque de rupture.",
        _actor("character", 52, 9, 2, 11, 5,
               skills=("charge",), tags=("bandit", "raider"))),
    "bandit_captain": _entry("Chef bandit", "Brigands", "Commandement", 3,
        "Protège ses troupes et consolide une ligne de combat.",
        _actor("character", 80, 11, 5, 11, 4,
               skills=("shield", "rally", "sunder"), tags=("bandit", "leader"),
               reaction="counter")),
    "militia": _entry("Milicien", "Soldats", "Défense de village", 1,
        "Milice locale équipée sommairement.",
        _actor("character", 45, 6, 3, 9, 4,
               skills=("shield",), tags=("militia",))),
    "squire": _entry("Écuyer", "Soldats", "Apprenti polyvalent", 1,
        "Apprend à tenir une ligne et à manier l'épée.",
        _actor("character", 47, 7, 3, 10, 4,
               skills=("shield",), tags=("squire",))),
    "swordsman": _entry("Épéiste", "Soldats", "Duel", 2,
        "Contre les assauts au corps à corps.",
        _actor("character", 62, 10, 4, 12, 4,
               skills=("thrust", "sunder"), tags=("swordsman",),
               reaction="counter", weapon_power=5)),
    "spearman": _entry("Lancier", "Soldats", "Contrôle de zone", 2,
        "Maintient les adversaires à deux cases.",
        _actor("character", 58, 9, 4, 10, 4, "spear",
               skills=("thrust",), tags=("spearman",),
               attack_range=2, reaction="opportunity")),
    "crossbowman": _entry("Arbalétrier", "Soldats", "Tireur lourd", 2,
        "Tir puissant, faible résistance en mêlée.",
        _actor("character", 44, 9, 2, 8, 3, "ranged",
               skills=("aim",), tags=("crossbowman", "ranged"),
               attack_range=5, weapon_power=6)),
    "healer": _entry("Soigneur", "Soldats", "Soutien", 2,
        "Soigne et soutient la première ligne.",
        _actor("character", 39, 4, 2, 10, 4, "focus",
               skills=("bandage", "rally"), tags=("healer",),
               magic=7, max_mp=22)),
    "knight": _entry("Chevalier", "Soldats", "Défenseur d'élite", 3,
        "Défenseur endurant et maître de la contre-attaque.",
        _actor("character", 92, 12, 8, 9, 4,
               skills=("shield", "charge", "rally"),
               tags=("knight", "protector"), reaction="counter",
               weapon_power=6)),
    "commander": _entry("Capitaine d'armes", "Soldats", "Chef tactique", 3,
        "Encadre les soldats et renforce leurs défenses.",
        _actor("character", 76, 10, 6, 11, 4,
               skills=("rally", "thrust"), tags=("leader",),
               reaction="counter")),
    "siege_troll": _entry("Troll de siège", "Créatures de siège", "Briseur de porte", 4,
        "Géant de deux cases de côté; puissant, mais lent.",
        _actor("monster", 210, 18, 7, 6, 2, "unarmed",
               skills=("charge", "sunder"), tags=("siege", "giant"),
               footprint=(2, 2), weapon_power=8)),
}


def _job(name, *, requires="", requires_level=1, bonuses=None, skills=None,
         talents=None):
    return {"name": name, "requires": requires, "requires_level": requires_level,
            "bonuses": bonuses or {}, "skills": skills or {},
            "talents": talents or {}}


def _talent(jp, *, requires=(), exclusive="", bonuses=None, skills=()):
    return {"jp": jp, "requires": list(requires), "exclusive": exclusive,
            "bonuses": bonuses or {}, "skills": list(skills)}


JOBS = {
    "recruit": _job("Recrue", bonuses={"max_hp": 3}),
    "squire": _job("Écuyer", requires="recruit", requires_level=2,
                   bonuses={"defense": 2, "max_hp": 7},
                   skills={"shield": 2},
                   talents={"resolve": _talent(1, bonuses={"max_hp": 6}),
                            "discipline": _talent(2, requires=("resolve",),
                                                  bonuses={"defense": 2})}),
    "swordsman": _job("Épéiste", requires="squire", requires_level=3,
                      bonuses={"attack": 3, "speed": 1},
                      skills={"thrust": 1},
                      talents={"duel": _talent(2, bonuses={"attack": 2},
                                               skills=("sunder",)),
                               "riposte": _talent(2, bonuses={"defense": 2})}),
    "guard": _job("Garde", requires="squire", requires_level=3,
                  bonuses={"defense": 4, "max_hp": 10},
                  skills={"shield": 1},
                  talents={"wall": _talent(2, bonuses={"defense": 3}),
                           "intercept": _talent(2, bonuses={"max_hp": 9},
                                                 skills=("rally",))}),
    "knight": _job("Chevalier", requires="guard", requires_level=3,
                   bonuses={"attack": 3, "defense": 4, "max_hp": 14},
                   skills={"charge": 1, "rally": 3},
                   talents={"banner": _talent(3, bonuses={"defense": 3},
                                              skills=("rally",))}),
    "duelist": _job("Duelliste", requires="swordsman", requires_level=3,
                    bonuses={"attack": 4, "speed": 3},
                    skills={"sunder": 1},
                    talents={"parry": _talent(2, bonuses={"defense": 2}),
                             "execution": _talent(3, bonuses={"attack": 3})}),
    "archer": _job("Archer", requires="recruit", requires_level=2,
                   bonuses={"attack": 2, "speed": 1},
                   skills={"aim": 1}),
    "marksman": _job("Tireur d'élite", requires="archer", requires_level=3,
                     bonuses={"attack": 3, "speed": 2},
                     talents={"eye": _talent(2, bonuses={"attack": 3})}),
    "scout": _job("Éclaireur", requires="recruit", requires_level=2,
                  bonuses={"move": 1, "speed": 2}),
    "ranger": _job("Rôdeur", requires="scout", requires_level=3,
                   bonuses={"move": 1, "attack": 3},
                   skills={"hamstring": 1}),
    "healer": _job("Soigneur", requires="recruit", requires_level=2,
                   bonuses={"max_mp": 8, "magic": 3},
                   skills={"bandage": 1, "rally": 3}),
}


EQUIPMENT = {
    "iron_sword": {"name": "Épée de fer", "slot": "weapon", "price": 70,
                   "bonuses": {"weapon_power": 2}},
    "longsword": {"name": "Épée longue", "slot": "weapon", "price": 120,
                  "bonuses": {"weapon_power": 4, "attack": 2}},
    "spear": {"name": "Lance d'infanterie", "slot": "weapon", "price": 65,
              "bonuses": {"weapon_power": 2, "attack": 1}},
    "bow": {"name": "Arc de chasse", "slot": "weapon", "price": 85,
            "bonuses": {"weapon_power": 3}},
    "chainmail": {"name": "Cotte de mailles", "slot": "armor", "price": 130,
                  "bonuses": {"defense": 3, "max_hp": 8}},
    "plate": {"name": "Armure de plates", "slot": "armor", "price": 260,
              "bonuses": {"defense": 6, "max_hp": 15}},
    "shield": {"name": "Écu de bois", "slot": "accessory", "price": 55,
               "bonuses": {"defense": 2}},
    "field_kit": {"name": "Sac de soins", "slot": "accessory", "price": 50,
                  "bonuses": {"max_mp": 4}},
}


def archetype_id(preset_id):
    require(preset_id in BESTIARY, "Unknown medieval bestiary entry")
    return "med_" + preset_id


def entries(family=None):
    """Stable, presentation-ready index. Returned rows cannot mutate the pack."""
    rows = [
        {"id": identifier, **{key: deepcopy(value) for key, value in entry.items()
                             if key != "actor"}}
        for identifier, entry in BESTIARY.items()
        if family is None or entry["family"] == family
    ]
    return sorted(rows, key=lambda row: (row["tier"], row["family"], row["id"]))


def install_pack(data):
    """Atomic, idempotent opt-in import, rejecting changed ID collisions.

    Existing missions, instances, saves and other archetype families are not
    touched. Author-supplied definitions win only through explicit editing,
    never by a silent re-import.
    """
    new = deepcopy(data)
    require(isinstance(new, dict), "Content must be an object")
    collections = (
        ("skills", [{"id": "med_" + identifier, **deepcopy(spec)}
                    for identifier, spec in SKILLS.items()]),
        ("archetypes", {"med_" + identifier: deepcopy(spec["actor"])
                        for identifier, spec in BESTIARY.items()}),
        ("jobs", {"med_" + identifier: {
            **deepcopy(spec),
            "requires": "med_" + spec["requires"] if spec["requires"] else "",
            "skills": {"med_" + sid: level
                       for sid, level in spec["skills"].items()},
            "talents": {"med_" + tid: {
                **deepcopy(talent),
                "requires": ["med_" + ref for ref in talent["requires"]],
                "skills": ["med_" + sid for sid in talent["skills"]],
            } for tid, talent in spec["talents"].items()},
        } for identifier, spec in JOBS.items()}),
        ("equipment", {"med_" + identifier: deepcopy(spec)
                       for identifier, spec in EQUIPMENT.items()}),
    )
    for collection, values in collections:
        if isinstance(values, list):
            existing = new.setdefault(collection, [])
            known = {item["id"]: item for item in existing}
            for row in values:
                require(row["id"] not in known or known[row["id"]] == row,
                        "Conflicting medieval " + collection + ": " + row["id"])
                if row["id"] not in known:
                    existing.append(row)
        else:
            existing = new.setdefault(collection, {})
            for key, value in values.items():
                require(key not in existing or existing[key] == value,
                        "Conflicting medieval " + collection + ": " + key)
                existing.setdefault(key, value)
    return Content.from_dict(new).to_dict()


RANKS = {
    "normal": (0, 0, 0, 0),
    "veteran": (20, 2, 1, 0),
    "elite": (45, 4, 3, 1),
}


def place_entry(data, mission_id, preset_id, unit_id, team, pos, *,
                rank="normal", name=None):
    """Place an authored, rank-adjusted unit via the usual collision validator."""
    require(rank in RANKS, "Unknown rank")
    require(preset_id in BESTIARY, "Unknown medieval bestiary entry")
    label = name if name is not None else BESTIARY[preset_id]["name"]
    require(isinstance(label, str) and bool(label.strip()), "Actor needs a name")
    content = place_archetype(data, mission_id, archetype_id(preset_id),
                              unit_id, label.strip(), team, pos)
    pct, attack, defense, speed = RANKS[rank]
    # place_archetype resolves the template into full, immutable spawn fields.
    mission = next(row for row in content["missions"] if row["id"] == mission_id)
    unit = next(row for row in mission["units"] if row["id"] == unit_id)
    unit["max_hp"] += unit["max_hp"] * pct // 100
    unit["hp"] = unit["max_hp"]
    unit["attack"] += attack
    unit["defense"] += defense
    unit["speed"] += speed
    if rank != "normal":
        unit["tags"].append("rank:" + rank)
    return Content.from_dict(content).to_dict()
