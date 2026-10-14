"""Small deterministic Jeanne fixture built from canonical content, never overwritten."""
from copy import deepcopy
from importlib.resources import files
from drawtemp.core import Content, GameProject

MISSION = "r0_village_forest"


def reference_project():
    source = Content.load(files("sporebound").joinpath("content/jeanne.json"))
    data = source.to_dict()
    mission = deepcopy(next(m for m in data["missions"] if m["id"] == "p0_01_lame"))
    mission.update(id=MISSION, name="R0 — village et lisière", next_missions=[])
    mission["board"]["tiles"].extend([
        {"pos": [0, 0], "surface": "grass", "feature": "tree", "blocked": True},
        {"pos": [1, 0], "surface": "grass", "feature": "tree", "blocked": True},
        {"pos": [1, 4], "surface": "cobble"},
        {"pos": [2, 4], "surface": "cobble"},
    ])
    mission["objects"] = [
        {"id": "gate", "kind": "door", "pos": [3, 4]},
        {"id": "lever", "kind": "switch", "pos": [2, 4], "link": "gate"},
    ]
    data["missions"] = [mission]
    content = Content.from_dict(data)
    project = GameProject.default(content)
    project.title = "Jeanne — référence de migration R0"
    project.story = {
        "entry_scenes": {"main": "arrival"}, "after_mission": {},
        "scenes": [{"id": "arrival", "title": "À la lisière", "speaker": "Jeanne",
                    "text": "Ouvrons la porte du village avant l'entraînement.",
                    "choices": [{"id": "enter", "label": "Entrer"}]}],
    }
    project.validate(content)
    return content, project
