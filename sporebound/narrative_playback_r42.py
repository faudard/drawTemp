"""R42.B2: saved dialogue line cursor using existing Campaign.story_flags.

A presentation cursor is not a quest flag interpreter. R9 remains responsible
for choices and effects. No new GameSession recording field or replay schema.
"""
from .model import require

CURSOR = 'r42_line_cursor'


def initialize_cursor(progress):
    require(CURSOR not in progress.story_flags,
            'R42 dialogue cursor collides with an existing story flag')
    require(len(progress.story_flags) < 1000, 'Narrative flag budget exhausted')
    progress.story_flags[CURSOR] = 0


def validate_cursor(progress, scene=None):
    cursor = progress.story_flags.get(CURSOR)
    require(type(cursor) is int and 0 <= cursor <= 31,
            'Missing or corrupted R42 dialogue line cursor')
    if scene is not None:
        require(cursor < len(scene['lines']),
                'R42 saved cursor is beyond the dialogue lines')
    return cursor


def current_line(progress, scene):
    require(scene is not None, 'No active narrative scene')
    index = validate_cursor(progress, scene)
    lines = scene['lines']
    line = lines[index]
    return {'scene_id': scene['id'], 'id': line['id'],
            'speaker': line['speaker'], 'text': line['text'],
            'index': index, 'count': len(lines),
            'complete': index == len(lines) - 1}


def advance_line(progress, scene):
    presentation = current_line(progress, scene)
    require(not presentation['complete'],
            'All dialogue lines have already been read')
    progress.story_flags[CURSOR] = presentation['index'] + 1
    return current_line(progress, scene)


def reset_cursor(progress):
    require(type(progress.story_flags.get(CURSOR)) is int,
            'R42 dialogue cursor is missing')
    progress.story_flags[CURSOR] = 0
