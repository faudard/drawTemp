"""Opt-in Jeanne Chapter I, reusing the existing tactical and story data.

Constructed in memory: the original Jeanne project and its save slots are
never modified or interpreted as chapter-one slots.
"""
from copy import deepcopy

from .model import require


CHAPTER_CAMPAIGN_ID = "jeanne_chapter1"
CHAPTER_MISSIONS = (
    "a1_01_route", "a1_02_pont", "a1_03_hospice",
    "a1_04a_archives", "a1_04b_otages", "a1_05_vaucouleurs",
)


def chapter_one_project(content, project):
    """Adapt a valid Jeanne project to an independent Act I campaign."""
    require(project.campaign("jeanne") is not None,
            "Chapter I requires the original Jeanne campaign")
    require(all(mid in content.missions for mid in CHAPTER_MISSIONS),
            "Chapter I requires all six authored mission variants")
    require(any(scene["id"] == "sc_a1_camp"
                for scene in project.story.get("scenes", [])),
            "Chapter I requires the refugee camp scene")
    chapter = deepcopy(project)
    chapter.title = "Jeanne d'Arc — Chapitre I"
    chapter.subtitle = "Les Cendres · Du camp des réfugiés à Vaucouleurs"
    chapter.campaigns = [{
        "id": CHAPTER_CAMPAIGN_ID,
        "name": "Chapitre I — Les Cendres",
        "description": "Une route, un compagnon, un choix, une audience.",
        "start_mission": "a1_01_route",
    }]
    chapter.story["entry_scenes"] = {CHAPTER_CAMPAIGN_ID: "sc_a1_camp"}
    chapter.validate(content)
    return chapter
