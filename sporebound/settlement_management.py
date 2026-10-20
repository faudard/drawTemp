"""R61.A — opt-in settlement management over the canonical R55 economy.

The GameProject settlement extension authors zones, buildings, residents and
needs. The R55 SystemEconomy remains the *only* owner of resource stocks, tick
and operation journal; no second clock, market or inventory is introduced.
"""
from __future__ import annotations

from copy import deepcopy
from .model import require
from .system_design import _id, _integer, MAX_STOCK

EXTENSION = "org.drawtemp.settlement"
VERSION = 1


def validate_settlement(spec, system_spec, scenes):
    """Validate a bounded, typed settlement against one R55 resource graph."""
    require(type(spec) is dict and set(spec) ==
            {"version", "zones", "buildings", "residents", "needs"},
            "Malformed R61 settlement")
    require(type(spec["version"]) is int and spec["version"] == VERSION,
            "Unsupported R61 settlement version; explicit migration required")
    require(type(spec["zones"]) is list and 1 <= len(spec["zones"]) <= 32
            and type(spec["buildings"]) is list and len(spec["buildings"]) <= 32
            and type(spec["residents"]) is list and len(spec["residents"]) <= 256
            and type(spec["needs"]) is list and len(spec["needs"]) <= 32,
            "R61 authored budgets exceeded")
    resources = {r["id"] for r in system_spec["resources"]}
    producers = {p["id"] for p in system_spec["producers"]}
    zones = {}
    for zone in spec["zones"]:
        require(type(zone) is dict and set(zone) ==
                {"id", "scene", "capacity"}
                and _id(zone["id"]) and zone["id"] not in zones
                and type(zone["scene"]) is str and zone["scene"] in scenes
                and _integer(zone["capacity"], 1, 32),
                "Invalid or duplicate R61 build zone")
        zones[zone["id"]] = zone
    seen, referenced, occupied = set(), set(), {k: 0 for k in zones}
    for building in spec["buildings"]:
        require(type(building) is dict and set(building) ==
                {"id", "zone", "producer", "workers", "cost", "built"}
                and _id(building["id"]) and building["id"] not in seen
                and building["zone"] in zones
                and _id(building["producer"])
                and building["producer"] in producers
                and building["producer"] not in referenced
                and _integer(building["workers"], 1, 16)
                and type(building["built"]) is bool
                and type(building["cost"]) is dict
                and len(building["cost"]) <= 16,
                "Invalid R61 building, producer or workforce")
        for key, quantity in building["cost"].items():
            require(_id(key) and key in resources and _integer(quantity, 1, 1000),
                    "Invalid R61 construction resource")
        seen.add(building["id"])
        referenced.add(building["producer"])
        if building["built"]:
            occupied[building["zone"]] += 1
    # A producer may not continue to work in the background without a building.
    require(referenced == producers,
            "R61 must bind every R55 producer to exactly one building")
    require(all(occupied[k] <= zone["capacity"] for k, zone in zones.items()),
            "Initial R61 zone occupancy exceeds capacity")
    residents = set()
    for resident in spec["residents"]:
        require(type(resident) is dict and set(resident) == {"id"}
                and _id(resident["id"]) and resident["id"] not in residents,
                "Invalid or repeated R61 resident")
        residents.add(resident["id"])
    needs = set()
    for need in spec["needs"]:
        require(type(need) is dict and set(need) ==
                {"resource", "quantity", "interval"}
                and need["resource"] in resources
                and need["resource"] not in needs
                and _integer(need["quantity"], 1, 1000)
                and _integer(need["interval"], 1, 256),
                "Invalid R61 consumption need")
        needs.add(need["resource"])
    return deepcopy(spec)


class Settlement:
    """Building and workforce state, attached to an R55 SystemEconomy.

    All stock mutations use economy.stocks; the economy owns journal replay,
    including building costs, employment commands and automatic consumption.
    """

    def __init__(self, spec, economy, scenes):
        self.spec = validate_settlement(spec, economy.spec, scenes)
        self.economy = economy
        self.buildings = {r["id"]: r for r in self.spec["buildings"]}
        self.producer_building = {
            r["producer"]: r["id"] for r in self.spec["buildings"]}
        self.zones = {r["id"]: r for r in self.spec["zones"]}
        self.residents = {r["id"] for r in self.spec["residents"]}
        self.built = {r["id"] for r in self.spec["buildings"] if r["built"]}
        self.assignments = {}
        self.shortages = {r["resource"]: 0 for r in self.spec["needs"]}

    def can_produce(self, producer_id):
        building_id = self.producer_building[producer_id]
        building = self.buildings[building_id]
        return (building_id in self.built
                and sum(assigned == building_id
                        for assigned in self.assignments.values()) >= building["workers"])

    def build(self, building_id):
        require(_id(building_id) and building_id in self.buildings,
                "Unknown R61 building")
        building = self.buildings[building_id]
        require(building_id not in self.built, "R61 building already constructed")
        zone_id = building["zone"]
        occupancy = sum(self.buildings[key]["zone"] == zone_id for key in self.built)
        require(occupancy < self.zones[zone_id]["capacity"],
                "R61 build zone saturated")
        require(all(self.economy.stocks[key] >= qty
                    for key, qty in building["cost"].items()),
                "Insufficient R61 construction materials")
        for key, qty in building["cost"].items():
            self.economy.stocks[key] -= qty
        self.built.add(building_id)

    def assign(self, resident_id, building_id):
        require(_id(resident_id) and resident_id in self.residents,
                "Unknown R61 resident")
        require(building_id is None or (
            _id(building_id) and building_id in self.built),
            "R61 job requires a constructed building")
        if self.assignments.get(resident_id) == building_id:
            return False
        if building_id is not None:
            limit = self.buildings[building_id]["workers"]
            staffed = sum(job == building_id for job in self.assignments.values())
            require(staffed < limit, "R61 building workforce is full")
            self.assignments[resident_id] = building_id
        else:
            self.assignments.pop(resident_id, None)
        return True

    def consume(self, tick):
        """Deterministic post-production household consumption, including shortages."""
        for need in sorted(self.spec["needs"], key=lambda row: row["resource"]):
            if tick % need["interval"]:
                continue
            key, quantity = need["resource"], need["quantity"]
            if self.economy.stocks[key] >= quantity:
                self.economy.stocks[key] -= quantity
                self.shortages[key] = 0
            else:
                self.shortages[key] += 1

    def snapshot(self):
        return {"version": VERSION, "built": sorted(self.built),
                "assignments": dict(sorted(self.assignments.items())),
                "shortages": dict(sorted(self.shortages.items()))}


__all__ = ["EXTENSION", "Settlement", "validate_settlement"]
