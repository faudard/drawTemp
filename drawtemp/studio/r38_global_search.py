"""R38.1 — revision-scoped global discovery of canonical authoring resources.

Read-only projection of AuthoringSession.snapshot(): no shadow manifest, filesystem
walk, implicit migrations, Qt dependency or mutation of Content/GameProject.
Only known typed references count as usages; arbitrary matching strings do not.
"""
from __future__ import annotations

from dataclasses import dataclass
from unicodedata import normalize

from .resource_links import reference_edges
from .workspace_model import resources


def _fold(value: object) -> str:
    value = normalize("NFKD", str(value)).casefold()
    return "".join(char for char in value if not 0x300 <= ord(char) <= 0x36F)


@dataclass(frozen=True)
class SearchEntry:
    family: str
    mission_id: str
    resource_id: str
    title: str
    details: str
    path: str
    navigate: tuple[str, str, str] | None = None

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.family, self.mission_id, self.resource_id)


@dataclass(frozen=True)
class SearchUsage:
    source: tuple[str, str, str]
    target: tuple[str, str, str]
    field: str
    path: str


class GlobalSearchIndex:
    """Immutable-to-callers index, rebuilt for one specific authoring revision.

    All keys retain family and mission scope. A mission-local object named
    "gate" is not confused with a similarly named object on another map.
    """

    def __init__(self, snapshot):
        raw = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        content, project = raw["content"], raw["project"]
        self.revision = raw.get("revision")
        items: dict[tuple[str, str, str], SearchEntry] = {}
        edges: set[SearchUsage] = set()

        def add(entry: SearchEntry):
            if entry.key in items:
                raise ValueError("Duplicate search identity: " + repr(entry.key))
            items[entry.key] = entry

        def link(source, target, field: str, path: str):
            if source in items and target in items and source != target:
                edges.add(SearchUsage(source, target, field, path))

        for row in resources(raw):
            key = row.key
            path = (("Content.missions[id=" + row.mission_id + "]") if row.mission_id
                    else ("Content.missions[id=" + row.resource_id + "]")
                    if row.family == "maps" else "GameProject")
            add(SearchEntry(row.family, row.mission_id, row.resource_id,
                            row.title, row.resource_id, path, key))

        # GameProject assets are already validated by the canonical AssetRegistry.
        assets = project.get("assets") or {}
        for asset in assets.get("entries", ()):
            identifier = asset["id"]
            detail = asset.get("path", "animation (%s frames)" %
                               len(asset.get("frames", ())))
            add(SearchEntry("assets", "", identifier, identifier,
                            asset["kind"] + " · " + detail,
                            "GameProject.assets.entries[id=" + identifier + "]"))
        for edge in reference_edges(raw):
            link(edge.source.key, edge.target.key, edge.field, edge.path)

        project_key = ("project", "", "project")
        for kind, bindings in (assets.get("bindings") or {}).items():
            for slot, identifier in bindings.items():
                link(project_key, ("assets", "", identifier), "asset_binding",
                     "GameProject.assets.bindings." + kind + "." + slot)
        for asset in assets.get("entries", ()):
            if asset["kind"] == "animation":
                for i, frame in enumerate(asset.get("frames", ())):
                    link(("assets", "", asset["id"]), ("assets", "", frame["sprite"]),
                         "sprite", "GameProject.assets.entries[id=" +
                         asset["id"] + "].frames[" + str(i) + "].sprite")

        # Graphs live under the existing R31 extension and compile to R9 events;
        # indexing them does not add another graph format or execution pipeline.
        spec = (project.get("extensions") or {}).get("org.drawtemp.logic") or {}
        graph_data = spec.get("data") or {}
        for graph in graph_data.get("graphs", ()):
            mission = graph["mission_id"]
            graph_id = graph["id"]
            parent = ("logic_graphs", mission, graph_id)
            base = ("GameProject.extensions.org.drawtemp.logic.data.graphs[id=" +
                    graph_id + "]")
            add(SearchEntry("logic_graphs", mission, graph_id, graph_id,
                            "Graphe logique · " + mission, base))
            link(parent, ("maps", "", mission), "mission_id", base + ".mission_id")
            for node in graph.get("nodes", ()):
                identifier = graph_id + "/" + node["id"]
                node_key = ("graph_nodes", mission, identifier)
                params = node.get("params") or {}
                add(SearchEntry("graph_nodes", mission, identifier,
                                node["id"], node["kind"] + " · " + graph_id +
                                " · " + str(params.get("kind", "")),
                                base + ".nodes[id=" + node["id"] + "]"))
                link(parent, node_key, "node", base + ".nodes")
                for field, family in (("object_id", "objects"), ("unit", "actors")):
                    target = params.get(field)
                    if isinstance(target, str):
                        link(node_key, (family, mission, target),
                             field, base + ".nodes[id=" + node["id"] +
                             "].params." + field)

        # R35 daily quests and factions live in the existing living-world
        # extension. Their IDs remain separate from R31 graph and R2 map IDs.
        living = (project.get("extensions") or {}).get("org.drawtemp.livingworld") or {}
        living_data = living.get("data") or {}
        living_base = "GameProject.extensions.org.drawtemp.livingworld.data"
        for faction in living_data.get("factions", ()):
            identifier = faction["id"]
            add(SearchEntry("factions", "", identifier, identifier,
                            "Faction · réputation initiale " + str(faction["initial"]),
                            living_base + ".factions[id=" + identifier + "]"))
        for quest in living_data.get("daily_quests", ()):
            identifier = quest["id"]
            add(SearchEntry("quests", "", identifier, identifier,
                            "Quête quotidienne · " + quest["completion_flag"],
                            living_base + ".daily_quests[id=" + identifier + "]"))
            link(("quests", "", identifier), ("factions", "", quest["faction"]),
                 "faction", living_base + ".daily_quests[id=" + identifier +
                 "].faction")

        self.entries = tuple(sorted(items.values(), key=lambda e: e.key))
        self.by_key = items
        self.usages = tuple(sorted(edges, key=lambda e: (
            e.source, e.target, e.path, e.field)))
        self._searchable = {
            entry.key: _fold(" ".join((entry.title, entry.resource_id,
                                      entry.mission_id, entry.family,
                                      entry.details, entry.path)))
            for entry in self.entries
        }

    def search(self, query: str = "", *, families=(), mission_id: str = "",
               limit: int = 200) -> tuple[SearchEntry, ...]:
        if not isinstance(query, str) or not isinstance(mission_id, str):
            raise TypeError("Expected search text and mission string")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Result limit must be within 1..1000")
        terms = _fold(query).split()
        families = set(families)
        ranked = []
        for entry in self.entries:
            if families and entry.family not in families:
                continue
            if mission_id and entry.mission_id != mission_id and not (
                    entry.family == "maps" and entry.resource_id == mission_id):
                continue
            searchable = self._searchable[entry.key]
            if not all(term in searchable for term in terms):
                continue
            identifier, name = _fold(entry.resource_id), _fold(entry.title)
            priority = (0 if terms and identifier == " ".join(terms) else
                        1 if terms and identifier.startswith(terms[0]) else
                        2 if terms and name.startswith(terms[0]) else 3)
            ranked.append((priority, name, entry.key, entry))
        ranked.sort(key=lambda row: row[:3])
        return tuple(entry for _, _, _, entry in ranked[:limit])

    def references(self, key: tuple[str, str, str], direction="incoming"
                   ) -> tuple[SearchUsage, ...]:
        if direction not in ("incoming", "outgoing"):
            raise ValueError("Unknown reference direction")
        if key not in self.by_key:
            raise KeyError("Unknown search identity: " + repr(key))
        return tuple(edge for edge in self.usages if (
            edge.target if direction == "incoming" else edge.source) == key)
