"""Pure, validated authoring actions for Character & Bestiary Studio 4.0."""
from copy import deepcopy

from .actor_catalog import place_archetype, remove_archetype
from .authoring import _identifier
from .model import Content, require
from .tactical_rpg3 import authored_rules_for_document

DOCTRINE_OPTIONS = ("", "pack_hunt", "bandit_ambush",
                    "spear_hold", "crossbow_reload")


def _checked(data):
    return Content.from_dict(data, rules=authored_rules_for_document(data)).to_dict()


def create_variant(data, source_id, new_id, *, kind="character", doctrine=""):
    _identifier(new_id, "Archetype id")
    require(kind in {"character", "monster"}, "Invalid variant type")
    require(doctrine in DOCTRINE_OPTIONS, "Unsupported doctrine")
    new = deepcopy(data)
    library = new.setdefault("archetypes", {})
    require(source_id in library, "Source archetype missing")
    require(new_id not in library, "Archetype already exists")
    variant = deepcopy(library[source_id])
    variant["kind"] = kind
    variant["tags"] = [tag for tag in variant.get("tags", [])
                       if not tag.startswith("doctrine:")]
    if doctrine:
        variant["tags"].append("doctrine:" + doctrine)
    library[new_id] = variant
    return _checked(new)


def edit_doctrine(data, archetype_id, doctrine):
    require(doctrine in DOCTRINE_OPTIONS, "Unsupported doctrine")
    new = deepcopy(data)
    require(archetype_id in new.get("archetypes", {}), "Unknown archetype")
    tags = new["archetypes"][archetype_id].get("tags", [])
    tags = [tag for tag in tags if not tag.startswith("doctrine:")]
    if doctrine:
        tags.append("doctrine:" + doctrine)
    new["archetypes"][archetype_id]["tags"] = tags
    return _checked(new)


def place_variant(data, mission_id, archetype_id, unit_id, name, team, pos):
    return _checked(place_archetype(data, mission_id, archetype_id,
                                     unit_id, name, team, pos))


def delete_variant(data, archetype_id):
    return _checked(remove_archetype(data, archetype_id))
