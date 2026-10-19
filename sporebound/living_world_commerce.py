"""R35.B2: bounded shop catalogue, deterministic stock and atomic buy/sell."""
from .model import require

MAX_TRADES = 2048


def _id(value):
    return (type(value) is str and 1 <= len(value) <= 64
            and all(c.isascii() and (c.isalnum() or c in "_-") for c in value))


def validate_shops(spec, scenes):
    shops = spec.get("shops", [])
    require(type(shops) is list and len(shops) <= 32,
            "Invalid shop catalogue")
    npcs = {npc["id"]: npc for npc in spec["npcs"]}
    factions = {f["id"] for f in spec.get("factions", [])}
    seen = set()
    for shop in shops:
        require(type(shop) is dict and set(shop) ==
                {"id", "npc", "scene", "activity", "faction",
                 "min_reputation", "items"}, "Invalid shop fields")
        require(_id(shop["id"]) and shop["id"] not in seen
                and shop["npc"] in npcs and shop["scene"] in scenes
                and _id(shop["activity"]) and shop["faction"] in factions
                and type(shop["min_reputation"]) is int
                and -100 <= shop["min_reputation"] <= 100,
                "Invalid shop ID, NPC, scene or faction")
        seen.add(shop["id"])
        require(any(s["scene"] == shop["scene"]
                    and s["activity"] == shop["activity"]
                    for s in npcs[shop["npc"]]["schedule"]),
                "Shop NPC has no trading schedule at this scene")
        items = shop["items"]
        require(type(items) is list and 1 <= len(items) <= 32,
                "Shop needs 1..32 items")
        keys = set()
        for item in items:
            require(type(item) is dict and set(item) ==
                    {"id", "buy_price", "sell_price", "daily_stock"}
                    and _id(item["id"]) and item["id"] not in keys
                    and type(item["buy_price"]) is int
                    and type(item["sell_price"]) is int
                    and 0 <= item["sell_price"] <= item["buy_price"] <= 1000000
                    and type(item["daily_stock"]) is int
                    and 1 <= item["daily_stock"] <= 1000,
                    "Invalid shop stock or price")
            keys.add(item["id"])


def _find(world, shop_id, item_id=None):
    require(_id(shop_id), "Invalid shop ID")
    shop = next((s for s in world.spec.get("shops", [])
                 if s["id"] == shop_id), None)
    require(shop is not None, "Unknown shop")
    if item_id is None:
        return shop, None
    require(_id(item_id), "Invalid shop item ID")
    item = next((x for x in shop["items"] if x["id"] == item_id), None)
    require(item is not None, "Unknown shop item")
    return shop, item


def stock(world, shop_id, item_id, day=None, receipts=None):
    shop, item = _find(world, shop_id, item_id)
    target = world.day if day is None else day
    ledger = world.trades.values() if receipts is None else receipts
    balance = item["daily_stock"]
    for entry in ledger:
        if (entry["day"] == target and entry["shop"] == shop_id
                and entry["item"] == item_id):
            balance += entry["quantity"] * (
                1 if entry["action"] == "sell" else -1)
    return balance


def listing(world, flags, scene=None):
    result = []
    for shop in world.spec.get("shops", []):
        if scene is not None and shop["scene"] != scene:
            continue
        npc_scene, action = world.npc_status(shop["npc"], flags)
        opened = (npc_scene == shop["scene"] and action == shop["activity"]
                  and world.reputation[shop["faction"]] >= shop["min_reputation"])
        result.append({
            "id": shop["id"], "npc": shop["npc"], "scene": shop["scene"],
            "open": opened, "items": [
                {"id": x["id"], "buy_price": x["buy_price"],
                 "sell_price": x["sell_price"],
                 "stock": stock(world, shop["id"], x["id"])}
                for x in shop["items"]]})
    return result


def validate_trades(world, trades, day):
    require(type(trades) is dict and len(trades) <= MAX_TRADES,
            "Invalid trade ledger")
    sequenced = []
    for tid, row in trades.items():
        require(_id(tid) and type(row) is dict and set(row) ==
                {"shop", "item", "action", "quantity", "day", "unit_price",
                 "total", "sequence"}, "Malformed trade record")
        require(type(row["sequence"]) is int and 0 <= row["sequence"] < len(trades),
                "Invalid trade sequence")
        sequenced.append(row)
    require({r["sequence"] for r in sequenced} == set(range(len(trades))),
            "Duplicate or missing trade sequences")
    # JSON object key order is NOT a simulation ordering contract.
    balances = {}
    prior_day = -1
    for row in sorted(sequenced, key=lambda entry: entry["sequence"]):
        shop, item = _find(world, row["shop"], row["item"])
        require(row["action"] in ("buy", "sell")
                and type(row["quantity"]) is int
                and 1 <= row["quantity"] <= 99
                and type(row["day"]) is int
                and prior_day <= row["day"] <= day,
                "Invalid chronological trade")
        prior_day = row["day"]
        price = item["buy_price"] if row["action"] == "buy" else item["sell_price"]
        require(type(row["unit_price"]) is int
                and row["unit_price"] == price
                and type(row["total"]) is int
                and row["total"] == price * row["quantity"],
                "Trade prices do not match authored shop")
        key = (row["day"], shop["id"], item["id"])
        balances[key] = (balances.get(key, item["daily_stock"])
                         + row["quantity"] * (
                             1 if row["action"] == "sell" else -1))
        require(0 <= balances[key] <= item["daily_stock"],
                "Trade history exceeds daily stock")


def transact(world, progress, flags, active_scene, shop_id, item_id,
             action, quantity, transaction_id):
    require(_id(transaction_id) and action in ("buy", "sell")
            and type(quantity) is int and 1 <= quantity <= 99,
            "Invalid trade request")
    shop, item = _find(world, shop_id, item_id)
    previous = world.trades.get(transaction_id)
    if previous is not None:
        require((previous["shop"], previous["item"], previous["action"],
                 previous["quantity"]) == (shop_id, item_id, action, quantity),
                "Reused trade ID with different command")
        return False
    require(len(world.trades) < MAX_TRADES, "Trade ledger capacity reached")
    npc_scene, activity = world.npc_status(shop["npc"], flags)
    require(active_scene == shop["scene"] == npc_scene
            and activity == shop["activity"], "Shop is closed or off-scene")
    require(world.reputation[shop["faction"]] >= shop["min_reputation"],
            "Faction reputation does not permit this trade")
    remaining = stock(world, shop_id, item_id)
    available = progress.inventory.get(item_id, 0)
    require(type(available) is int and 0 <= available <= 2**53-1
            and type(progress.gold) is int
            and 0 <= progress.gold <= 2**53-1,
            "Invalid campaign currency or inventory")
    price = item["buy_price"] if action == "buy" else item["sell_price"]
    total = quantity * price
    if action == "buy":
        require(remaining >= quantity and progress.gold >= total
                and available + quantity <= 2**53-1,
                "Insufficient gold, stock or inventory capacity")
        new_gold, new_count = progress.gold - total, available + quantity
    else:
        require(available >= quantity
                and remaining + quantity <= item["daily_stock"]
                and progress.gold + total <= 2**53-1,
                "Insufficient items or merchant capacity")
        new_gold, new_count = progress.gold + total, available - quantity
    progress.gold = new_gold
    progress.inventory[item_id] = new_count
    world.trades[transaction_id] = {
        "shop": shop_id, "item": item_id, "action": action,
        "quantity": quantity, "day": world.day,
        "unit_price": price, "total": total,
        "sequence": len(world.trades)}
    return True
