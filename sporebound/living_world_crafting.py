"""R45.A — opt-in, bounded crafting with R35 time and R8 inventory.

Recipe configuration lives only in the GameProject living-world extension.
Player-owned items and gold live only in Campaign. Execution is a single
preflight followed by an atomic commit; no wall-clock jobs or CT mutations.
"""
from __future__ import annotations

from .model import require
from .living_world_commerce import _id

MAX_CRAFTS = 2048
MAX_PORTABLE = 2 ** 53 - 1


def validate_recipes(spec, scenes, *, item_ids=None):
    recipes = spec.get("recipes", [])
    require(type(recipes) is list and len(recipes) <= 128,
            "Invalid R45 recipe catalogue")
    npcs = {row["id"]: row for row in spec["npcs"]}
    factions = {row["id"] for row in spec.get("factions", [])}
    known_items = set(item_ids or ())
    for shop in spec.get("shops", []):
        known_items.update(row["id"] for row in shop["items"])
    seen = set()
    for recipe in recipes:
        require(type(recipe) is dict and set(recipe) == {
            "id", "npc", "scene", "activity", "faction", "min_reputation",
            "inputs", "outputs", "gold_cost", "daily_limit"},
            "Invalid R45 recipe fields")
        rid = recipe["id"]
        require(_id(rid) and rid not in seen, "Invalid or duplicate recipe ID")
        seen.add(rid)
        require(_id(recipe["npc"]) and recipe["npc"] in npcs
                and type(recipe["scene"]) is str and recipe["scene"] in scenes
                and _id(recipe["activity"])
                and _id(recipe["faction"]) and recipe["faction"] in factions
                and type(recipe["min_reputation"]) is int
                and -100 <= recipe["min_reputation"] <= 100,
                "Unknown R45 NPC, scene, activity or faction")
        require(any(stop["scene"] == recipe["scene"]
                    and stop["activity"] == recipe["activity"]
                    for stop in npcs[recipe["npc"]]["schedule"]),
                "Recipe requires an authored NPC schedule")
        require(type(recipe["gold_cost"]) is int
                and 0 <= recipe["gold_cost"] <= 1_000_000
                and type(recipe["daily_limit"]) is int
                and 1 <= recipe["daily_limit"] <= 1000,
                "Invalid R45 cost or daily production limit")
        item_sets = []
        for key in ("inputs", "outputs"):
            rows = recipe[key]
            require(type(rows) is list and 1 <= len(rows) <= 8,
                    "Recipe requires 1..8 input and output types")
            ids = set()
            for row in rows:
                require(type(row) is dict and set(row) == {"item", "quantity"}
                        and _id(row["item"]) and row["item"] in known_items
                        and row["item"] not in ids
                        and type(row["quantity"]) is int
                        and 1 <= row["quantity"] <= 99,
                        "Invalid recipe item reference or quantity")
                ids.add(row["item"])
            item_sets.append(ids)
        require(not (item_sets[0] & item_sets[1]),
                "Cannot consume and produce the same item in one recipe")


def _recipe(world, recipe_id):
    require(_id(recipe_id), "Invalid recipe ID")
    recipe = next((row for row in world.spec.get("recipes", [])
                   if row["id"] == recipe_id), None)
    require(recipe is not None, "Unknown crafting recipe")
    return recipe


def produced_today(world, recipe_id, *, day=None):
    target = world.day if day is None else day
    return sum(row["quantity"] for row in world.crafts.values()
               if row["recipe"] == recipe_id and row["day"] == target)


def validate_crafts(world, crafts, day):
    """Reject reordered, duplicated, over-budget and future-dated receipts."""
    require(type(crafts) is dict and len(crafts) <= MAX_CRAFTS,
            "Invalid crafting receipt ledger")
    rows = []
    for receipt_id, receipt in crafts.items():
        require(_id(receipt_id) and type(receipt) is dict
                and set(receipt) == {"recipe", "quantity", "day", "sequence"},
                "Malformed crafting receipt")
        require(type(receipt["sequence"]) is int
                and 0 <= receipt["sequence"] < len(crafts),
                "Invalid crafting receipt sequence")
        rows.append(receipt)
    require({r["sequence"] for r in rows} == set(range(len(crafts))),
            "Duplicate or missing crafting sequences")
    usage = {}
    prior = -1
    for receipt in sorted(rows, key=lambda row: row["sequence"]):
        recipe = _recipe(world, receipt["recipe"])
        require(type(receipt["day"]) is int
                and prior <= receipt["day"] <= day
                and type(receipt["quantity"]) is int
                and 1 <= receipt["quantity"] <= 99,
                "Invalid chronological crafting receipt")
        prior = receipt["day"]
        key = (receipt["day"], recipe["id"])
        usage[key] = usage.get(key, 0) + receipt["quantity"]
        require(usage[key] <= recipe["daily_limit"],
                "Crafting receipts exceed daily limit")


def catalogue(world, flags, scene=None):
    result = []
    for recipe in world.spec.get("recipes", []):
        if scene is not None and recipe["scene"] != scene:
            continue
        npc_scene, activity = world.npc_status(recipe["npc"], flags)
        opened = (npc_scene == recipe["scene"]
                  and activity == recipe["activity"]
                  and world.reputation[recipe["faction"]]
                  >= recipe["min_reputation"])
        result.append({
            "id": recipe["id"], "npc": recipe["npc"],
            "scene": recipe["scene"], "available": opened,
            "remaining_today": recipe["daily_limit"]
                               - produced_today(world, recipe["id"]),
            "gold_cost": recipe["gold_cost"],
            "inputs": [dict(row) for row in recipe["inputs"]],
            "outputs": [dict(row) for row in recipe["outputs"]]})
    return result


def craft(world, progress, flags, active_scene, recipe_id, quantity,
          transaction_id):
    """Apply a recipe to canonical Campaign state at most once per receipt."""
    require(_id(transaction_id) and type(quantity) is int
            and 1 <= quantity <= 99, "Invalid crafting command")
    recipe = _recipe(world, recipe_id)
    previous = world.crafts.get(transaction_id)
    if previous is not None:
        require(previous["recipe"] == recipe_id
                and previous["quantity"] == quantity,
                "Craft receipt ID reused with a different command")
        return False
    require(len(world.crafts) < MAX_CRAFTS, "Craft ledger capacity reached")
    npc_scene, activity = world.npc_status(recipe["npc"], flags)
    require(active_scene == recipe["scene"] == npc_scene
            and activity == recipe["activity"],
            "Crafting NPC is closed or off-scene")
    require(world.reputation[recipe["faction"]] >= recipe["min_reputation"],
            "Faction reputation does not permit crafting")
    require(produced_today(world, recipe_id) + quantity
            <= recipe["daily_limit"], "Daily crafting limit exceeded")
    require(type(progress.gold) is int
            and 0 <= progress.gold <= MAX_PORTABLE
            and progress.gold >= recipe["gold_cost"] * quantity,
            "Insufficient or invalid campaign currency")
    changes = {}
    for row in recipe["inputs"]:
        item, amount = row["item"], row["quantity"] * quantity
        value = progress.inventory.get(item, 0)
        require(type(value) is int and 0 <= value <= MAX_PORTABLE
                and value >= amount, "Insufficient or invalid recipe materials")
        changes[item] = value - amount
    for row in recipe["outputs"]:
        item, amount = row["item"], row["quantity"] * quantity
        value = progress.inventory.get(item, 0)
        require(type(value) is int and 0 <= value <= MAX_PORTABLE
                and value + amount <= MAX_PORTABLE,
                "Craft output exceeds portable inventory range")
        changes[item] = value + amount
    # Commit only after all preconditions; neither the recipe nor CT changes.
    progress.inventory.update(changes)
    progress.gold -= recipe["gold_cost"] * quantity
    world.crafts[transaction_id] = {
        "recipe": recipe_id, "quantity": quantity, "day": world.day,
        "sequence": len(world.crafts)}
    return True
