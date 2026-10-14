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

# Presentation-only data. These descriptions mirror authored engine objectives.
CHAPTER_BEATS = {
    "a1_01_route": {
        "ordinal": "01", "chapter": "La route des fugitifs",
        "objective": "Atteindre les cases de sortie à l'est.",
        "context": "Le groupe quitte le camp avant l'aube. Les brigands "
                   "bloquent la route, mais leur élimination n'est pas nécessaire.",
        "tip": "Privilégiez les déplacements et la position : "
               "la victoire vient de l'extraction.",
        "victory": "Le passage est ouvert. Les réfugiés peuvent poursuivre leur route.",
    },
    "a1_02_pont": {
        "ordinal": "02", "chapter": "Le pont de la Brume",
        "objective": "Tenir le centre du pont pendant 35 ticks, sans contestation.",
        "context": "Un lancier et un arbalétrier défendent le passage. "
                   "La position des héros devient plus importante que leurs dégâts.",
        "tip": "Contrôlez les cases centrales et surveillez les intentions ennemies.",
        "victory": "Le pont est à vous. Les familles peuvent traverser.",
    },
    "a1_03_hospice": {
        "ordinal": "03", "chapter": "L'hospice assiégé",
        "objective": "Survivre aux attaques jusqu'à 75 ticks.",
        "context": "Les blessés ont besoin de temps. Il faut tenir les assaillants "
                   "loin des derniers abris.",
        "tip": "Économisez les soins et ne laissez pas un héros isolé.",
        "victory": "L'hospice a résisté. Les décisions prises ici pèseront sur la suite.",
    },
    "a1_04a_archives": {
        "ordinal": "04", "chapter": "Les archives du bailli",
        "objective": "Vaincre les défenseurs des archives.",
        "context": "Les registres peuvent révéler qui a ordonné l'attaque "
                   "de Domrémy. Jeanne choisit de chercher des preuves.",
        "tip": "Restez groupés et éliminez les ennemis qui protègent les documents.",
        "victory": "Les preuves sont préservées. Jeanne a un argument pour Vaucouleurs.",
    },
    "a1_04b_otages": {
        "ordinal": "04", "chapter": "Les otages de la tour",
        "objective": "Tenir 75 ticks en protégeant Anne.",
        "context": "Jeanne renonce aux archives pour libérer des prisonniers. "
                   "Anne doit survivre.",
        "tip": "Gardez Anne à l'abri : la victoire dépend de sa survie.",
        "victory": "Les prisonniers sont sauvés. Leur témoignage accompagnera Jeanne.",
    },
    "a1_05_vaucouleurs": {
        "ordinal": "05", "chapter": "Aux portes de Vaucouleurs",
        "objective": "Vaincre les assaillants qui bloquent l'accès à la ville.",
        "context": "Dernier obstacle avant l'audience avec Robert de Baudricourt.",
        "tip": "Attention à l'archer des remparts et au capitaine. "
               "Concentrez vos efforts sans exposer Jeanne.",
        "victory": "Les portes sont dégagées. Jeanne peut demander une audience.",
    },
}

CHAPTER_SCENE_KICKERS = {
    "sc_a1_camp": "01 · UNE ALLIANCE",
    "sc_a1_pont": "02 · LE PASSAGE",
    "sc_a1_hospice": "03 · UN REFUGE",
    "sc_a1_dilemme": "04 · UN CHOIX IRRÉVERSIBLE",
    "sc_a1_debrief": "05 · LA ROUTE CONTINUE",
    "sc_a1_fin": "FIN · UNE PROMESSE",
}


def chapter_mission_card(mission_id):
    """Return a read-only, French mission briefing."""
    from .model import RuleError
    if mission_id not in CHAPTER_BEATS:
        raise RuleError("Unknown Jeanne chapter I encounter")
    return dict(CHAPTER_BEATS[mission_id])


def chapter_progress(progress):
    """Derive friendly chapter progress without modifying Campaign."""
    completed = set(progress.completed)
    done = sum(any(mid in completed for mid in group) for group in (
        ("a1_01_route",), ("a1_02_pont",), ("a1_03_hospice",),
        ("a1_04a_archives", "a1_04b_otages"), ("a1_05_vaucouleurs",)))
    flags = progress.story_flags
    return {
        "completed": done,
        "total": 5,
        "companion": {"etienne": "Étienne", "agnes": "Agnès"}.get(
            flags.get("compagnon_acte1"), "À recruter"),
        "branch": {"archives": "Les archives", "otages": "Les otages"}.get(
            flags.get("acte1_choix"), "À décider"),
        "finished": flags.get("acte1_complete") is True,
        "support": {
            "archives": "Les preuves des archives",
            "temoins": "La parole des survivants",
            "foi": "La conviction de Jeanne",
        }.get(flags.get("acte2_appui"), ""),
    }


def chapter_auto_enemy(session, enabled=True):
    """Allow one ordinary controller AI activation only during enemy combat.

    No timer or state mutation here; the UI schedules the action and persists
    it through the same controller as manual enemy activations.
    """
    if not enabled or session is None or session.mode != "battle":
        return False
    battle = session.active_battle
    return (battle is not None and not session.finalized and
            not battle.deploying and battle.result is None and
            not session.tactical_story_pending and
            not session.progress.story_pending and
            battle.active is not None and battle.active.team == "enemy")
