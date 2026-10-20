"""VS-42 — La loyauté du capitaine, an actual R42 v2 Player project.

The slice is generated from the small reference fixture. It uses the R9
StoryBook and existing R5 campaign flow, never an independent story engine.
No generated files or changes to the source Jeanne fixture.
"""
from __future__ import annotations

from copy import deepcopy

from drawtemp.sdk.reference import reference_project
from sporebound.game_project import GameProject
from sporebound.model import Content
from sporebound.narrative_state_r42 import state_key, state_condition

QUEST_MISSION = 'r42_captain_quest'
ENDINGS = ('alliance', 'accord', 'exile')
CAMPAIGN = 'main'


def _line(identifier, speaker, text):
    return {'id': identifier, 'speaker': speaker, 'text': text}


def _scene(identifier, title, first_speaker, first_text, choices,
           second_speaker=None, second_text=None):
    lines = [_line('line_001', first_speaker, first_text)]
    if second_text is not None:
        lines.append(_line('line_002', second_speaker or '', second_text))
    return {'id': identifier, 'title': title,
            'speaker': first_speaker, 'text': first_text,
            'lines': lines, 'choices': choices}


def _choice(identifier, label, *, target='', condition=None, effects=()):
    result = {'id': identifier, 'label': label}
    if target:
        result['next_scene'] = target
    if condition is not None:
        result['when'] = deepcopy(condition)
    if effects:
        result['effects'] = deepcopy(list(effects))
    return result


def make_captain_slice():
    """Return validated (Content, GameProject), ready for R1/Player use."""
    base_content, _ = reference_project()
    content_data = base_content.to_dict()
    extra = deepcopy(content_data['missions'][0])
    extra['id'] = QUEST_MISSION
    extra['name'] = 'Quête conditionnelle — La lettre du capitaine'
    extra['next_missions'] = []
    extra['triggers'] = []
    content_data['missions'].append(extra)
    content = Content.from_dict(content_data)
    project = GameProject.default(content)
    project.title = 'La loyauté du capitaine'
    project.subtitle = 'Trois destins pour un royaume'
    declare = [
        {'id': 'captain_trust', 'kind': 'relation', 'scope': 'campaign',
         'owner': CAMPAIGN, 'initial': 0},
        {'id': 'evidence', 'kind': 'bool', 'scope': 'campaign',
         'owner': CAMPAIGN, 'initial': False},
        {'id': 'quest_ready', 'kind': 'bool', 'scope': 'campaign',
         'owner': CAMPAIGN, 'initial': False},
        {'id': 'ending', 'kind': 'text', 'scope': 'campaign',
         'owner': CAMPAIGN, 'initial': 'none'},
    ]
    keys = {row['id']: state_key(row) for row in declare}

    def setvar(name, value):
        return {'kind': 'set_flag', 'flag': keys[name], 'value': value}

    def addtrust(value):
        return {'kind': 'add_flag', 'flag': keys['captain_trust'], 'amount': value}

    def cond(name, op, value):
        return state_condition({'schema_version': 2, 'state': declare},
                               identifier=name, scope='campaign',
                               owner=CAMPAIGN, operator=op, value=value)

    loyal = cond('captain_trust', 'gte', 30)
    hostile = cond('captain_trust', 'lte', -10)
    evidence = cond('evidence', 'eq', True)
    quest = cond('quest_ready', 'eq', True)
    project.story = {
        'schema_version': 2,
        'entry_scenes': {'main': 'oath'},
        'after_mission': {},
        'subgraphs': [
            {'id': 'shared_council', 'entry_scene': 'council'},
            {'id': 'shared_camp', 'entry_scene': 'camp'},
        ],
        'state': declare,
        'scenes': [
            _scene('oath', 'Le serment', 'Jeanne',
                   'Le capitaine attend notre jugement.',
                   [_choice('defend', 'Lui faire confiance', target='gate',
                            effects=[addtrust(25)]),
                    _choice('accuse', 'Mettre sa loyauté en doute',
                            target='archive', effects=[addtrust(-20)])],
                   'Capitaine', 'Mes hommes attendent votre décision.'),
            _scene('gate', 'Devant les portes', 'Capitaine',
                   'Nos blessés sont encore dehors.',
                   [_choice('rescue', 'Sauver les blessés', target='council',
                            effects=[addtrust(20)]),
                    _choice('ledger', 'Ouvrir les registres', target='council',
                            effects=[setvar('evidence', True)])]),
            _scene('archive', 'Les archives', 'Jeanne',
                   'Des lettres du capitaine sont scellées.',
                   [_choice('reveal', 'Révéler les lettres', target='council',
                            effects=[setvar('evidence', True), addtrust(15)]),
                    _choice('silence', 'Ne rien dire', target='council',
                            effects=[addtrust(-10)])]),
            _scene('council', 'Le conseil', 'Conseiller',
                   'La mission du capitaine peut être confiée sous conditions.',
                   [_choice('trust', 'Lui confier la mission',
                            condition=loyal, target='quest_brief',
                            effects=[setvar('quest_ready', True),
                                     {'kind': 'unlock_mission',
                                      'mission': QUEST_MISSION}]),
                    _choice('proof', 'Agir sur les preuves',
                            condition=evidence, target='quest_brief',
                            effects=[setvar('quest_ready', True),
                                     {'kind': 'unlock_mission',
                                      'mission': QUEST_MISSION}]),
                    _choice('avoid', 'Rentrer au camp sans mission',
                            target='camp')]),
            _scene('quest_brief', 'La lettre', 'Capitaine',
                   'Je récupérerai la lettre qui pourrait sauver nos alliés.',
                   [_choice('accept', 'Accepter son aide', target='camp',
                            effects=[addtrust(5)])],
                   'Jeanne', 'Cette lettre scellera notre destin.'),
            _scene('camp', 'La dernière veillée', 'Jeanne',
                   'Notre décision déterminera le sort du capitaine.',
                   [_choice('alliance', 'Faire alliance', target='ending_alliance',
                            condition={'all': [loyal, quest]},
                            effects=[setvar('ending', 'alliance')]),
                    _choice('exile', 'Le bannir du royaume',
                            target='ending_exile', condition=hostile,
                            effects=[setvar('ending', 'exile')]),
                    _choice('accord', 'Négocier un accord limité',
                            target='ending_accord',
                            effects=[setvar('ending', 'accord')])],
                   'Capitaine', 'Je répondrai de ce choix.'),
            _scene('ending_alliance', 'Fin — Alliance', 'Jeanne',
                   'Le capitaine devient notre allié.',
                   [_choice('finish', 'Terminer')]),
            _scene('ending_accord', 'Fin — Accord', 'Jeanne',
                   'Une paix fragile préserve le royaume.',
                   [_choice('finish', 'Terminer')]),
            _scene('ending_exile', 'Fin — Exil', 'Jeanne',
                   'Le capitaine est exilé.',
                   [_choice('finish', 'Terminer')]),
        ],
    }
    # Existing R5 flow owns gates/endings; no R42 quest engine is created.
    project.campaign_flow = {
        'gates': {QUEST_MISSION: quest},
        'endings': {name: cond('ending', 'eq', name) for name in ENDINGS},
    }
    project.validate(content)
    return content, project
