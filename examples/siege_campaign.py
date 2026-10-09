"""Castle siege campaign: choose the breach, then resolve the courtyard."""
from sporebound.scenarios import ScenarioDirector

SIEGE_CAMPAIGN = {
    "start": "approach",
    "phases": [
        {"id": "approach", "mission": "castle_troll",
         "exits": {"ram": "gate", "artillery": "bombardment", "infiltrate": "relief"},
         "on_exit": {"ram": {"breach": "ram"}, "artillery": {"breach": "catapult"},
                     "infiltrate": {"breach": "infiltration"}}},
        {"id": "gate", "mission": "castle_ram",
         "exits": {"continue": "courtyard"}},
        {"id": "bombardment", "mission": "castle_artillery",
         "exits": {"continue": "courtyard"}},
        {"id": "relief", "mission": "castle_relief",
         "exits": {"continue": "courtyard"}},
        {"id": "courtyard", "mission": "castle_relief",
         "exits": {"finish": None}},
    ],
}

if __name__ == "__main__":
    director = ScenarioDirector.from_dict(SIEGE_CAMPAIGN)
    print(director.mission_id(), director.available_choices())
    director.advance("victory", "ram")
    print(director.mission_id(), director.state())
